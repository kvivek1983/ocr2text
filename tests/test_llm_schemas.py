from app.llm.schemas import (
    RCExtractionFields, DLExtractionFields, AadhaarExtractionFields,
    LLMExtractionResult, LLMExtractionMetadata,
    VerifyDocumentRequest, VerifyDocumentResponse,
)

def test_rc_extraction_fields_from_dict():
    fields = RCExtractionFields(registration_number="MH47BL1775", owner_name="TEST")
    assert fields.registration_number == "MH47BL1775"
    assert fields.chassis_number is None

def test_verify_document_request_validation():
    req = VerifyDocumentRequest(image_type="rc_book", side="front", driver_id="123", image_url="https://example.com/img.jpg")
    assert req.image_type == "rc_book"

def test_verify_document_request_invalid_type():
    import pytest
    with pytest.raises(ValueError):
        VerifyDocumentRequest(image_type="passport", side="front", driver_id="123", image_url="https://example.com/img.jpg")

def test_llm_extraction_result():
    r = LLMExtractionResult(
        extracted_fields={"reg": "MH47"},
        metadata=LLMExtractionMetadata(llm_provider="anthropic", llm_model="haiku", extraction_time_ms=100, prompt_version="v1"),
        raw_response={"text": "{}"},
        system_prompt_used="test",
    )
    assert r.status == "success"
    assert r.token_input == 0
