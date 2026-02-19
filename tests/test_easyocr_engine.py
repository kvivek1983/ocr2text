# tests/test_easyocr_engine.py
import pytest
from unittest.mock import patch, MagicMock
from app.engines.easyocr_engine import EasyOCREngine


def test_easyocr_engine_get_name():
    with patch("app.engines.easyocr_engine.easyocr"):
        engine = EasyOCREngine()
    assert engine.get_name() == "easyocr"


def test_easyocr_engine_extract():
    mock_reader = MagicMock()
    # EasyOCR returns: list of (bbox, text, confidence)
    mock_reader.readtext.return_value = [
        ([[0, 0], [100, 0], [100, 30], [0, 30]], "Hello World", 0.95),
        ([[0, 40], [100, 40], [100, 70], [0, 70]], "Total: 500", 0.88),
    ]

    with patch("app.engines.easyocr_engine.easyocr") as mock_easyocr, \
         patch("app.engines.easyocr_engine.Image") as mock_image, \
         patch("app.engines.easyocr_engine.np") as mock_np:
        mock_easyocr.Reader.return_value = mock_reader
        mock_np.array.return_value = MagicMock()  # fake numpy array
        engine = EasyOCREngine()
        result = engine.extract(b"fake_image_bytes")

    assert "Hello World" in result["raw_text"]
    assert "Total: 500" in result["raw_text"]
    assert result["confidence"] == pytest.approx(0.915, abs=0.01)
    assert len(result["blocks"]) == 2
    assert result["blocks"][0]["text"] == "Hello World"
    assert result["blocks"][0]["confidence"] == 0.95
    assert isinstance(result["processing_time_ms"], int)


def test_easyocr_engine_extract_empty():
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = []

    with patch("app.engines.easyocr_engine.easyocr") as mock_easyocr, \
         patch("app.engines.easyocr_engine.Image") as mock_image, \
         patch("app.engines.easyocr_engine.np") as mock_np:
        mock_easyocr.Reader.return_value = mock_reader
        mock_np.array.return_value = MagicMock()
        engine = EasyOCREngine()
        result = engine.extract(b"fake_image_bytes")

    assert result["raw_text"] == ""
    assert result["confidence"] == 0.0
    assert result["blocks"] == []
