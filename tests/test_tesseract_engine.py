# tests/test_tesseract_engine.py
import pytest
from unittest.mock import patch, MagicMock
from app.engines.tesseract_engine import TesseractEngine


def test_tesseract_engine_get_name():
    engine = TesseractEngine()
    assert engine.get_name() == "tesseract"


def test_tesseract_engine_extract():
    mock_data = {
        "text": ["Hello World", "Total: 500", ""],
        "conf": [95, 88, -1],
        "left": [0, 0, 0],
        "top": [0, 40, 0],
        "width": [100, 100, 0],
        "height": [30, 30, 0],
    }

    with patch("app.engines.tesseract_engine.pytesseract") as mock_tess, \
         patch("app.engines.tesseract_engine.Image.open") as mock_open:
        mock_tess.image_to_data.return_value = mock_data
        mock_tess.image_to_string.return_value = "Hello World\nTotal: 500\n"
        engine = TesseractEngine()
        result = engine.extract(b"fake_image_bytes")

    assert "Hello World" in result["raw_text"]
    assert "Total: 500" in result["raw_text"]
    assert result["confidence"] == pytest.approx(0.915, abs=0.01)
    assert len(result["blocks"]) == 2
    assert result["blocks"][0]["text"] == "Hello World"
    assert isinstance(result["processing_time_ms"], int)


def test_tesseract_engine_extract_empty():
    mock_data = {
        "text": [""],
        "conf": [-1],
        "left": [0],
        "top": [0],
        "width": [0],
        "height": [0],
    }

    with patch("app.engines.tesseract_engine.pytesseract") as mock_tess, \
         patch("app.engines.tesseract_engine.Image.open") as mock_open:
        mock_tess.image_to_data.return_value = mock_data
        mock_tess.image_to_string.return_value = ""
        engine = TesseractEngine()
        result = engine.extract(b"fake_image_bytes")

    assert result["raw_text"] == ""
    assert result["confidence"] == 0.0
    assert result["blocks"] == []
