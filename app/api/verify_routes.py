import asyncio
import logging
from datetime import datetime, timedelta

import cv2
import numpy as np
from fastapi import APIRouter, Depends, BackgroundTasks, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.routes import get_db
from app.core.image_quality import ImageQualityAssessor
from app.engines.google_engine import GoogleVisionEngine
from app.llm.extractor import LLMExtractor
from app.llm.schemas import VerifyDocumentRequest, VerifyDocumentResponse, LLMExtractionMetadata
from app.utils.image_utils import fetch_image_url
from app.config import settings
from app.storage.models import DocumentValidation
from app.storage.repository import (
    DocumentValidationRepository,
    LLMExtractionRepository,
    GovtVerificationRepository,
    FieldComparisonRepository,
    DriverOnboardingRepository,
)

logger = logging.getLogger(__name__)

verify_router = APIRouter()

# Singletons — reused across requests
_llm_extractor = LLMExtractor()
_google_engine = None  # lazy init
_quality_assessor = ImageQualityAssessor()

DOC_NUMBER_FIELD = {
    "rc_book": "registration_number",
    "driving_license": "dl_number",
    "aadhaar": "aadhaar_number",
}

# Mandatory fields per doc type + side (for Layer B completeness check)
MANDATORY_FIELDS = {
    "rc_book": {
        "front": ["registration_number", "owner_name", "fuel_type", "registration_date"],
        "back": ["registration_number", "manufacturer"],
    },
    "driving_license": {
        "front": ["dl_number", "holder_name", "date_of_birth"],
        "back": ["dl_number"],
    },
    "aadhaar": {
        "front": ["aadhaar_number", "holder_name"],
        "back": ["aadhaar_number"],
    },
}


def _get_google_engine() -> GoogleVisionEngine:
    global _google_engine
    if _google_engine is None:
        _google_engine = GoogleVisionEngine()
    return _google_engine


def _check_field_completeness(extracted_fields: dict, doc_type: str, side: str):
    """Layer B: check mandatory fields are present in LLM output."""
    mandatory = MANDATORY_FIELDS.get(doc_type, {}).get(side, [])
    missing = [f for f in mandatory if not extracted_fields.get(f)]
    completeness_score = (len(mandatory) - len(missing)) / len(mandatory) if mandatory else 1.0
    return completeness_score, missing


