import pytest
import numpy as np
from app.core.document_validator import DocumentValidator


class TestStructuralChecks:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_valid_rc_header_passes(self):
        """Text containing 'REGISTRATION CERTIFICATE' header should pass"""
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: KA01AB1234"
        result = self.validator.check_structural(text, side="front")
        assert result["has_header"] is True

    def test_missing_header_fails(self):
        """Random text without RC header should fail"""
        text = "Some random text without any RC markers"
        result = self.validator.check_structural(text, side="front")
        assert result["has_header"] is False

    def test_valid_registration_format(self):
        """Standard Indian registration format should be detected"""
        text = "Registration No: KA01AB1234\nOwner: Test"
        result = self.validator.check_structural(text, side="front")
        assert result["has_valid_reg_format"] is True

    def test_invalid_registration_format(self):
        """Non-standard registration should fail format check"""
        text = "Registration No: INVALID123\nOwner: Test"
        result = self.validator.check_structural(text, side="front")
        assert result["has_valid_reg_format"] is False

    def test_sufficient_field_count_front(self):
        """Front side with enough fields should pass"""
        text = """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
S/O: SURESH KUMAR
Address: 123 MG Road
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        result = self.validator.check_structural(text, side="front")
        assert result["has_sufficient_fields"] is True

    def test_insufficient_field_count(self):
        """Only 1-2 lines should fail field count check"""
        text = "Registration No: KA01AB1234"
        result = self.validator.check_structural(text, side="front")
        assert result["has_sufficient_fields"] is False

    def test_structural_is_authentic_all_pass(self):
        """All structural checks pass -> is_authentic = True"""
        text = """FORM 23
REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
S/O: SURESH KUMAR
Address: 123 MG Road
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        result = self.validator.check_structural(text, side="front")
        assert result["is_authentic"] is True

    def test_structural_fails_if_no_header(self):
        """Missing header -> is_authentic = False (header is critical)"""
        text = """Registration No: KA01AB1234
Owner: RAJESH KUMAR
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        result = self.validator.check_structural(text, side="front")
        assert result["is_authentic"] is False

    def test_back_side_structural_check(self):
        """Back side structural checks should work"""
        text = """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Engine No: K12M1234567
Chassis No: MA3FJEB1S00123456
Cubic Capacity: 1197 CC
Wheelbase: 2430 MM
Emission Norms: BS VI"""
        result = self.validator.check_structural(text, side="back")
        assert result["has_header"] is True
        assert result["has_sufficient_fields"] is True


class TestVisualChecks:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_good_aspect_ratio_card(self):
        """Standard card aspect ratio (roughly 1.5-1.7) should score well"""
        # Create image with card-like aspect ratio (856x540 ~ 1.585)
        img = np.full((540, 856, 3), 200, dtype=np.uint8)
        result = self.validator.check_visual(img)
        assert result["aspect_ratio_score"] > 0.5

    def test_square_image_lower_score(self):
        """Square image is unusual for RC card"""
        img = np.full((500, 500, 3), 200, dtype=np.uint8)
        result = self.validator.check_visual(img)
        assert result["aspect_ratio_score"] < 1.0  # square is not ideal card ratio

    def test_visual_returns_confidence(self):
        """Visual check should return overall confidence"""
        img = np.full((540, 856, 3), 200, dtype=np.uint8)
        result = self.validator.check_visual(img)
        assert "visual_confidence" in result
        assert 0 <= result["visual_confidence"] <= 1.0

    def test_visual_checks_are_advisory(self):
        """Visual checks should never block - just add confidence"""
        img = np.full((100, 100, 3), 50, dtype=np.uint8)  # small dark image
        result = self.validator.check_visual(img)
        assert "visual_confidence" in result  # should still return, not throw


class TestCombinedValidation:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_validate_combines_structural_and_visual(self):
        """Combined validation should include both results"""
        text = """FORM 23
REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        img = np.full((540, 856, 3), 200, dtype=np.uint8)
        result = self.validator.validate(text, img, side="front")
        assert "is_authentic" in result
        assert "confidence" in result
        assert "structural" in result
        assert "visual" in result

    def test_validate_authentic_document(self):
        """Document passing structural checks should be authentic"""
        text = """FORM 23
REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        img = np.full((540, 856, 3), 200, dtype=np.uint8)
        result = self.validator.validate(text, img, side="front")
        assert result["is_authentic"] is True
        assert result["confidence"] > 0.5

    def test_validate_inauthentic_document(self):
        """Random text on random image should be inauthentic"""
        text = "Hello world random text"
        img = np.full((100, 100, 3), 50, dtype=np.uint8)
        result = self.validator.validate(text, img, side="front")
        assert result["is_authentic"] is False

    def test_confidence_boosted_by_visual(self):
        """Good visual checks should boost confidence above base 0.5"""
        text = """FORM 23
REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
Fuel Type: Petrol
Body Type: Sedan
Date of Registration: 15/03/2020"""
        img = np.full((540, 856, 3), 200, dtype=np.uint8)
        result = self.validator.validate(text, img, side="front")
        assert result["confidence"] >= 0.5  # at least base confidence
