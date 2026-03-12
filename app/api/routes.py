# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import (
    ComparisonResponse,
    ExtractionRequest,
    ExtractionResponse,
    FieldResult,
    ImageQuality,
    DocumentAuthenticity,
    MarkReviewedRequest,
    RCValidationRequest,
    RCValidationResponse,
    RCSideResult,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.config import settings
from app.comparison.comparator import Comparator
from app.core.extraction_service import ExtractionService
from app.core.router import EngineRouter
from app.storage.repository import RCValidationRepository
from app.utils.image_utils import decode_base64_image, fetch_image_url

# Database session factory (lazy-initialised on first use)
_SessionLocal = None


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db():
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter()

# Initialize engine router (engines registered at startup in main.py)
engine_router = EngineRouter()
extraction_service = ExtractionService(
    router=engine_router,
    enable_preprocessing=settings.ENABLE_PREPROCESSING,
)


def _get_image_bytes(request: ExtractionRequest) -> bytes:
    if request.image:
        return decode_base64_image(request.image)
    elif request.image_url:
        return fetch_image_url(request.image_url)
    raise HTTPException(status_code=400, detail="No image provided")


def _build_response(result: dict) -> ExtractionResponse:
    """Build ExtractionResponse from extraction result dict."""
    image_quality = None
    if result.get("image_quality"):
        iq = result["image_quality"]
        image_quality = ImageQuality(
            overall_score=iq["overall_score"],
            is_acceptable=iq["is_acceptable"],
            feedback=iq.get("feedback", []),
            blur_score=iq.get("blur_score", 0.0),
            brightness_score=iq.get("brightness_score", 0.0),
            resolution_score=iq.get("resolution_score", 0.0),
            completeness_score=iq.get("completeness_score", 0.0),
            missing_mandatory=iq.get("missing_mandatory", []),
        )

    document_authenticity = None
    if result.get("document_authenticity"):
        da = result["document_authenticity"]
        document_authenticity = DocumentAuthenticity(
            is_authentic=da["is_authentic"],
            confidence=da["confidence"],
            structural=da.get("structural", {}),
            visual=da.get("visual", {}),
        )

    return ExtractionResponse(
        success=result["success"],
        document_type=result["document_type"],
        confidence=result["confidence"],
        fields=[FieldResult(**f) for f in result["fields"]],
        raw_text=result["raw_text"],
        processing_time_ms=result["processing_time_ms"],
        image_quality=image_quality,
        document_authenticity=document_authenticity,
        detected_side=result.get("detected_side"),
    )


@router.get("/health")
def health():
    return {"status": "healthy", "engines": engine_router.list_engines()}


@router.get("/engines")
def list_engines():
    return {"engines": engine_router.list_engines()}


@router.post("/extract", response_model=ExtractionResponse)
def extract(request: ExtractionRequest):
    image_bytes = _get_image_bytes(request)
    engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

    result = extraction_service.extract(
        image_bytes=image_bytes,
        engine=engine,
        document_type=request.document_type,
        include_raw_text=request.include_raw_text,
        side=request.side,
    )

    return _build_response(result)


def _make_type_endpoint(doc_type: str):
    def endpoint(request: ExtractionRequest):
        image_bytes = _get_image_bytes(request)
        engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

        result = extraction_service.extract(
            image_bytes=image_bytes,
            engine=engine,
            document_type=doc_type,
            include_raw_text=request.include_raw_text,
            side=request.side,
        )

        return _build_response(result)

    return endpoint


# Expense Tracking
router.post("/extract/receipt", response_model=ExtractionResponse)(
    _make_type_endpoint("receipt")
)
router.post("/extract/invoice", response_model=ExtractionResponse)(
    _make_type_endpoint("invoice")
)

# Driver Onboarding
router.post("/extract/driving-license", response_model=ExtractionResponse)(
    _make_type_endpoint("driving_license")
)
router.post("/extract/rc-book", response_model=ExtractionResponse)(
    _make_type_endpoint("rc_book")
)
router.post("/extract/insurance", response_model=ExtractionResponse)(
    _make_type_endpoint("insurance")
)

# Fuel Tracking
router.post("/extract/petrol-receipt", response_model=ExtractionResponse)(
    _make_type_endpoint("petrol_receipt")
)
router.post("/extract/odometer", response_model=ExtractionResponse)(
    _make_type_endpoint("odometer")
)
router.post("/extract/fuel-pump-reading", response_model=ExtractionResponse)(
    _make_type_endpoint("fuel_pump_reading")
)


