# tests/test_google_engine.py
import pytest
from unittest.mock import patch, MagicMock
from app.engines.google_engine import GoogleVisionEngine


def test_google_engine_get_name():
    with patch("app.engines.google_engine.vision"):
        engine = GoogleVisionEngine()
    assert engine.get_name() == "google"


def test_google_engine_extract():
    mock_client = MagicMock()

    mock_text_annotation = MagicMock()
    mock_text_annotation.description = "Hello World\nTotal: 500\n"

    mock_block = MagicMock()
    mock_block.confidence = 0.95
    mock_word1 = MagicMock()
    mock_word1.symbols = [MagicMock(text="Hello")]
    mock_paragraph = MagicMock()
    mock_paragraph.words = [mock_word1]
    mock_block.paragraphs = [mock_paragraph]

    mock_page = MagicMock()
    mock_page.blocks = [mock_block]

    mock_full_text = MagicMock()
    mock_full_text.pages = [mock_page]

    mock_response = MagicMock()
    mock_response.text_annotations = [mock_text_annotation]
    mock_response.full_text_annotation = mock_full_text
    mock_response.error.message = ""

    mock_client.text_detection.return_value = mock_response

    with patch("app.engines.google_engine.vision") as mock_vision:
        mock_vision.ImageAnnotatorClient.return_value = mock_client
        mock_vision.Image.return_value = MagicMock()
        engine = GoogleVisionEngine()
        result = engine.extract(b"fake_image_bytes")

    assert "Hello World" in result["raw_text"]
    assert result["confidence"] == pytest.approx(0.95, abs=0.01)
    assert isinstance(result["processing_time_ms"], int)


def test_google_engine_extract_empty():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text_annotations = []
    mock_response.full_text_annotation = None
    mock_response.error.message = ""
    mock_client.text_detection.return_value = mock_response

    with patch("app.engines.google_engine.vision") as mock_vision:
        mock_vision.ImageAnnotatorClient.return_value = mock_client
        mock_vision.Image.return_value = MagicMock()
        engine = GoogleVisionEngine()
        result = engine.extract(b"fake_image_bytes")

    assert result["raw_text"] == ""
    assert result["confidence"] == 0.0
