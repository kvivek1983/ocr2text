# app/api/routes.py
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ComparisonResponse,
    ExtractionRequest,
    ExtractionResponse,
    FieldResult,
    ImageQuality,
    DocumentAuthenticity,
)
from app.config import settings
from app.comparison.comparator import Comparator
from app.core.extraction_service import ExtractionService
from app.core.router import EngineRouter
from app.utils.image_utils import decode_base64_image, fetch_image_url

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