# RC Validation (production quality gate)
@router.post("/validate/rc-book", response_model=RCValidationResponse)
def validate_rc_book(request: RCValidationRequest, db: Session = Depends(get_db)):
    """
    Production quality gate for RC book uploads.
    Extracts both sides, assesses image quality, and stores results for review.
    """
    engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

    def _extract_side(url: str, side: str) -> dict:
        try:
            image_bytes = fetch_image_url(url)
            return extraction_service.extract(
                image_bytes=image_bytes,
                engine=engine,
                document_type="rc_book",
                include_raw_text=False,
                side=side,
            )
        except Exception as e:
            return {
                "success": False,
                "fields": [],
                "image_quality": None,
                "document_authenticity": None,
                "error": str(e),
            }

    def _build_side_result(result: dict, side: str) -> RCSideResult:
        fields = {f["label"]: f["value"] for f in result.get("fields", [])}
        iq = result.get("image_quality") or {}
        issues: list[str] = list(iq.get("feedback", []))
        if not result.get("success"):
            issues.append(f"Extraction failed: {result.get('error', 'unknown error')}")
        da = result.get("document_authenticity") or {}
        if da and not da.get("is_authentic", True):
            issues.append("Document authenticity check failed")
        return RCSideResult(
            quality_score=iq.get("overall_score", 0.0),
            is_acceptable=iq.get("is_acceptable", False) if result.get("success") else False,
            extracted_fields=fields,
            missing_mandatory=iq.get("missing_mandatory", []),
            issues=issues,
            blur_score=iq.get("blur_score", 0.0),
            brightness_score=iq.get("brightness_score", 0.0),
            resolution_score=iq.get("resolution_score", 0.0),
        )

    front_result = _extract_side(request.front_url, "front")
    back_result = _extract_side(request.back_url, "back")

    front = _build_side_result(front_result, "front")
    back = _build_side_result(back_result, "back")

    # Merge fields — front takes precedence; registration_number must match
    merged = {**back.extracted_fields, **front.extracted_fields}
    reg_number = merged.get("registration_number")

    # Determine overall status
    all_issues = [f"[FRONT] {i}" for i in front.issues] + [f"[BACK] {i}" for i in back.issues]
    front_mandatory_ok = len(front.missing_mandatory) == 0
    back_mandatory_ok = len(back.missing_mandatory) == 0

    if not front.is_acceptable or not back.is_acceptable:
        overall_status = "rejected"
        requires_review = True
        message = "One or more images failed quality check. Please re-upload clearer photos."
    elif front_mandatory_ok and back_mandatory_ok:
        overall_status = "accepted"
        requires_review = False
        message = "RC book images accepted. All mandatory fields extracted successfully."
    else:
        overall_status = "needs_review"
        requires_review = True
        missing = front.missing_mandatory + back.missing_mandatory
        message = f"Extraction incomplete. Missing fields: {', '.join(missing)}."

    # Persist to DB (best-effort — don't fail the API if DB is unavailable)
    validation_id = ""
    try:
        repo = RCValidationRepository(db)
        record = repo.create(
            driver_id=request.driver_id,
            front_url=request.front_url,
            back_url=request.back_url,
            overall_status=overall_status,
            front_quality_score=front.quality_score,
            back_quality_score=back.quality_score,
            front_issues=front.issues,
            back_issues=back.issues,
            front_fields=front.extracted_fields,
            back_fields=back.extracted_fields,
            merged_fields=merged,
            registration_number=reg_number,
            requires_review=requires_review,
        )
        validation_id = record.id
    except Exception:
        pass  # DB unavailable — still return extraction result

    return RCValidationResponse(
        success=True,
        validation_id=validation_id,
        overall_status=overall_status,
        requires_review=requires_review,
        front=front,
        back=back,
        merged_fields=merged,
        issues=all_issues,
        message=message,
    )


@router.get("/validate/rc-book/review-queue", response_model=ReviewQueueResponse)
def get_review_queue(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    db: Session = Depends(get_db),
):
    """Return RC validations that need human review."""
    repo = RCValidationRepository(db)
    items = repo.get_review_queue(limit=limit, offset=offset, status=status)
    total = repo.count_review_queue(status=status)
    return ReviewQueueResponse(
        total=total,
        items=[
            ReviewQueueItem(
                validation_id=r.id,
                created_at=r.created_at.isoformat(),
                driver_id=r.driver_id,
                overall_status=r.overall_status,
                front_url=r.front_url,
                back_url=r.back_url,
                registration_number=r.registration_number,
                front_issues=r.front_issues or [],
                back_issues=r.back_issues or [],
                merged_fields=r.merged_fields or {},
            )
            for r in items
        ],
    )


@router.patch("/validate/rc-book/{validation_id}/review")
def mark_reviewed(
    validation_id: str,
    request: MarkReviewedRequest,
    db: Session = Depends(get_db),
):
    """Mark a validation as reviewed."""
    repo = RCValidationRepository(db)
    record = repo.mark_reviewed(
        validation_id=validation_id,
        reviewed_by=request.reviewed_by,
        review_notes=request.review_notes,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Validation record not found")
    return {"success": True, "validation_id": record.id, "reviewed_at": record.reviewed_at.isoformat()}


# Comparison Endpoint
@router.post("/compare/rc-book", response_model=ComparisonResponse)
def compare_rc_book(request: ExtractionRequest):
    """Compare RC book extraction across all available engines."""
    image_bytes = _get_image_bytes(request)

    # Build engine dict from all registered engines
    engines = {
        name: engine_router.get_engine(name)
        for name in engine_router.list_engines()
    }

    if not engines:
        raise HTTPException(status_code=500, detail="No engines registered")

    comparator = Comparator(engines=engines)
    result = comparator.compare(image_bytes, document_type="rc_book", side=request.side)

    return ComparisonResponse(
        success=True,
        document_type="rc_book",
        results=result.get("engine_results", {}),
        comparison=result.get("metrics", {}),
        recommendation=result.get("recommendation"),
    )
