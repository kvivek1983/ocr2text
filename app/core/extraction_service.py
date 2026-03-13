# app/core/extraction_service.py
import cv2
import numpy as np
from typing import Any, Dict, List, Optional

from app.core.document_detector import DocumentDetector
from app.core.field_extractor import FieldExtractor
from app.core.image_quality import ImageQualityAssessor
from app.core.document_validator import DocumentValidator
from app.core.preprocessor import ImagePreprocessor
from app.core.router import EngineRouter
from app.mappers import get_mapper
from app.mappers.rc_book import _detect_side


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
        self.quality_assessor = ImageQualityAssessor()
        self.document_validator = DocumentValidator()

    def extract(
        self,
        image_bytes: bytes,
        engine: str = "paddle",
        document_type: Optional[str] = None,
        include_raw_text: bool = True,
        side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full extraction pipeline."""
        # 1. Preprocess
        processed = self.preprocessor.process(image_bytes)

        # 2. OCR — fallback to easyocr if primary engine crashes
        ocr_engine = self.router.get_engine(engine)
        try:
            ocr_result = ocr_engine.extract(processed)
        except Exception as primary_err:
            fallback_name = "easyocr" if engine != "easyocr" else "tesseract"
            try:
                fallback_engine = self.router.get_engine(fallback_name)
                ocr_result = fallback_engine.extract(processed)
            except Exception:
                raise primary_err  # re-raise original if fallback also fails

        raw_text = ocr_result["raw_text"]
        confidence = ocr_result["confidence"]
        processing_time_ms = ocr_result["processing_time_ms"]

        # 3. Detect document type (if not provided)
        if not document_type:
            document_type, _det_conf = self.detector.detect(raw_text)

        # 4. Map fields using type-specific mapper
        fields: List[Dict[str, str]] = []
        is_rc_book = document_type == "rc_book"

        try:
            mapper = get_mapper(document_type)
            if is_rc_book:
                fields = mapper.map_fields(raw_text, side=side)
            else:
                fields = mapper.map_fields(raw_text)
        except ValueError:
            fields = self.field_extractor.extract(raw_text)

        # 5. Build base result
        result: Dict[str, Any] = {
            "success": True,
            "document_type": document_type,
            "confidence": confidence,
            "fields": fields,
            "raw_text": raw_text if include_raw_text else None,
            "processing_time_ms": processing_time_ms,
        }

        # 6. RC book specific: quality assessment and authenticity validation
        if is_rc_book:
            # Decode image bytes to numpy array for CV2 analysis
            img_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            # Auto-detect side if not provided
            detected_side = side if side else _detect_side(raw_text)
            result["detected_side"] = detected_side

            # Layer A: Image property assessment (pre-OCR quality)
            layer_a = self.quality_assessor.assess_image_properties(image)

            # Layer B: Extraction completeness assessment (post-OCR quality)
            layer_b = self.quality_assessor.assess_completeness(fields, side=detected_side)

            # Combine quality layers
            quality = self.quality_assessor.combine(layer_a, layer_b)
            result["image_quality"] = quality

            # Authenticity validation
            authenticity = self.document_validator.validate(raw_text, image, side=detected_side)
            result["document_authenticity"] = authenticity

        return result
