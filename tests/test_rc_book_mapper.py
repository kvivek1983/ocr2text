import pytest
from app.mappers.rc_book import RCBookMapper


class TestRCBookMapperFront:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_front_extracts_registration_number(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "KA01AB1234" in field_dict["registration_number"]

    def test_front_extracts_owner_name(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" in field_dict
        assert "RAJESH KUMAR" in field_dict["owner_name"]

    def test_front_extracts_fuel_type(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fuel_type" in field_dict
        assert "Petrol" in field_dict["fuel_type"]

    def test_front_extracts_registration_date(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_date" in field_dict

    def test_front_extracts_fitness_expiry(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fitness_expiry" in field_dict

    def test_front_extracts_tax_expiry(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "tax_expiry" in field_dict

    def test_front_does_not_extract_back_fields(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" not in field_dict
        assert "chassis_number" not in field_dict
        assert "cubic_capacity" not in field_dict

    def test_front_all_mandatory_fields_present(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        mandatory = ["registration_number", "owner_name", "fuel_type", "registration_date"]
        for field in mandatory:
            assert field in field_dict, f"Mandatory field '{field}' missing from front extraction"


class TestRCBookMapperBack:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_back_extracts_registration_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "KA01AB1234" in field_dict["registration_number"]

    def test_back_extracts_engine_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" in field_dict
        assert "K12M1234567" in field_dict["engine_number"]

    def test_back_extracts_chassis_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "chassis_number" in field_dict
        assert "MA3FJEB1S00123456" in field_dict["chassis_number"]

    def test_back_extracts_cubic_capacity(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "cubic_capacity" in field_dict

    def test_back_does_not_extract_front_fields(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" not in field_dict
        assert "fuel_type" not in field_dict

    def test_back_all_mandatory_fields_present(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        mandatory = ["registration_number", "engine_number", "chassis_number"]
        for field in mandatory:
            assert field in field_dict, f"Mandatory field '{field}' missing from back extraction"


class TestRCBookMapperAutoDetect:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_auto_detect_front(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side=None)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" in field_dict
        assert "registration_number" in field_dict

    def test_auto_detect_back(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side=None)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" in field_dict
        assert "chassis_number" in field_dict

    def test_empty_text_returns_empty(self):
        mapper = RCBookMapper()
        assert mapper.map_fields("", side="front") == []
        assert mapper.map_fields("", side="back") == []
        assert mapper.map_fields("") == []

    def test_backward_compat_no_side(self, sample_raw_text_rc_book):
        mapper = RCBookMapper()
        fields = mapper.map_fields(sample_raw_text_rc_book)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict


class TestRCBookMapperGujaratFormat:
    """Tests with real Gujarat RC OCR output format."""

    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_gujarat_front_extraction(self):
        """Real Gujarat RC front side OCR output."""
        text = """Indian Union Vehide Registration Certificate
Issued by Gujarat Motor Vehicle Department. .
Regn No
GJ27TG4232
Date of Regn
29-08-2025
As per Fitness
Chassis No
MA3ZFDFSKSH252355
Engine/Motor No
Z12ENF152032
Owner Name
SUNILBHAI KARSANBHAI CHUNARA
Son/Wife/Daughter of (In case of Individual Owner)
KARSANBHAI CHUNARA
Ownership
INDIVIDUAL
Fuel
PETROL/CNG
Emission Norms
BHARAT STAGE VI
Address
58, SWAPNA SANKET SOCIETY, BH DERIYA VAS, VATVA, DASKROI
AHMEDABAD(EAST)-GUJARAT-382440"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "GJ27TG4232" in field_dict["registration_number"]
        assert "owner_name" in field_dict
        assert "SUNILBHAI" in field_dict["owner_name"]
        assert "fuel_type" in field_dict

    def test_gujarat_back_extraction(self):
        """Real Gujarat RC back side OCR output."""
        text = """Vehicle Class: MOTOR CAB (LPV)
Regn. Number
GJ27TG4232
Maker's Name:
MARUTI SUZUKI INDIA LTD
Model Name:
TOUR S CNG
Colour:
PEARL ARCTIC WHITE
Body Type:
RIGID (PASSENGER CAR)
Seating(in all) Capacity
5
Unladen/ Laden Weight (Kg)
1010 / 1435
Cubic Cap. / Horse Power (BHP/Kw) Wheel Base(mm)
1197.00 / 80.40 2450
Month-Year of Mfg.
08-2025
Financier:
INDUSIND BANK LIMITED
No. of Cylinders
3
Registration Authority
AHMEDABAD EAST"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "GJ27TG4232" in field_dict["registration_number"]
        assert "vehicle_make" in field_dict
        assert "MARUTI" in field_dict["vehicle_make"]
        assert "vehicle_model" in field_dict
        assert "TOUR S CNG" in field_dict["vehicle_model"]
        assert "chassis_number" not in field_dict  # not on back of Gujarat format
