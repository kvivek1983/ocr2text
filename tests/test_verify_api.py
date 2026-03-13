import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def test_verify_document_front_upload():
    """POST /verify/document with side=front creates record and returns response."""
    from app.main import app
    client = TestClient(app)

    with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
         patch("app.api.verify_routes.extraction_service") as mock_svc, \
         patch("app.api.verify_routes.LLMExtractor") as mock_llm_cls, \
         patch("app.api.verify_routes.get_db") as mock_get_db:

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_fetch.return_value = b"fake_image_bytes"
        mock_svc.extract.return_value = {
            "success": True,
            "fields": [{"label": "registration_number", "value": "MH47BL1775"}],
            "raw_text": "Registration No: MH47BL1775",
            "image_quality": {"overall_score": 0.85, "is_acceptable": True, "feedback": []},
            "document_authenticity": {"is_authentic": True, "confidence": 0.9},
            "processing_time_ms": 500,
            "document_type": "rc_book",
            "confidence": 0.9,
        }

        mock_llm = AsyncMock()
        mock_llm.extract.return_value = MagicMock(
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
        mock_llm_cls.return_value = mock_llm

        # Mock the repository create to return a record with an id
        with patch("app.api.verify_routes.RCValidationRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.id = "test-validation-id"
            mock_repo.create.return_value = mock_record
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.verify_routes.LLMExtractionRepository"):
                resp = client.post("/verify/document", json={
                    "image_type": "rc_book",
                    "side": "front",
                    "driver_id": "196274",
                    "image_url": "https://example.com/img.jpg",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("accepted", "rejected")
        assert "request_id" in data


def test_status_endpoint_returns_404_for_missing():
    from app.main import app
    client = TestClient(app)
    with patch("app.api.verify_routes.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        # Mock all three repos to return None
        with patch("app.api.verify_routes.RCValidationRepository") as mock_rc, \
             patch("app.api.verify_routes.DLValidationRepository") as mock_dl, \
             patch("app.api.verify_routes.AadhaarValidationRepository") as mock_aa:
            for m in [mock_rc, mock_dl, mock_aa]:
                m.return_value.get_by_id.return_value = None
            resp = client.get("/verify/document/nonexistent-id/status")
    assert resp.status_code == 404


def test_admin_endpoint_requires_api_key():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/admin/retry-stuck")
    assert resp.status_code in (401, 403, 422)
