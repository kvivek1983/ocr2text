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
def mock_rc_extraction_result():
    return {
        "success": True,
        "document_type": "rc_book",
        "confidence": 0.90,
        "fields": [{"label": "registration_number", "value": "KA01AB1234"}],
        "raw_text": "raw text",
        "processing_time_ms": 200,
        "detected_side": "front",
        "image_quality": {
            "overall_score": 0.85,
            "is_acceptable": True,
            "feedback": [],
            "blur_score": 0.9,
            "brightness_score": 0.8,
            "resolution_score": 1.0,
            "completeness_score": 0.7,
            "missing_mandatory": [],
        },
        "document_authenticity": {
            "is_authentic": True,
            "confidence": 0.92,
            "structural": {"has_header": True},
            "visual": {"aspect_ratio_score": 0.95},
        },
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
    assert data["image_quality"] is None
    assert data["document_authenticity"] is None
    assert data["detected_side"] is None


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


def test_extract_rc_book_endpoint(client, mock_rc_extraction_result):
    with patch("app.api.routes.extraction_service") as mock_service:
        mock_service.extract.return_value = mock_rc_extraction_result
        response = client.post(
            "/extract/rc-book",
            json={"image": _make_test_image_base64(), "side": "front"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["document_type"] == "rc_book"
    assert data["image_quality"] is not None
    assert data["image_quality"]["overall_score"] == 0.85
    assert data["image_quality"]["is_acceptable"] is True
    assert data["document_authenticity"] is not None
    assert data["document_authenticity"]["is_authentic"] is True
    assert data["detected_side"] == "front"


def test_extract_with_side_parameter(client, mock_rc_extraction_result):
    with patch("app.api.routes.extraction_service") as mock_service:
        mock_service.extract.return_value = mock_rc_extraction_result
        response = client.post(
            "/extract",
            json={
                "image": _make_test_image_base64(),
                "document_type": "rc_book",
                "side": "front",
            },
        )

    assert response.status_code == 200
    # Verify side was passed through to extraction service
    call_kwargs = mock_service.extract.call_args
    assert call_kwargs[1].get("side") == "front" or (
        len(call_kwargs[0]) > 4 and call_kwargs[0][4] == "front"
    )


def test_extract_with_invalid_side_returns_422(client):
    response = client.post(
        "/extract",
        json={"image": _make_test_image_base64(), "side": "top"},
    )
    assert response.status_code == 422
