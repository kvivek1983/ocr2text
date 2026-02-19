import pytest
from app.core.router import EngineRouter
from app.engines.base import BaseOCREngine


class MockEngine(BaseOCREngine):
    def __init__(self, name):
        self._name = name

    def extract(self, image: bytes) -> dict:
        return {"raw_text": "mock", "confidence": 1.0, "blocks": [], "processing_time_ms": 0}

    def get_name(self) -> str:
        return self._name


def test_router_get_default_engine():
    router = EngineRouter()
    router.engines = {"paddle": MockEngine("paddle"), "google": MockEngine("google")}
    router.default_engine = "paddle"

    engine = router.get_engine()
    assert engine.get_name() == "paddle"


def test_router_get_named_engine():
    router = EngineRouter()
    router.engines = {"paddle": MockEngine("paddle"), "google": MockEngine("google")}

    engine = router.get_engine("google")
    assert engine.get_name() == "google"


def test_router_unknown_engine_raises():
    router = EngineRouter()
    router.engines = {"paddle": MockEngine("paddle")}

    with pytest.raises(ValueError, match="Unknown engine"):
        router.get_engine("nonexistent")


def test_router_list_engines():
    router = EngineRouter()
    router.engines = {"paddle": MockEngine("paddle"), "google": MockEngine("google")}

    engines = router.list_engines()
    assert "paddle" in engines
    assert "google" in engines


def test_router_register_engine():
    router = EngineRouter()
    router.engines = {}

    new_engine = MockEngine("aws")
    router.register_engine("aws", new_engine)
    assert "aws" in router.engines
    assert router.get_engine("aws").get_name() == "aws"
