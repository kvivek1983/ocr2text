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
