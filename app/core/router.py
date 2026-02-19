from typing import Dict, List, Optional

from app.engines.base import BaseOCREngine


class EngineRouter:
    """Routes requests to appropriate OCR engine."""

    def __init__(self):
        self.engines: Dict[str, BaseOCREngine] = {}
        self.default_engine: str = "paddle"

    def get_engine(self, name: Optional[str] = None) -> BaseOCREngine:
        engine_name = name or self.default_engine
        if engine_name not in self.engines:
            raise ValueError(f"Unknown engine: {engine_name}")
        return self.engines[engine_name]

    def list_engines(self) -> List[str]:
        return list(self.engines.keys())

    def register_engine(self, name: str, engine: BaseOCREngine):
        """Dynamically register a new engine."""
        self.engines[name] = engine
