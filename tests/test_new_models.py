import pytest
from app.storage.models import (
    GovtReseller, RCLLMExtraction, RCGovtVerification, RCFieldComparison,
    DLValidation, DLLLMExtraction, DLGovtVerification, DLFieldComparison,
    AadhaarValidation, AadhaarLLMExtraction, AadhaarGovtVerification, AadhaarFieldComparison,
    DriverOnboardingStatus,
)


def test_govt_reseller_model_exists():
    r = GovtReseller(name="test", provider_code="test_code")
    assert r.name == "test"
    assert r.is_active is True
    assert r.circuit_state == "closed"


def test_rc_llm_extraction_model_exists():
    e = RCLLMExtraction(model_provider="anthropic", model_name="claude-haiku-4-5-20251001", extracted_fields={"registration_number": "MH47BL1775"})
    assert e.model_provider == "anthropic"
    assert e.status == "success"


def test_rc_govt_verification_model_exists():
    v = RCGovtVerification(reseller_id="abc")
    assert v.status == "pending"
    assert v.attempt_number == 1


def test_rc_field_comparison_model_exists():
    c = RCFieldComparison(validation_id="abc", field_name="owner_name", comparison_type="llm_vs_govt")
    assert c.field_name == "owner_name"


def test_dl_validation_model():
    v = DLValidation(driver_id="123")
    assert v.overall_status == "pending_back"
    assert v.verification_status == "pending"


def test_aadhaar_validation_model():
    v = AadhaarValidation(driver_id="123")
    assert v.overall_status == "pending_back"


def test_driver_onboarding_status_model():
    s = DriverOnboardingStatus(driver_id="123")
    assert s.onboarding_status == "incomplete"
