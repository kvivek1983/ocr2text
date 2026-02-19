from typing import Any, Dict
from app.engines.base import BaseOCREngine
from app.comparison.metrics import calculate_comparison_metrics
from app.core.field_extractor import FieldExtractor


class EngineComparator:
    def __init__(self, engine_a: BaseOCREngine, engine_b: BaseOCREngine):
        self.engine_a = engine_a
        self.engine_b = engine_b
        self.field_extractor = FieldExtractor()

    def compare(self, image: bytes) -> Dict[str, Any]:
        result_a = self.engine_a.extract(image)
        result_b = self.engine_b.extract(image)

        fields_a = self.field_extractor.extract(result_a["raw_text"])
        fields_b = self.field_extractor.extract(result_b["raw_text"])

        metrics = calculate_comparison_metrics(fields_a, fields_b)

        recommendation = self.engine_a.get_name()
        if result_b["confidence"] > result_a["confidence"]:
            recommendation = self.engine_b.get_name()

        return {
            self.engine_a.get_name(): {
                "confidence": result_a["confidence"],
                "fields": fields_a,
                "raw_text": result_a["raw_text"],
                "processing_time_ms": result_a["processing_time_ms"],
            },
            self.engine_b.get_name(): {
                "confidence": result_b["confidence"],
                "fields": fields_b,
                "raw_text": result_b["raw_text"],
                "processing_time_ms": result_b["processing_time_ms"],
            },
            "comparison": metrics,
            "recommendation": recommendation,
        }
