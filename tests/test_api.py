# tests/test_api.py
import base64
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image


def _make_test_image_base64():
    img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
    pil_img = Image.fromarray(img)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture
def mock_extraction_result():
    return {
        "success": True,
        "document_type": "receipt",
        "confidence": 0.92,
        "fields": [{"label": "vendor", "value": "Big Bazaar"}],
        "raw_text": "raw text",
        "processing_time_ms": 100,
    }


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_engines_endpoint(client):
    response = client.get("/engines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["engines"], list)


def test_extract_endpoint(client, mock_extraction_result):
    with patch("app.api.routes.extraction_service") as mock_service:
        mock_service.extract.return_value = mock_extraction_result
        response = client.post(
            "/extract",
            json={"image": _make_test_image_base64()},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["document_type"] == "receipt"


def test_extract_receipt_endpoint(client, mock_extraction_result):
    with patch("app.api.routes.extraction_service") as mock_service:
        mock_service.extract.return_value = mock_extraction_result
        response = client.post(
            "/extract/receipt",
            json={"image": _make_test_image_base64()},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_extract_no_image_returns_422(client):
    response = client.post("/extract", json={})
    assert response.status_code == 422


def test_extract_with_invalid_engine(client):
    with patch("app.api.routes.extraction_service") as mock_service:
        mock_service.extract.side_effect = ValueError("Unknown engine: fake")
        response = client.post(
            "/extract",
            json={"image": _make_test_image_base64(), "engine": "fake"},
        )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
