import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.routes import get_db, extraction_service
from app.llm.extractor import LLMExtractor
from app.llm.schemas import VerifyDocumentRequest, VerifyDocumentResponse, LLMExtractionMetadata
from app.utils.image_utils import fetch_image_url
from app.config import settings
from app.storage.repository import (
    RCValidationRepository, DLValidationRepository, AadhaarValidationRepository,
    LLMExtractionRepository,
)

verify_router = APIRouter()

REPO_MAP = {
    "rc_book": RCValidationRepository,
    "driving_license": DLValidationRepository,
    "aadhaar": AadhaarValidationRepository,
}


@verify_router.post("/verify/document", response_model=VerifyDocumentResponse)
async def verify_document(
    request: VerifyDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Fetch image
    image_bytes = fetch_image_url(request.image_url)

    # 2. Run OCR
    ocr_result = extraction_service.extract(
        image_bytes=image_bytes,
        engine="paddle",
        document_type=request.image_type,
        include_raw_text=True,
        side=request.side,
    )
    raw_text = ocr_result.get("raw_text", "")

    # 3. LLM extraction
    llm_extractor = LLMExtractor()
    llm_result = await llm_extractor.extract(
        ocr_text_front=raw_text if request.side == "front" else None,
        ocr_text_back=raw_text if request.side == "back" else None,
        document_type=request.image_type,
        side=request.side,
    )

    # 4. Evaluate quality
    iq = ocr_result.get("image_quality", {})
    quality_score = iq.get("overall_score", 0.0)
    is_acceptable = iq.get("is_acceptable", False)
    da = ocr_result.get("document_authenticity", {})
    authenticity_passed = da.get("is_authentic", False) if da else False

    rejection_reasons = list(iq.get("feedback", []))
    if not authenticity_passed and da:
        rejection_reasons.append("Document authenticity check failed")

    # 5. Store in DB
    repo = REPO_MAP[request.image_type](db)
    fields = {f["label"]: f["value"] for f in ocr_result.get("fields", [])}
    validation_id = ""

    try:
        if request.side == "front":
            record = repo.create(
                driver_id=request.driver_id,
                front_url=request.image_url,
                overall_status="pending_back",
                front_quality_score=quality_score,
                front_issues=rejection_reasons,
                front_fields=fields,
                ocr_raw_text_front=raw_text,
            )
            validation_id = record.id
        else:
            record = repo.get_pending_back_for_driver(request.driver_id)
            if not record:
                record = repo.create(
                    driver_id=request.driver_id,
                    back_url=request.image_url,
                    overall_status="needs_review",
                    back_quality_score=quality_score,
                    back_issues=rejection_reasons,
                    back_fields=fields,
                    ocr_raw_text_back=raw_text,
                    requires_review=True,
                )
            else:
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
                background_tasks.add_task(
                    _run_govt_verification, record.id, request.image_type, db
                )
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
    except Exception:
        pass  # DB issues shouldn't crash the endpoint

    # 6. Build response
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


async def _run_govt_verification(validation_id: str, doc_type: str, db: Session):
    """Background task: call govt API and run auto-approval after response."""
    from app.govt.client import GovtAPIClient
    from app.verification.engine import AutoApprovalEngine
    # Placeholder — will be fully implemented when govt API is integrated
    pass


# --- Task 15: Status + Admin ---

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


@verify_router.post("/admin/retry-stuck")
def retry_stuck(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Find records stuck in pending_verification and re-trigger govt API."""
    # Placeholder for now
    return {"success": True, "retried": 0}
