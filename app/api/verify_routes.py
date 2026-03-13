import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, BackgroundTasks, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.routes import get_db, extraction_service
from app.llm.extractor import LLMExtractor
from app.llm.schemas import VerifyDocumentRequest, VerifyDocumentResponse, LLMExtractionMetadata
from app.utils.image_utils import fetch_image_url
from app.config import settings
from app.storage.models import RCValidation, DLValidation, AadhaarValidation
from app.storage.repository import (
    RCValidationRepository, DLValidationRepository, AadhaarValidationRepository,
    LLMExtractionRepository, GovtVerificationRepository, FieldComparisonRepository,
    DriverOnboardingRepository,
)

logger = logging.getLogger(__name__)

verify_router = APIRouter()

# Singleton LLM extractor — reuses connection pool across requests
_llm_extractor = LLMExtractor()

REPO_MAP = {
    "rc_book": RCValidationRepository,
    "driving_license": DLValidationRepository,
    "aadhaar": AadhaarValidationRepository,
}

DOC_NUMBER_FIELD = {
    "rc_book": "registration_number",
    "driving_license": "dl_number",
    "aadhaar": "aadhaar_number",
}


@verify_router.post("/verify/document", response_model=VerifyDocumentResponse)
async def verify_document(
    request: VerifyDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Fetch image
    image_bytes = fetch_image_url(request.image_url)

    # 2. Run OCR (must complete before parallel step)
    ocr_result = extraction_service.extract(
        image_bytes=image_bytes,
        engine="paddle",
        document_type=request.image_type,
        include_raw_text=True,
        side=request.side,
    )
    raw_text = ocr_result.get("raw_text", "")

    # 3. Quality evaluation + LLM extraction in PARALLEL (I5 fix)
    async def _quality_eval():
        iq = ocr_result.get("image_quality", {})
        da = ocr_result.get("document_authenticity", {})
        return iq, da

    async def _llm_extract():
        return await _llm_extractor.extract(
            ocr_text_front=raw_text if request.side == "front" else None,
            ocr_text_back=raw_text if request.side == "back" else None,
            document_type=request.image_type,
            side=request.side,
        )

    (iq, da), llm_result = await asyncio.gather(_quality_eval(), _llm_extract())

    quality_score = iq.get("overall_score", 0.0)
    is_acceptable = iq.get("is_acceptable", False)
    authenticity_passed = da.get("is_authentic", False) if da else False

    rejection_reasons = list(iq.get("feedback", []))
    if not authenticity_passed and da:
        rejection_reasons.append("Document authenticity check failed")

    # 4. Store in DB (C2 fix — no more silent exception swallowing)
    repo = REPO_MAP[request.image_type](db)
    fields = {f["label"]: f["value"] for f in ocr_result.get("fields", [])}

    try:
        # C3/C4 fix — proper front/back upload logic
        if request.side == "front":
            # Check if there's already a pending_back record for this driver
            existing = repo.get_pending_back_for_driver(request.driver_id)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="Front side already uploaded. Please upload the back side.",
                )
            record = repo.create(
                driver_id=request.driver_id,
                front_url=request.image_url,
                overall_status="pending_back",
                front_quality_score=quality_score,
                front_issues=rejection_reasons,
                front_fields=fields,
                ocr_raw_text_front=raw_text,
            )
        else:
            # Back upload — must have a pending_back record
            record = repo.get_pending_back_for_driver(request.driver_id)
            if not record:
                raise HTTPException(
                    status_code=400,
                    detail="Please upload the front side first.",
                )
            merged = {**(record.front_fields or {}), **fields}
            record = repo.update(
                record,
                back_url=request.image_url,
                overall_status="pending_verification",
                back_quality_score=quality_score,
                back_issues=rejection_reasons,
                back_fields=fields,
                merged_fields=merged,
                ocr_raw_text_back=raw_text,
            )
            # Fire background govt verification (disabled until reseller keys are configured)
            # doc_number = (record.merged_fields or {}).get(
            #     DOC_NUMBER_FIELD.get(request.image_type, ""), ""
            # )
            # background_tasks.add_task(
            #     _run_govt_verification, record.id, request.image_type, doc_number, db
            # )

        validation_id = record.id

        # Store LLM extraction
        if llm_result.status == "success":
            llm_repo = LLMExtractionRepository(db, request.image_type)
            llm_repo.create(
                validation_id=validation_id,
                model_provider=llm_result.metadata.llm_provider,
                model_name=llm_result.metadata.llm_model,
                prompt_version=llm_result.metadata.prompt_version,
                llm_raw_response=llm_result.raw_response,
                system_prompt_used=llm_result.system_prompt_used,
                extracted_fields=llm_result.extracted_fields,
                extraction_time_ms=llm_result.metadata.extraction_time_ms,
                token_input=llm_result.token_input,
                token_output=llm_result.token_output,
                cost_inr=llm_result.cost_inr,
                status=llm_result.status,
            )
    except HTTPException:
        raise  # Re-raise validation errors (C3/C4)
    except Exception as e:
        logger.error(f"Failed to store verification record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

    # 5. Build response
    if is_acceptable and (authenticity_passed or not da):
        status = "accepted"
        message = "Document accepted"
        structured_data = llm_result.extracted_fields if llm_result.status == "success" else None
    else:
        status = "rejected"
        message = "Please re-upload a clearer photo of the document"
        structured_data = None

    return VerifyDocumentResponse(
        request_id=validation_id,
        status=status,
        quality_score=quality_score,
        authenticity_passed=authenticity_passed,
        rejection_reasons=rejection_reasons,
        message=message,
        structured_data=structured_data,
        extraction_metadata=LLMExtractionMetadata(
            llm_provider=llm_result.metadata.llm_provider,
            llm_model=llm_result.metadata.llm_model,
            extraction_time_ms=llm_result.metadata.extraction_time_ms,
            prompt_version=llm_result.metadata.prompt_version,
            ocr_engine="paddleocr",
        ) if llm_result.status == "success" else None,
    )


# C1 fix — fully implement background govt verification
async def _run_govt_verification(validation_id: str, doc_type: str, document_number: str, db: Session):
    """Background task: govt API → field comparison → auto-approval."""
    from app.govt.client import GovtAPIClient
    from app.verification.comparator import FieldComparator
    from app.verification.engine import AutoApprovalEngine

    repo = REPO_MAP[doc_type](db)

    try:
        # 1. Update status to in_progress
        record = repo.get_by_id(validation_id)
        if not record:
            logger.error(f"Validation record {validation_id} not found for govt verification")
            return
        repo.update(record, verification_status="in_progress")

        # 2. Call govt API
        govt_client = GovtAPIClient(db)
        govt_result = await govt_client.verify(
            document_number=document_number,
            doc_type=doc_type,
        )

        # 3. Store govt verification result
        govt_repo = GovtVerificationRepository(db, doc_type)
        govt_record = govt_repo.create(
            validation_id=validation_id,
            reseller_code=govt_result.reseller_code,
            raw_response=govt_result.raw_response,
            govt_fields=govt_result.normalized_fields if isinstance(govt_result.normalized_fields, dict) else govt_result.normalized_fields.model_dump() if hasattr(govt_result.normalized_fields, 'model_dump') else {},
            status=govt_result.status,
            error_message=govt_result.error_message,
            response_time_ms=govt_result.response_time_ms,
            api_cost_inr=govt_result.api_cost_inr,
        )

        # Update validation with govt_verification_id FK
        repo.update(record, govt_verification_id=govt_record.id)

        if govt_result.status != "success":
            repo.update(record, verification_status=govt_result.status)
            logger.warning(f"Govt verification failed for {validation_id}: {govt_result.error_message}")
            return

        # 4. Run field comparison
        comparator = FieldComparator()
        llm_repo = LLMExtractionRepository(db, doc_type)
        llm_record = llm_repo.get_by_validation_id(validation_id)
        llm_fields = llm_record.extracted_fields if llm_record else {}
        govt_fields = govt_result.normalized_fields if isinstance(govt_result.normalized_fields, dict) else govt_result.normalized_fields.model_dump() if hasattr(govt_result.normalized_fields, 'model_dump') else {}
        mapper_fields = record.mapper_raw_output or {}

        comparison_results = []
        all_field_names = set(list(llm_fields.keys()) + list(govt_fields.keys()))
        for field_name in all_field_names:
            if field_name in ("extra_fields",):
                continue
            comp = comparator.compare_field(
                field_name=field_name,
                mapper_value=mapper_fields.get(field_name),
                llm_value=llm_fields.get(field_name),
                govt_value=govt_fields.get(field_name),
            )
            comp["validation_id"] = validation_id
            comparison_results.append(comp)

        if comparison_results:
            fc_repo = FieldComparisonRepository(db, doc_type)
            fc_repo.bulk_create(comparison_results)

        # 5. Compute match score
        match_score = comparator.compute_match_score(comparison_results)
        critical_match = all(
            c["is_match"] for c in comparison_results
            if c["field_name"] in {"chassis_number", "engine_number", "registration_number"}
        )

        # 6. Run auto-approval engine
        engine = AutoApprovalEngine()
        front_quality = record.front_quality_score or 0.0
        back_quality = record.back_quality_score or 0.0
        llm_status = llm_record.status if llm_record else "failed"

        if doc_type == "rc_book":
            decision = engine.evaluate_rc(
                front_quality=front_quality,
                back_quality=back_quality,
                llm_status=llm_status,
                govt_status=govt_result.status,
                govt_match_score=match_score,
                govt_rc_status=govt_fields.get("rc_status", ""),
                govt_fitness_upto=govt_fields.get("fitness_upto", "1900-01-01"),
                govt_insurance_upto=govt_fields.get("insurance_upto", "1900-01-01"),
                critical_fields_match=critical_match,
            )
        elif doc_type == "driving_license":
            decision = engine.evaluate_dl(
                front_quality=front_quality,
                back_quality=back_quality,
                llm_status=llm_status,
                govt_status=govt_result.status,
                govt_match_score=match_score,
                govt_dl_status=govt_fields.get("dl_status", ""),
                govt_validity_tr=govt_fields.get("validity_tr", "1900-01-01"),
                cov_covers_vehicle=True,  # placeholder — needs vehicle class check
                critical_fields_match=critical_match,
            )
        else:  # aadhaar
            decision = engine.evaluate_aadhaar(
                front_quality=front_quality,
                back_quality=back_quality,
                llm_status=llm_status,
                govt_status=govt_result.status,
                govt_match_score=match_score,
                govt_aadhaar_status=govt_fields.get("aadhaar_status", ""),
                critical_fields_match=critical_match,
            )

        # 7. Update validation with approval decision
        verification_status = "verified" if match_score >= settings.AUTO_APPROVAL_MATCH_THRESHOLD else "mismatch"
        update_kwargs = {
            "verification_status": verification_status,
            "approval_method": decision.method,
            "govt_match_score": match_score,
        }
        if decision.method in ("auto_approved", "auto_rejected"):
            update_kwargs["approved_at"] = datetime.utcnow()
        if decision.method == "manual_review":
            update_kwargs["requires_review"] = True

        repo.update(record, **update_kwargs)

        # 8. Update driver onboarding status
        onboarding_repo = DriverOnboardingRepository(db)
        onboarding_kwargs = {}
        if doc_type == "rc_book":
            onboarding_kwargs["rc_status"] = decision.method
        elif doc_type == "driving_license":
            onboarding_kwargs["dl_status"] = decision.method
        else:
            onboarding_kwargs["aadhaar_status"] = decision.method
        onboarding_repo.upsert(driver_id=record.driver_id, **onboarding_kwargs)

        logger.info(f"Govt verification complete for {validation_id}: {decision.method} ({decision.reason})")

    except Exception as e:
        logger.error(f"Govt verification failed for {validation_id}: {e}", exc_info=True)
        try:
            record = repo.get_by_id(validation_id)
            if record:
                repo.update(record, verification_status="failed")
        except Exception:
            logger.error(f"Failed to update status to 'failed' for {validation_id}", exc_info=True)


# --- Status + Admin ---

@verify_router.get("/verify/document/{validation_id}/status")
def get_verification_status(validation_id: str, db: Session = Depends(get_db)):
    """Look up verification status across all doc types."""
    for repo_cls in [RCValidationRepository, DLValidationRepository, AadhaarValidationRepository]:
        repo = repo_cls(db)
        record = repo.get_by_id(validation_id)
        if record:
            return {
                "validation_id": record.id,
                "overall_status": record.overall_status,
                "verification_status": getattr(record, "verification_status", None),
                "approval_method": getattr(record, "approval_method", None),
                "govt_match_score": getattr(record, "govt_match_score", None),
                "requires_review": record.requires_review,
            }
    raise HTTPException(status_code=404, detail="Validation record not found")


def require_admin(x_admin_key: str = Header(...)):
    if not settings.ADMIN_API_KEY or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# I6 fix — implement retry-stuck endpoint
@verify_router.post("/admin/retry-stuck")
def retry_stuck(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Find records stuck in verification_status='in_progress' for >10 min and re-trigger."""
    stuck_threshold = datetime.utcnow() - timedelta(minutes=10)
    stuck_records = []

    for doc_type, model in [("rc_book", RCValidation), ("driving_license", DLValidation), ("aadhaar", AadhaarValidation)]:
        records = (
            db.query(model)
            .filter(
                model.verification_status == "in_progress",
                model.updated_at < stuck_threshold,
            )
            .all()
        )
        for record in records:
            record.verification_status = "pending"
            record.updated_at = datetime.utcnow()

            # Extract document number for re-triggering
            doc_number = ""
            if doc_type == "rc_book":
                doc_number = (record.merged_fields or {}).get("registration_number", "")
            elif doc_type == "driving_license":
                doc_number = (record.merged_fields or {}).get("dl_number", "")
            else:
                doc_number = (record.merged_fields or {}).get("aadhaar_number", "")

            background_tasks.add_task(
                _run_govt_verification, record.id, doc_type, doc_number, db
            )
            stuck_records.append({"id": record.id, "doc_type": doc_type})

    db.commit()
    return {"success": True, "retried": len(stuck_records), "records": stuck_records}
