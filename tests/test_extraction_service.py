# tests/test_extraction_service.py
from unittest.mock import MagicMock, patch
from app.core.extraction_service import ExtractionService


def test_extraction_service_single_engine():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Vendor: Big Bazaar\nTotal: 1234\nDate: 15/01/2024\nBill No: B-123\nSubtotal: 1100\nGST: 134",
        "confidence": 0.92,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = ExtractionService(
        router=mock_router,
        enable_preprocessing=False,
    )

    result = service.extract(image_bytes=b"fake", engine="paddle")

    assert result["success"] is True
    assert result["document_type"] is not None
    assert result["confidence"] == 0.92
    assert isinstance(result["fields"], list)
    assert result["raw_text"] is not None
    # Non-rc_book should not have quality/authenticity
    assert "image_quality" not in result
    assert "document_authenticity" not in result


def test_extraction_service_with_document_type_hint():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Some text",
        "confidence": 0.85,
        "blocks": [],
        "processing_time_ms": 50,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = ExtractionService(
        router=mock_router,
        enable_preprocessing=False,
    )

    result = service.extract(
        image_bytes=b"fake",
        engine="paddle",
        document_type="receipt",
    )

    assert result["success"] is True
    assert result["document_type"] == "receipt"
    # Non-rc_book should not have quality/authenticity
    assert "image_quality" not in result
    assert "document_authenticity" not in result


def test_extraction_service_rc_book_with_quality():
    """RC book extraction should include quality and authenticity."""
    import numpy as np
    import cv2

    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: RAJESH KUMAR\nFuel Type: Petrol\nVehicle Make: MARUTI\nDate of Registration: 15/03/2020",
        "confidence": 0.90,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = ExtractionService(
        router=mock_router,
        enable_preprocessing=False,
    )

    # Create valid image bytes that cv2.imdecode can handle
    img = np.full((500, 800, 3), 128, dtype=np.uint8)
    _, img_encoded = cv2.imencode('.jpg', img)
    img_bytes = img_encoded.tobytes()

    result = service.extract(
        image_bytes=img_bytes,
        engine="paddle",
        document_type="rc_book",
        side="front",
    )

    assert result["success"] is True
    assert result["document_type"] == "rc_book"
    assert "image_quality" in result
    assert "document_authenticity" in result
    assert "detected_side" in result
    assert result["detected_side"] == "front"
