# app/api/routes.py
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    FieldResult,
)
from app.config import settings
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
    )

    return ExtractionResponse(
        success=result["success"],
        document_type=result["document_type"],
        confidence=result["confidence"],
        fields=[FieldResult(**f) for f in result["fields"]],
        raw_text=result["raw_text"],
        processing_time_ms=result["processing_time_ms"],
    )


def _make_type_endpoint(doc_type: str):
    def endpoint(request: ExtractionRequest):
        image_bytes = _get_image_bytes(request)
        engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

        result = extraction_service.extract(
            image_bytes=image_bytes,
            engine=engine,
            document_type=doc_type,
            include_raw_text=request.include_raw_text,
        )

        return ExtractionResponse(
            success=result["success"],
            document_type=result["document_type"],
            confidence=result["confidence"],
            fields=[FieldResult(**f) for f in result["fields"]],
            raw_text=result["raw_text"],
            processing_time_ms=result["processing_time_ms"],
        )

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
