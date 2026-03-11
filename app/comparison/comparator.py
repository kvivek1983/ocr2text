from typing import Any, Dict, Optional
from app.engines.base import BaseOCREngine
from app.comparison.metrics import calculate_comparison_metrics
from app.core.field_extractor import FieldExtractor


class Comparator:
    """N-engine comparator that runs multiple OCR engines and compares results."""

    def __init__(
        self,
        engines: Optional[Dict[str, BaseOCREngine]] = None,
        **kwargs,
    ):
        """Initialize with a dict of named engines.

        Args:
            engines: Dict mapping engine_name -> engine instance.
            **kwargs: For backward compatibility (engine_a=..., engine_b=...).
        """
        if engines is not None:
            self.engines = engines
        elif kwargs:
            # Backward compat: Comparator(engine_a=eng_a, engine_b=eng_b)
            self.engines = kwargs
        else:
            self.engines = {}

        self.field_extractor = FieldExtractor()

    def compare(self, image: bytes, document_type: str = None) -> Dict[str, Any]:
        """Run all engines on the image and compare results.

        Returns:
            {
                "metrics": { agreement_rate, total_fields, field_agreement, ... },
                "engine_results": { engine_name: { fields, raw_text, confidence, ... }, ... },
                "recommendation": str (engine name with highest confidence),
            }
        """
        engine_results = {}
        engine_fields = {}

        for name, engine in self.engines.items():
            result = engine.extract(image)

            # Handle both raw text (string) and structured result (dict) returns
            if isinstance(result, str):
                raw_text = result
                confidence = 0.0
                processing_time_ms = 0
            else:
                raw_text = result.get("raw_text", "")
                confidence = result.get("confidence", 0.0)
                processing_time_ms = result.get("processing_time_ms", 0)

            fields = self.field_extractor.extract(raw_text)

            engine_results[name] = {
                "fields": fields,
                "raw_text": raw_text,
                "confidence": confidence,
                "processing_time_ms": processing_time_ms,
            }
            engine_fields[name] = fields

        metrics = calculate_comparison_metrics(engine_fields)

        # Recommendation: engine with highest confidence
        recommendation = None
        best_confidence = -1
        for name, res in engine_results.items():
            if res["confidence"] > best_confidence:
                best_confidence = res["confidence"]
                recommendation = name

        return {
            "metrics": metrics,
            "engine_results": engine_results,
            "recommendation": recommendation,
        }


class EngineComparator:
    """Legacy 2-engine comparator (backward compatible).

    Preserved for existing code that uses EngineComparator(engine_a, engine_b).
    """

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
