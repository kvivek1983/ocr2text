# app/core/extraction_service.py
from typing import Any, Dict, List, Optional

from app.core.document_detector import DocumentDetector
from app.core.field_extractor import FieldExtractor
from app.core.preprocessor import ImagePreprocessor
from app.core.router import EngineRouter
from app.mappers import get_mapper


class ExtractionService:
    """Orchestrates the full extraction pipeline."""

    def __init__(
        self,
        router: EngineRouter,
        enable_preprocessing: bool = True,
    ):
        self.router = router
        self.preprocessor = ImagePreprocessor(enabled=enable_preprocessing)
        self.detector = DocumentDetector()
        self.field_extractor = FieldExtractor()

    def extract(
        self,
        image_bytes: bytes,
        engine: str = "paddle",
        document_type: Optional[str] = None,
        include_raw_text: bool = True,
    ) -> Dict[str, Any]:
        """Run full extraction pipeline."""
        # 1. Preprocess
        processed = self.preprocessor.process(image_bytes)

        # 2. OCR
        ocr_engine = self.router.get_engine(engine)
        ocr_result = ocr_engine.extract(processed)

        raw_text = ocr_result["raw_text"]
        confidence = ocr_result["confidence"]
        processing_time_ms = ocr_result["processing_time_ms"]

        # 3. Detect document type (if not provided)
        if not document_type:
            document_type, _det_conf = self.detector.detect(raw_text)

        # 4. Map fields using type-specific mapper
        fields: List[Dict[str, str]] = []
        try:
            mapper = get_mapper(document_type)
            fields = mapper.map_fields(raw_text)
        except ValueError:
            fields = self.field_extractor.extract(raw_text)

        return {
            "success": True,
            "document_type": document_type,
            "confidence": confidence,
            "fields": fields,
            "raw_text": raw_text if include_raw_text else None,
            "processing_time_ms": processing_time_ms,
        }
