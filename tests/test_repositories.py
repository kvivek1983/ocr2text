import pytest
from unittest.mock import MagicMock
from app.storage.repository import (
    DLValidationRepository, AadhaarValidationRepository,
    LLMExtractionRepository, GovtVerificationRepository,
    FieldComparisonRepository, GovtResellerRepository,
    DriverOnboardingRepository,
)


def test_dl_validation_repo_has_get_pending_back():
    repo = DLValidationRepository(session=MagicMock())
    assert hasattr(repo, "get_pending_back_for_driver")
    assert hasattr(repo, "create")
    assert hasattr(repo, "update")


def test_aadhaar_validation_repo_has_methods():
    repo = AadhaarValidationRepository(session=MagicMock())
    assert hasattr(repo, "get_pending_back_for_driver")


def test_llm_extraction_repo_has_create():
    repo = LLMExtractionRepository(session=MagicMock(), doc_type="rc_book")
    assert hasattr(repo, "create")
    assert hasattr(repo, "get_by_validation_id")


def test_govt_verification_repo_has_methods():
    repo = GovtVerificationRepository(session=MagicMock(), doc_type="rc_book")
    assert hasattr(repo, "create")
    assert hasattr(repo, "get_by_validation_id")


def test_field_comparison_repo_has_bulk_create():
    repo = FieldComparisonRepository(session=MagicMock(), doc_type="rc_book")
    assert hasattr(repo, "bulk_create")


def test_govt_reseller_repo_has_get_active():
    repo = GovtResellerRepository(session=MagicMock())
    assert hasattr(repo, "get_active_ordered")
    assert hasattr(repo, "update_circuit_state")


def test_driver_onboarding_repo_has_upsert():
    repo = DriverOnboardingRepository(session=MagicMock())
    assert hasattr(repo, "upsert")
    assert hasattr(repo, "get_by_driver_id")
