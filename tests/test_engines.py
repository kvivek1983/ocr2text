import pytest
from app.engines.base import BaseOCREngine


def test_base_engine_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseOCREngine()


def test_base_engine_requires_extract_and_get_name():
    class IncompleteEngine(BaseOCREngine):
        def get_name(self):
            return "incomplete"

    with pytest.raises(TypeError):
        IncompleteEngine()


def test_concrete_engine_works():
    class FakeEngine(BaseOCREngine):
        def extract(self, image: bytes) -> dict:
            return {
                "raw_text": "hello",
                "confidence": 0.99,
                "blocks": [],
                "processing_time_ms": 10,
            }

        def get_name(self) -> str:
            return "fake"

    engine = FakeEngine()
    assert engine.get_name() == "fake"
    result = engine.extract(b"fake_image")
    assert result["raw_text"] == "hello"
    assert result["confidence"] == 0.99
    assert engine.health_check() is True


import io
from unittest.mock import patch, MagicMock
from app.engines.paddle_engine import PaddleEngine


def test_paddle_engine_get_name():
    with patch("app.engines.paddle_engine.PaddleOCR"):
        engine = PaddleEngine()
    assert engine.get_name() == "paddle"


def test_paddle_engine_extract():
    mock_ocr_instance = MagicMock()
    # PaddleOCR returns: list of pages, each page is list of lines,
    # each line is (bbox, (text, confidence))
    mock_ocr_instance.ocr.return_value = [
        [
            ([[0, 0], [100, 0], [100, 30], [0, 30]], ("Hello World", 0.95)),
            ([[0, 40], [100, 40], [100, 70], [0, 70]], ("Total: 500", 0.88)),
        ]
    ]

    with patch("app.engines.paddle_engine.PaddleOCR", return_value=mock_ocr_instance), \
         patch("app.engines.paddle_engine.Image.open"), \
         patch("app.engines.paddle_engine.np.array"):
        engine = PaddleEngine()
        result = engine.extract(b"fake_image_bytes")

    assert "Hello World" in result["raw_text"]
    assert "Total: 500" in result["raw_text"]
    assert result["confidence"] == pytest.approx(0.915, abs=0.01)
    assert len(result["blocks"]) == 2
    assert result["blocks"][0]["text"] == "Hello World"
    assert result["blocks"][0]["confidence"] == 0.95
    assert isinstance(result["processing_time_ms"], int)


def test_paddle_engine_extract_empty_result():
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [None]

    with patch("app.engines.paddle_engine.PaddleOCR", return_value=mock_ocr_instance), \
         patch("app.engines.paddle_engine.Image.open"), \
         patch("app.engines.paddle_engine.np.array"):
        engine = PaddleEngine()
        result = engine.extract(b"fake_image_bytes")

    assert result["raw_text"] == ""
    assert result["confidence"] == 0.0
    assert result["blocks"] == []
