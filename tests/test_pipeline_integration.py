import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.extraction_service import ExtractionService
from app.core.image_quality import ImageQualityAssessor
from app.core.document_validator import DocumentValidator


class TestExtractionServiceWithQuality:
    """Tests for ExtractionService integration with quality + authenticity."""

    def setup_method(self):
        mock_router = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_engine.get_name.return_value = "mock_engine"
        mock_router.get_engine.return_value = self.mock_engine
        self.service = ExtractionService(
            router=mock_router,
            enable_preprocessing=False,
        )

    def test_rc_book_extraction_includes_quality(self):
        """RC book extraction should include image_quality in result."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: RAJESH KUMAR\nFuel Type: Petrol\nVehicle Make: MARUTI\nDate of Registration: 15/03/2020",
            "confidence": 0.90,
            "blocks": [],
            "processing_time_ms": 100,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="front",
        )

        assert "image_quality" in result
        assert "overall_score" in result["image_quality"]
        assert "is_acceptable" in result["image_quality"]

    def test_rc_book_extraction_includes_authenticity(self):
        """RC book extraction should include document_authenticity in result."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: RAJESH KUMAR\nFuel Type: Petrol\nVehicle Make: MARUTI\nDate of Registration: 15/03/2020",
            "confidence": 0.90,
            "blocks": [],
            "processing_time_ms": 100,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="front",
        )

        assert "document_authenticity" in result
        assert "is_authentic" in result["document_authenticity"]
        assert "confidence" in result["document_authenticity"]

    def test_non_rc_book_skips_quality_and_authenticity(self):
        """Non-RC document types should NOT include quality/authenticity."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "Vendor: Big Bazaar\nTotal: 500.00\nDate: 15/01/2024\nBill No: B-12345",
            "confidence": 0.85,
            "blocks": [],
            "processing_time_ms": 50,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="receipt",
        )

        assert "image_quality" not in result
        assert "document_authenticity" not in result

    def test_side_auto_detection_in_extraction(self):
        """When side is not provided for rc_book, it should be auto-detected."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nEngine No: K12M1234567\nChassis No: MA3FJEB1S00123456\nCubic Capacity: 1197",
            "confidence": 0.88,
            "blocks": [],
            "processing_time_ms": 80,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
        )

        # Should still work without side param
        assert "fields" in result
        assert "detected_side" in result

    def test_extraction_always_returns_fields(self):
        """Even with low quality, extraction should return best-effort fields."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234",
            "confidence": 0.50,
            "blocks": [],
            "processing_time_ms": 120,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="front",
        )

        assert "fields" in result
        assert len(result["fields"]) > 0

    def test_rc_book_quality_has_expected_sub_scores(self):
        """Image quality should contain blur, brightness, resolution, completeness scores."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: RAJESH KUMAR\nFuel Type: Petrol\nVehicle Make: MARUTI\nDate of Registration: 15/03/2020",
            "confidence": 0.90,
            "blocks": [],
            "processing_time_ms": 100,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="front",
        )

        quality = result["image_quality"]
        assert "blur_score" in quality
        assert "brightness_score" in quality
        assert "resolution_score" in quality
        assert "completeness_score" in quality
        assert "feedback" in quality

    def test_rc_book_authenticity_has_structural_and_visual(self):
        """Document authenticity should contain structural and visual sub-dicts."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: RAJESH KUMAR\nFuel Type: Petrol\nVehicle Make: MARUTI\nDate of Registration: 15/03/2020",
            "confidence": 0.90,
            "blocks": [],
            "processing_time_ms": 100,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="front",
        )

        authenticity = result["document_authenticity"]
        assert "structural" in authenticity
        assert "visual" in authenticity

    def test_rc_book_back_side(self):
        """RC book back side should use back-specific fields and quality checks."""
        img_bytes = self._create_test_image_bytes()

        self.mock_engine.extract.return_value = {
            "raw_text": "REGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nEngine No: K12M1234567\nChassis No: MA3FJEB1S00123456\nCubic Capacity: 1197\nUnladen Weight: 875 KG",
            "confidence": 0.88,
            "blocks": [],
            "processing_time_ms": 80,
        }

        result = self.service.extract(
            image_bytes=img_bytes,
            document_type="rc_book",
            side="back",
        )

        assert "image_quality" in result
        assert "document_authenticity" in result
        assert "fields" in result

    def _create_test_image_bytes(self):
        """Create minimal valid image bytes for testing."""
        import cv2
        img = np.full((500, 800, 3), 128, dtype=np.uint8)
        _, img_encoded = cv2.imencode('.jpg', img)
        return img_encoded.tobytes()
