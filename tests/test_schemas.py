import pytest
from pydantic import ValidationError
from app.api.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    FieldResult,
    ImageQuality,
    DocumentAuthenticity,
)


def test_extraction_request_with_base64():
    req = ExtractionRequest(image="base64data")
    assert req.image == "base64data"
    assert req.engine == "auto"


def test_extraction_request_with_url():
    req = ExtractionRequest(image_url="https://example.com/img.jpg")
    assert req.image_url == "https://example.com/img.jpg"


def test_extraction_request_requires_image_or_url():
    with pytest.raises(ValidationError):
        ExtractionRequest()


def test_extraction_response():
    resp = ExtractionResponse(
        success=True,
        document_type="receipt",
        confidence=0.92,
        fields=[FieldResult(label="vendor", value="Big Bazaar")],
        raw_text="raw",
        processing_time_ms=100,
    )
    assert resp.success is True
    assert resp.fields[0].label == "vendor"


# --- Side validation tests ---


def test_extraction_request_side_front():
    req = ExtractionRequest(image="base64data", side="front")
    assert req.side == "front"


def test_extraction_request_side_back():
    req = ExtractionRequest(image="base64data", side="back")
    assert req.side == "back"


def test_extraction_request_side_none():
    req = ExtractionRequest(image="base64data", side=None)
    assert req.side is None


def test_extraction_request_side_default_is_none():
    req = ExtractionRequest(image="base64data")
    assert req.side is None


def test_extraction_request_invalid_side():
    with pytest.raises(ValidationError) as exc_info:
        ExtractionRequest(image="base64data", side="left")
    assert "side" in str(exc_info.value)


# --- ImageQuality model tests ---


def test_image_quality_model():
    quality = ImageQuality(
        overall_score=0.85,
        is_acceptable=True,
        feedback=["Image is clear"],
        blur_score=0.9,
        brightness_score=0.8,
        resolution_score=1.0,
        completeness_score=0.7,
        missing_mandatory=["fuel_type"],
    )
    assert quality.overall_score == 0.85
    assert quality.is_acceptable is True
    assert quality.blur_score == 0.9
    assert len(quality.missing_mandatory) == 1


def test_image_quality_defaults():
    quality = ImageQuality(
        overall_score=0.5,
        is_acceptable=False,
    )
    assert quality.feedback == []
    assert quality.blur_score == 0.0
    assert quality.missing_mandatory == []


# --- DocumentAuthenticity model tests ---


def test_document_authenticity_model():
    auth = DocumentAuthenticity(
        is_authentic=True,
        confidence=0.92,
        structural={"has_header": True, "has_valid_reg_format": True},
        visual={"aspect_ratio_score": 0.95},
    )
    assert auth.is_authentic is True
    assert auth.confidence == 0.92
    assert auth.structural["has_header"] is True


def test_document_authenticity_defaults():
    auth = DocumentAuthenticity(
        is_authentic=False,
        confidence=0.1,
    )
    assert auth.structural == {}
    assert auth.visual == {}


# --- ExtractionResponse with new optional fields ---


def test_extraction_response_with_quality_and_authenticity():
    resp = ExtractionResponse(
        success=True,
        document_type="rc_book",
        confidence=0.90,
        fields=[FieldResult(label="registration_number", value="KA01AB1234")],
        raw_text="raw",
        processing_time_ms=200,
        image_quality=ImageQuality(
            overall_score=0.85,
            is_acceptable=True,
        ),
        document_authenticity=DocumentAuthenticity(
            is_authentic=True,
            confidence=0.92,
        ),
        detected_side="front",
    )
    assert resp.image_quality is not None
    assert resp.image_quality.overall_score == 0.85
    assert resp.document_authenticity is not None
    assert resp.document_authenticity.is_authentic is True
    assert resp.detected_side == "front"


def test_extraction_response_without_quality_and_authenticity():
    resp = ExtractionResponse(
        success=True,
        document_type="receipt",
        confidence=0.90,
        fields=[],
        raw_text="raw",
        processing_time_ms=100,
    )
    assert resp.image_quality is None
    assert resp.document_authenticity is None
    assert resp.detected_side is None
