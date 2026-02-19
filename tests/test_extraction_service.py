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
