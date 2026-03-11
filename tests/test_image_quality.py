import pytest
import numpy as np
from unittest.mock import patch
from app.core.image_quality import ImageQualityAssessor


class TestLayerAImageProperties:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_good_image_passes_blur(self):
        """A sharp image should have blur_score > 0.7"""
        # Create sharp image with edges
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        img[100:400, 100:400] = 255  # sharp white rectangle on black
        result = self.assessor.assess_image_properties(img)
        assert result["blur_score"] > 0.7

    def test_blurry_image_fails_blur(self):
        """A very blurry image should have blur_score < 0.5"""
        import cv2
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        img[100:400, 100:400] = 255
        blurry = cv2.GaussianBlur(img, (51, 51), 0)
        result = self.assessor.assess_image_properties(blurry)
        assert result["blur_score"] < 0.5

    def test_good_brightness(self):
        """Normal brightness image should score > 0.7"""
        img = np.full((500, 500, 3), 128, dtype=np.uint8)  # mid-gray
        result = self.assessor.assess_image_properties(img)
        assert result["brightness_score"] > 0.7

    def test_dark_image_low_brightness(self):
        """Very dark image should score < 0.5"""
        img = np.full((500, 500, 3), 20, dtype=np.uint8)
        result = self.assessor.assess_image_properties(img)
        assert result["brightness_score"] < 0.5

    def test_overexposed_image_low_brightness(self):
        """Very bright image should score < 0.5"""
        img = np.full((500, 500, 3), 250, dtype=np.uint8)
        result = self.assessor.assess_image_properties(img)
        assert result["brightness_score"] < 0.5

    def test_good_resolution(self):
        """Image >= 800x600 should have resolution_score = 1.0"""
        img = np.zeros((800, 600, 3), dtype=np.uint8)
        result = self.assessor.assess_image_properties(img)
        assert result["resolution_score"] == 1.0

    def test_low_resolution(self):
        """Image < 200x200 should have resolution_score < 0.5"""
        img = np.zeros((150, 150, 3), dtype=np.uint8)
        result = self.assessor.assess_image_properties(img)
        assert result["resolution_score"] < 0.5

    def test_returns_layer_a_score(self):
        """Result should contain overall layer_a_score"""
        img = np.full((500, 500, 3), 128, dtype=np.uint8)
        result = self.assessor.assess_image_properties(img)
        assert "layer_a_score" in result
        assert 0 <= result["layer_a_score"] <= 1.0


class TestLayerBCompleteness:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_all_mandatory_fields_present(self):
        """All mandatory fields present should score 1.0"""
        fields = [
            {"label": "registration_number", "value": "KA01AB1234"},
            {"label": "owner_name", "value": "RAJESH KUMAR"},
            {"label": "vehicle_make", "value": "MARUTI SUZUKI"},
            {"label": "fuel_type", "value": "Petrol"},
            {"label": "registration_date", "value": "15/03/2020"},
        ]
        result = self.assessor.assess_completeness(fields, side="front")
        assert result["completeness_score"] == 1.0
        assert result["missing_mandatory"] == []

    def test_missing_fields_lowers_score(self):
        """Missing mandatory fields should lower score"""
        fields = [
            {"label": "registration_number", "value": "KA01AB1234"},
            {"label": "owner_name", "value": "RAJESH KUMAR"},
        ]
        result = self.assessor.assess_completeness(fields, side="front")
        assert result["completeness_score"] < 1.0
        assert len(result["missing_mandatory"]) > 0

    def test_back_side_mandatory_fields(self):
        """Back side uses back mandatory list"""
        fields = [
            {"label": "registration_number", "value": "KA01AB1234"},
            {"label": "vehicle_make", "value": "MARUTI SUZUKI"},
            {"label": "engine_number", "value": "K12M1234567"},
            {"label": "chassis_number", "value": "MA3FJEB1S00123456"},
        ]
        result = self.assessor.assess_completeness(fields, side="back")
        assert result["completeness_score"] == 1.0

    def test_empty_fields_zero_score(self):
        """No fields at all should score 0"""
        result = self.assessor.assess_completeness([], side="front")
        assert result["completeness_score"] == 0.0

    def test_returns_layer_b_score(self):
        """Result should contain layer_b_score"""
        fields = [{"label": "registration_number", "value": "KA01"}]
        result = self.assessor.assess_completeness(fields, side="front")
        assert "layer_b_score" in result


class TestCombinedQualityScore:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_combined_score_formula(self):
        """Combined = 0.3 * layer_a + 0.7 * layer_b"""
        layer_a = {"layer_a_score": 0.8, "blur_score": 0.9, "brightness_score": 0.8, "resolution_score": 0.7}
        layer_b = {"layer_b_score": 1.0, "completeness_score": 1.0, "missing_mandatory": [], "total_mandatory": 5, "found_mandatory": 5}
        result = self.assessor.combine(layer_a, layer_b)
        expected = 0.3 * 0.8 + 0.7 * 1.0
        assert abs(result["overall_score"] - expected) < 0.01

    def test_unacceptable_when_2_plus_missing(self):
        """2+ missing mandatory fields -> is_acceptable = False"""
        layer_a = {"layer_a_score": 0.9, "blur_score": 0.9, "brightness_score": 0.9, "resolution_score": 0.9}
        layer_b = {"layer_b_score": 0.4, "completeness_score": 0.4, "missing_mandatory": ["owner_name", "fuel_type", "registration_date"], "total_mandatory": 5, "found_mandatory": 2}
        result = self.assessor.combine(layer_a, layer_b)
        assert result["is_acceptable"] is False

    def test_unacceptable_when_blur_plus_missing(self):
        """Blur (score < 0.5) + 1 missing mandatory -> is_acceptable = False"""
        layer_a = {"layer_a_score": 0.3, "blur_score": 0.3, "brightness_score": 0.8, "resolution_score": 0.8}
        layer_b = {"layer_b_score": 0.8, "completeness_score": 0.8, "missing_mandatory": ["owner_name"], "total_mandatory": 5, "found_mandatory": 4}
        result = self.assessor.combine(layer_a, layer_b)
        assert result["is_acceptable"] is False

    def test_acceptable_good_quality(self):
        """Good image with all fields -> is_acceptable = True"""
        layer_a = {"layer_a_score": 0.9, "blur_score": 0.9, "brightness_score": 0.9, "resolution_score": 0.9}
        layer_b = {"layer_b_score": 1.0, "completeness_score": 1.0, "missing_mandatory": [], "total_mandatory": 5, "found_mandatory": 5}
        result = self.assessor.combine(layer_a, layer_b)
        assert result["is_acceptable"] is True

    def test_feedback_messages(self):
        """Should include feedback messages when quality is low"""
        layer_a = {"layer_a_score": 0.3, "blur_score": 0.2, "brightness_score": 0.3, "resolution_score": 0.4}
        layer_b = {"layer_b_score": 0.4, "completeness_score": 0.4, "missing_mandatory": ["owner_name", "fuel_type"], "total_mandatory": 5, "found_mandatory": 3}
        result = self.assessor.combine(layer_a, layer_b)
        assert "feedback" in result
        assert len(result["feedback"]) > 0
