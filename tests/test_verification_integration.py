import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def test_invalid_doc_type_returns_422():
    """Invalid image_type should be rejected by Pydantic validation."""
    from app.main import app
    client = TestClient(app)
    resp = client.post("/verify/document", json={
        "image_type": "passport",
        "side": "front",
        "driver_id": "123",
        "image_url": "https://example.com/img.jpg",
    })
    assert resp.status_code == 422


def test_invalid_side_returns_422():
    """Invalid side should be rejected."""
    from app.main import app
    client = TestClient(app)
    resp = client.post("/verify/document", json={
        "image_type": "rc_book",
        "side": "top",
        "driver_id": "123",
        "image_url": "https://example.com/img.jpg",
    })
    assert resp.status_code == 422


def test_health_endpoint():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_full_rc_pipeline_front_upload():
    """Upload front side. Verify record created and response correct."""
    from app.main import app
    client = TestClient(app)

    mock_repo_cls = MagicMock()
    mock_llm_repo_cls = MagicMock()

    with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
         patch("app.api.verify_routes.extraction_service") as mock_svc, \
         patch("app.api.verify_routes.LLMExtractor") as mock_llm_cls, \
         patch("app.api.verify_routes.get_db") as mock_get_db, \
         patch("app.api.verify_routes.REPO_MAP", {"rc_book": mock_repo_cls}), \
         patch("app.api.verify_routes.LLMExtractionRepository", mock_llm_repo_cls):

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_fetch.return_value = b"fake_image_bytes"
        mock_svc.extract.return_value = {
            "success": True,
            "fields": [{"label": "registration_number", "value": "KA01AB1234"}],
            "raw_text": "Registration No: KA01AB1234",
            "image_quality": {"overall_score": 0.9, "is_acceptable": True, "feedback": []},
            "document_authenticity": {"is_authentic": True, "confidence": 0.95},
            "processing_time_ms": 300,
            "document_type": "rc_book",
            "confidence": 0.95,
        }

        mock_llm = AsyncMock()
        mock_llm.extract.return_value = MagicMock(
            status="success",
            extracted_fields={"registration_number": "KA01AB1234", "owner_name": "RAJESH KUMAR"},
            metadata=MagicMock(
                llm_provider="anthropic", llm_model="claude-haiku-4-5-20251001",
                extraction_time_ms=800, prompt_version="v1", ocr_engine="paddleocr",
            ),
            raw_response={"text": "{}"},
            system_prompt_used="test",
            token_input=400, token_output=80, cost_inr=0.005,
        )
        mock_llm_cls.return_value = mock_llm

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.id = "int-test-001"
        mock_repo.create.return_value = mock_record
        mock_repo_cls.return_value = mock_repo

        resp = client.post("/verify/document", json={
            "image_type": "rc_book",
            "side": "front",
            "driver_id": "DRV-001",
            "image_url": "https://example.com/rc_front.jpg",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "int-test-001"
        assert data["status"] == "accepted"
        assert data["quality_score"] == 0.9
        assert data["structured_data"]["registration_number"] == "KA01AB1234"
