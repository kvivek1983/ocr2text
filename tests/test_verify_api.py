import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def _mock_ocr_result():
    return {
        "success": True,
        "fields": [{"label": "registration_number", "value": "MH47BL1775"}],
        "raw_text": "Registration No: MH47BL1775",
        "image_quality": {"overall_score": 0.85, "is_acceptable": True, "feedback": []},
        "document_authenticity": {"is_authentic": True, "confidence": 0.9},
        "processing_time_ms": 500,
        "document_type": "rc_book",
        "confidence": 0.9,
    }


def _mock_llm_result():
    return MagicMock(
        status="success",
        extracted_fields={"registration_number": "MH47BL1775", "owner_name": "TEST"},
        metadata=MagicMock(
            llm_provider="anthropic", llm_model="claude-haiku-4-5-20251001",
            extraction_time_ms=1200, prompt_version="v1", ocr_engine="paddleocr",
        ),
        raw_response={"text": "{}"},
        system_prompt_used="test prompt",
        token_input=500, token_output=100, cost_inr=0.01,
    )


def _setup_mocks(mock_repo, mock_record=None):
    """Configure a mock repo instance with common defaults."""
    if mock_record is None:
        mock_record = MagicMock()
        mock_record.id = "test-validation-id"
    mock_repo.create.return_value = mock_record
    mock_repo.get_pending_back_for_driver.return_value = None
    return mock_record


def _get_app_and_client():
    from app.main import app
    from app.api.routes import get_db
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    return app, client, mock_db


def _cleanup_overrides(app):
    app.dependency_overrides.clear()


def _make_repo_class_mock(mock_repo_instance):
    """Create a callable mock that returns mock_repo_instance when called with any args."""
    return lambda *args, **kwargs: mock_repo_instance


def _post_verify(client, mock_repo, side="front", image_type="rc_book"):
    """Helper to post to /verify/document with standard mocks around REPO_MAP."""
    mock_repo_factory = _make_repo_class_mock(mock_repo)
    repo_map = {
        "rc_book": mock_repo_factory,
        "driving_license": mock_repo_factory,
        "aadhaar": mock_repo_factory,
    }
    with patch("app.api.verify_routes.REPO_MAP", repo_map), \
         patch("app.api.verify_routes.LLMExtractionRepository"):
        return client.post("/verify/document", json={
            "image_type": image_type,
            "side": side,
            "driver_id": "196274",
            "image_url": "https://example.com/img.jpg",
        })


def test_verify_document_front_upload():
    """POST /verify/document with side=front creates record and returns response."""
    app, client, mock_db = _get_app_and_client()
    try:
        with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
             patch("app.api.verify_routes.extraction_service") as mock_svc, \
             patch("app.api.verify_routes._llm_extractor") as mock_llm:

            mock_fetch.return_value = b"fake_image_bytes"
            mock_svc.extract.return_value = _mock_ocr_result()
            mock_llm.extract = AsyncMock(return_value=_mock_llm_result())

            mock_repo = MagicMock()
            _setup_mocks(mock_repo)
            resp = _post_verify(client, mock_repo, side="front")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("accepted", "rejected")
        assert "request_id" in data
    finally:
        _cleanup_overrides(app)


def test_front_upload_duplicate_rejected_c3():
    """C3: If front already uploaded (pending_back exists), reject duplicate front."""
    app, client, mock_db = _get_app_and_client()
    try:
        with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
             patch("app.api.verify_routes.extraction_service") as mock_svc, \
             patch("app.api.verify_routes._llm_extractor") as mock_llm:

            mock_fetch.return_value = b"fake_image_bytes"
            mock_svc.extract.return_value = _mock_ocr_result()
            mock_llm.extract = AsyncMock(return_value=_mock_llm_result())

            mock_repo = MagicMock()
            mock_repo.get_pending_back_for_driver.return_value = MagicMock(id="existing-id")
            resp = _post_verify(client, mock_repo, side="front")

        assert resp.status_code == 400
        assert "back side" in resp.json()["detail"].lower()
    finally:
        _cleanup_overrides(app)


def test_back_upload_without_front_rejected_c4():
    """C4: Back upload without a pending_back record should be rejected."""
    app, client, mock_db = _get_app_and_client()
    try:
        with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
             patch("app.api.verify_routes.extraction_service") as mock_svc, \
             patch("app.api.verify_routes._llm_extractor") as mock_llm:

            mock_fetch.return_value = b"fake_image_bytes"
            mock_svc.extract.return_value = _mock_ocr_result()
            mock_llm.extract = AsyncMock(return_value=_mock_llm_result())

            mock_repo = MagicMock()
            mock_repo.get_pending_back_for_driver.return_value = None
            resp = _post_verify(client, mock_repo, side="back")

        assert resp.status_code == 400
        assert "front side" in resp.json()["detail"].lower()
    finally:
        _cleanup_overrides(app)


def test_db_exception_returns_500():
    """C2: DB exceptions now raise 500 instead of being silently swallowed."""
    app, client, mock_db = _get_app_and_client()
    try:
        with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
             patch("app.api.verify_routes.extraction_service") as mock_svc, \
             patch("app.api.verify_routes._llm_extractor") as mock_llm:

            mock_fetch.return_value = b"fake_image_bytes"
            mock_svc.extract.return_value = _mock_ocr_result()
            mock_llm.extract = AsyncMock(return_value=_mock_llm_result())

            mock_repo = MagicMock()
            mock_repo.get_pending_back_for_driver.return_value = None
            mock_repo.create.side_effect = RuntimeError("DB connection lost")
            resp = _post_verify(client, mock_repo, side="front")

        assert resp.status_code == 500
        assert "Failed to process document" in resp.json()["detail"]
    finally:
        _cleanup_overrides(app)


def test_status_endpoint_returns_404_for_missing():
    app, client, mock_db = _get_app_and_client()
    try:
        with patch("app.api.verify_routes.RCValidationRepository") as mock_rc, \
             patch("app.api.verify_routes.DLValidationRepository") as mock_dl, \
             patch("app.api.verify_routes.AadhaarValidationRepository") as mock_aa:
            for m in [mock_rc, mock_dl, mock_aa]:
                m.return_value.get_by_id.return_value = None
            resp = client.get("/verify/document/nonexistent-id/status")
        assert resp.status_code == 404
    finally:
        _cleanup_overrides(app)


def test_admin_endpoint_requires_api_key():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/admin/retry-stuck")
    assert resp.status_code in (401, 403, 422)
