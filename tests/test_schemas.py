import pytest
from pydantic import ValidationError
from app.api.schemas import ExtractionRequest, ExtractionResponse, FieldResult


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