@verify_router.post("/verify/document", response_model=VerifyDocumentResponse)
async def verify_document(
    request: VerifyDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # =========================================================================
    # Step 1: Fetch image (sync HTTP call — run in executor to avoid blocking)
    # =========================================================================
    loop = asyncio.get_event_loop()
    image_bytes = await loop.run_in_executor(None, fetch_image_url, request.image_url)

    # =========================================================================
    # Step 2: Image Quality Check FIRST (saves Google Vision + LLM cost on bad images)
    # =========================================================================
    def _quality_sync():
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return {
                "blur_score": 0.0, "brightness_score": 0.0, "resolution_score": 0.0,
                "layer_a_score": 0.0, "overall_score": 0.0, "is_acceptable": False,
                "feedback": ["Could not decode image"],
            }
        props = _quality_assessor.assess_image_properties(image)
        score = props["layer_a_score"]
        is_acceptable = score >= settings.QUALITY_GATE_THRESHOLD
        feedback = []
        if props["blur_score"] < 0.5:
            feedback.append("Image appears blurry. Please upload a clearer photo.")
        if props["brightness_score"] < 0.5:
            feedback.append("Image is too dark or overexposed. Please ensure good lighting.")
        if props["resolution_score"] < 0.5:
            feedback.append("Image resolution is too low. Please upload a higher resolution image.")
        return {
            **props,
            "overall_score": score,
            "is_acceptable": is_acceptable,
            "feedback": feedback,
        }

    quality_a = await loop.run_in_executor(None, _quality_sync)

    # =========================================================================
    # Step 3: Quality Gate — reject BEFORE calling Google Vision (saves OCR + LLM cost)
    # =========================================================================
    repo = DocumentValidationRepository(db)

    if not quality_a["is_acceptable"]:
        # Store record with rejection — no OCR text (Vision was never called)
        try:
            existing = repo.get_latest_for_driver(request.driver_id, request.image_type)
            if existing:
                # Update existing record with re-uploaded side
                update_kwargs = {
                    f"{request.side}_url": request.image_url,
                    f"{request.side}_quality_score": quality_a["overall_score"],
                    f"{request.side}_issues": quality_a["feedback"],
                    "overall_status": "rejected",
                }
                record = repo.update(existing, **update_kwargs)
            else:
                # Create new record (any side can be first)
                record = repo.create(
                    driver_id=request.driver_id,
                    doc_type=request.image_type,
                    **{f"{request.side}_url": request.image_url},
                    overall_status="rejected",
                    **{f"{request.side}_quality_score": quality_a["overall_score"]},
                    **{f"{request.side}_issues": quality_a["feedback"]},
                )
            validation_id = record.id
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to store rejection record: {e}", exc_info=True)
            validation_id = "error"

        return VerifyDocumentResponse(
            request_id=validation_id,
            status="rejected",
            quality_score=quality_a["overall_score"],
            rejection_reasons=quality_a["feedback"],
            message="Please re-upload a clearer photo",
            structured_data=None,
            extraction_metadata=None,
        )

    # =========================================================================
    # Step 4: Google Vision OCR (only if quality passed — saves ~₹0.12/bad image)
    # =========================================================================
    def _ocr_sync():
        engine = _get_google_engine()
        return engine.extract(image_bytes)

    ocr_result = await loop.run_in_executor(None, _ocr_sync)
    raw_text = ocr_result.get("raw_text", "")
    ocr_confidence = ocr_result.get("confidence", 0.0)

    # =========================================================================
    # Step 5: LLM Haiku extraction (only if quality passed)
    # =========================================================================
    llm_result = await _llm_extractor.extract(
        ocr_text_front=raw_text if request.side == "front" else None,
        ocr_text_back=raw_text if request.side == "back" else None,
        document_type=request.image_type,
        side=request.side,
    )

    # =========================================================================
    # Step 6: Field completeness check (Layer B)
    # =========================================================================
    extracted_fields = llm_result.extracted_fields if llm_result.status == "success" else {}
    completeness_score, missing_fields = _check_field_completeness(
        extracted_fields, request.image_type, request.side
    )

    # =========================================================================
    # Step 7: Store in DB
    # =========================================================================
    try:
        existing = repo.get_latest_for_driver(request.driver_id, request.image_type)
        other_side = "back" if request.side == "front" else "front"

        if existing:
            # Update existing record — driver is re-uploading or adding other side
            has_other_side = getattr(existing, f"{other_side}_url") is not None
            new_status = "pending_verification" if has_other_side else f"pending_{other_side}"
            update_kwargs = {
                f"{request.side}_url": request.image_url,
                f"{request.side}_quality_score": quality_a["overall_score"],
                f"{request.side}_issues": quality_a["feedback"],
                f"ocr_raw_text_{request.side}": raw_text,
                "overall_status": new_status,
            }
            record = repo.update(existing, **update_kwargs)
        else:
            # First upload for this driver+doc_type — any side can be first
            record = repo.create(
                driver_id=request.driver_id,
                doc_type=request.image_type,
                **{f"{request.side}_url": request.image_url},
                overall_status=f"pending_{other_side}",
                **{f"{request.side}_quality_score": quality_a["overall_score"]},
                **{f"{request.side}_issues": quality_a["feedback"]},
                **{f"ocr_raw_text_{request.side}": raw_text},
            )

        validation_id = record.id

        # Extract doc_number from LLM fields
        doc_number_key = DOC_NUMBER_FIELD.get(request.image_type, "")
        doc_number = extracted_fields.get(doc_number_key, "")
        if doc_number:
            repo.update(record, doc_number=doc_number)

        # Store LLM extraction
        if llm_result.status == "success":
            llm_repo = LLMExtractionRepository(db)
            llm_record = llm_repo.create(
                validation_id=validation_id,
                doc_type=request.image_type,
                model_provider=llm_result.metadata.llm_provider,
                model_name=llm_result.metadata.llm_model,
                prompt_version=llm_result.metadata.prompt_version,
                llm_raw_response=llm_result.raw_response,
                system_prompt_used=llm_result.system_prompt_used,
                extracted_fields=llm_result.extracted_fields,
                ocr_raw_text_front=raw_text if request.side == "front" else None,
                ocr_raw_text_back=raw_text if request.side == "back" else None,
                extraction_time_ms=llm_result.metadata.extraction_time_ms,
                token_input=llm_result.token_input,
                token_output=llm_result.token_output,
                cost_inr=llm_result.cost_inr,
                status=llm_result.status,
            )
            repo.update(record, llm_extraction_id=llm_record.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store verification record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

    # =========================================================================
    # Step 8: Build response
    # =========================================================================
    combined_score = 0.3 * quality_a["overall_score"] + 0.7 * completeness_score

    if llm_result.status == "success" and len(missing_fields) <= 1:
        status = "accepted"
        message = "Document accepted"
        structured_data = llm_result.extracted_fields
    else:
        status = "rejected"
        message = "Please re-upload a clearer photo of the document"
        structured_data = llm_result.extracted_fields if llm_result.status == "success" else None

    rejection_reasons = quality_a["feedback"].copy()
    if missing_fields:
        rejection_reasons.append(f"Missing mandatory fields: {', '.join(missing_fields)}")

    return VerifyDocumentResponse(
        request_id=validation_id,
        status=status,
        quality_score=round(combined_score, 3),
        rejection_reasons=rejection_reasons,
        message=message,
        structured_data=structured_data,
        extraction_metadata=LLMExtractionMetadata(
            llm_provider=llm_result.metadata.llm_provider,
            llm_model=llm_result.metadata.llm_model,
            extraction_time_ms=llm_result.metadata.extraction_time_ms,
            prompt_version=llm_result.metadata.prompt_version,
            ocr_engine="google_vision",
        ) if llm_result.status == "success" else None,
    )


# =============================================================================
# Status + Admin endpoints
# =============================================================================

@verify_router.get("/verify/document/{validation_id}/status")
def get_verification_status(validation_id: str, db: Session = Depends(get_db)):
    """Look up verification status."""
    repo = DocumentValidationRepository(db)
    record = repo.get_by_id(validation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Validation record not found")
    return {
        "validation_id": record.id,
        "doc_type": record.doc_type,
        "overall_status": record.overall_status,
        "verification_status": record.verification_status,
        "approval_method": record.approval_method,
        "govt_match_score": record.govt_match_score,
        "requires_review": record.requires_review,
    }


@verify_router.get("/verify/documents")
def list_documents(
    driver_id: str = None,
    doc_type: str = None,
    status: str = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List documents for review — filter by driver_id, doc_type, status."""
    q = db.query(DocumentValidation)
    if driver_id:
        q = q.filter(DocumentValidation.driver_id == driver_id)
    if doc_type:
        q = q.filter(DocumentValidation.doc_type == doc_type)
    if status:
        q = q.filter(DocumentValidation.overall_status == status)
    records = q.order_by(DocumentValidation.created_at.desc()).limit(limit).all()
    return [
        {
            "validation_id": r.id,
            "driver_id": r.driver_id,
            "doc_type": r.doc_type,
            "doc_number": r.doc_number,
            "overall_status": r.overall_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "front_url": r.front_url,
            "back_url": r.back_url,
        }
        for r in records
    ]


@verify_router.get("/verify/document/{validation_id}/review")
def get_document_review(validation_id: str, db: Session = Depends(get_db)):
    """Full review view: LLM extracted fields, govt data, images, quality scores."""
    repo = DocumentValidationRepository(db)
    record = repo.get_by_id(validation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Validation record not found")

    # LLM extraction
    llm_repo = LLMExtractionRepository(db)
    llm_record = llm_repo.get_by_validation_id(validation_id)

    # Govt verification (if exists)
    govt_repo = GovtVerificationRepository(db)
    govt_record = govt_repo.get_by_validation_id(validation_id)

    # Field comparisons (if exist)
    comp_repo = FieldComparisonRepository(db)
    comparisons = comp_repo.get_by_validation_id(validation_id)

    return {
        "validation_id": record.id,
        "doc_type": record.doc_type,
        "doc_number": record.doc_number,
        "driver_id": record.driver_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "overall_status": record.overall_status,
        "verification_status": record.verification_status,
        "approval_method": record.approval_method,

        # Images
        "images": {
            "front_url": record.front_url,
            "back_url": record.back_url,
        },

        # Quality scores
        "quality": {
            "front_score": record.front_quality_score,
            "back_score": record.back_quality_score,
            "front_issues": record.front_issues,
            "back_issues": record.back_issues,
        },

        # LLM extracted fields (structured data)
        "llm_extraction": {
            "extracted_fields": llm_record.extracted_fields if llm_record else None,
            "model": f"{llm_record.model_provider}/{llm_record.model_name}" if llm_record else None,
            "confidence": llm_record.llm_confidence if llm_record else None,
            "cost_inr": float(llm_record.cost_inr) if llm_record and llm_record.cost_inr else None,
            "extraction_time_ms": llm_record.extraction_time_ms if llm_record else None,
        },

        # OCR raw text
        "ocr_raw_text": {
            "front": record.ocr_raw_text_front,
            "back": record.ocr_raw_text_back,
        },

        # Govt verification (RTO / govt portal data)
        "govt_verification": {
            "status": govt_record.status if govt_record else None,
            "govt_fields": govt_record.govt_fields if govt_record else None,
            "match_score": record.govt_match_score,
        } if govt_record else None,

        # Field-by-field comparison (LLM vs Govt)
        "field_comparisons": [
            {
                "field": c.field_name,
                "llm_value": c.llm_value,
                "govt_value": c.govt_value,
                "is_match": c.is_match,
                "similarity": c.similarity_score,
            }
            for c in comparisons
        ] if comparisons else None,

        # Review status
        "review": {
            "requires_review": record.requires_review,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
            "reviewed_by": record.reviewed_by,
            "review_notes": record.review_notes,
        },
    }


def require_admin(x_admin_key: str = Header(...)):
    if not settings.ADMIN_API_KEY or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@verify_router.post("/admin/retry-stuck")
def retry_stuck(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Find records stuck in verification_status='in_progress' for >10 min and re-trigger."""
    stuck_threshold = datetime.utcnow() - timedelta(minutes=10)
    repo = DocumentValidationRepository(db)

    records = (
        db.query(DocumentValidation)
        .filter(
            DocumentValidation.verification_status == "in_progress",
            DocumentValidation.updated_at < stuck_threshold,
        )
        .all()
    )

    stuck_records = []
    for record in records:
        record.verification_status = "pending"
        record.updated_at = datetime.utcnow()
        stuck_records.append({"id": record.id, "doc_type": record.doc_type})

    db.commit()
    return {"success": True, "retried": len(stuck_records), "records": stuck_records}
