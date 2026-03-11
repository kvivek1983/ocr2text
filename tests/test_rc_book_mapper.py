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

    def test_front_does_not_extract_back_only_fields(self, sample_raw_text_rc_front):
        """Front should not extract back-only fields (vehicle_make, cubic_capacity etc.)"""
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "cubic_capacity" not in field_dict
        assert "vehicle_make" not in field_dict

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
        """Real Gujarat RC front side — clean OCR output."""
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
        # Gujarat front has engine/chassis — now COMMON fields
        assert "engine_number" in field_dict
        assert "Z12ENF152032" in field_dict["engine_number"]
        assert "chassis_number" in field_dict
        assert "MA3ZFDFSKSH252355" in field_dict["chassis_number"]

    def test_gujarat_back_extraction(self):
        """Real Gujarat RC back side — clean OCR output."""
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
        # Gujarat back has NO engine/chassis
        assert "chassis_number" not in field_dict
        assert "engine_number" not in field_dict


class TestRCBookMapperFallbacks:
    """Tests for fallback extraction strategies."""

    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_fuel_type_fallback_petrolcng(self):
        """Fuel type extracted even without 'Fuel' label (OCR drops label)."""
        text = """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner Name: RAJESH KUMAR
Date of Registration: 15/03/2020
PETROLCNG"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fuel_type" in field_dict
        assert field_dict["fuel_type"] == "PETROL/CNG"

    def test_fuel_type_fallback_diesel(self):
        """Standalone DIESEL line without label."""
        text = """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner Name: RAJESH KUMAR
Date of Registration: 15/03/2020
DIESEL"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fuel_type" in field_dict
        assert field_dict["fuel_type"] == "DIESEL"

    def test_reg_number_fallback_regex(self):
        """Registration number extracted by regex when label not matched."""
        text = """REGISTRATION CERTIFICATE
GJ27TG4232
Maker's Name:
MARUTI SUZUKI"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "GJ27TG4232" in field_dict["registration_number"]

    def test_ocr_typo_regr_number(self):
        """OCR misreads 'Regn' as 'Regr' — should still match."""
        text = """Regr Number
GJ27TG4232
Maker's Name:
MARUTI SUZUKI"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "GJ27TG4232" in field_dict["registration_number"]

    def test_ocr_typo_model_namo(self):
        """OCR misreads 'Model Name' as 'Model Namo' — should still match."""
        text = """Registration No: GJ27TG4232
Maker's Name:
MARUTI SUZUKI
Model Namo:
TOUR S CNG"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "vehicle_model" in field_dict
        assert "TOUR S CNG" in field_dict["vehicle_model"]

    def test_descriptor_text_skipped(self):
        """Parenthetical descriptor text should be skipped for next-line value."""
        text = """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner Name: RAJESH KUMAR
Son/Wife/Daughter of (In case of Individual Owner)
KARSANBHAI CHUNARA
Fuel Type: Petrol
Date of Registration: 15/03/2020"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "father_name" in field_dict
        assert "KARSANBHAI CHUNARA" in field_dict["father_name"]

    def test_next_line_skips_blanks(self):
        """Next-line extraction skips blank lines to find value."""
        text = """REGISTRATION CERTIFICATE
Regn No

GJ27TG4232
Owner Name: RAJESH KUMAR
Fuel Type: Petrol
Date of Registration: 15/03/2020"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "GJ27TG4232" in field_dict["registration_number"]


class TestRCBookMapperRealPaddleOCR:
    """Tests with actual noisy PaddleOCR output from Gujarat RC images."""

    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_noisy_front_ocr(self):
        """Real PaddleOCR output from Gujarat RC front — messy but should extract key fields."""
        text = """Indian Union Vehide Registration Certificate
Issued by Gujarat Motor Vehicle Department. .
Regn No
Date of RegnRegnValidity
Owner
GJ271G4232
29-08-2025
AsperFitness
Seral
Chassis No
MA3ZFDFSKSH252355
Engine/Motor No
Z12ENF152032
Owner Name
SUNILBHAIKARSANBHAICHUNARA
Son/Wife/Daughter of (In case of Individual Owner)
KARSANBHAI CHUNARA
Ownership
INDIVIDUAL
PETROLCNG
Address
EmlssIon Norms.? 58, SWApNA SAnKET SOCIETY, Bh DERIyA VAS, VaTVA,DASKRO..
pJe
BHARAT STAGE*AHMEDABAD(EAST)-GUJARAT-382440
C"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        # Engine and chassis should still be extractable (common fields)
        assert "engine_number" in field_dict
        assert "Z12ENF152032" in field_dict["engine_number"]
        assert "chassis_number" in field_dict
        assert "MA3ZFDFSKSH252355" in field_dict["chassis_number"]
        # Owner name (merged but present)
        assert "owner_name" in field_dict
        # Fuel type via fallback
        assert "fuel_type" in field_dict
        assert field_dict["fuel_type"] == "PETROL/CNG"
        # Registration number — should be found via fallback regex
        assert "registration_number" in field_dict

    def test_noisy_back_ocr(self):
        """Real PaddleOCR output from Gujarat RC back — messy but should extract key fields."""
        text = """VecsMOTOR CABLPV
GJ08147349
Regr Number
Maker's Name
MARUTI SUZURIINDIALTD
GJ27G4232
Model Namo:
TOUR S CNG
Colour:
-
Body Type
PEARLARCTICWHITE
RIGID (PASSENGERCAR
Seating(in all Gapacity
23A
Form
UnladenLaden Weight (Kg)
1010
11435
Cublc Cap./ Horse Power (BHP/Kw) Wheel Base(mm)
2450
1197.008040
Month-YearofMfg
08-2025
Financier:
:
INDUSIND BANKLIMITED
No.of Cylinders
Registralion Authorily
AHMEDABAD EAST"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        # Registration number via "Regr Number" alias or regex fallback
        assert "registration_number" in field_dict
        # Vehicle make should be extracted
        assert "vehicle_make" in field_dict
        assert "MARUTI" in field_dict["vehicle_make"]
        # Model via "model namo" alias
        assert "vehicle_model" in field_dict
        assert "TOUR S CNG" in field_dict["vehicle_model"]

    def test_registration_date_not_reg_number(self):
        """registration_date should extract a date, not a reg number."""
        text = """Regn No
Date of RegnRegnValidity
Owner
GJ271G4232
29-08-2025
AsperFitness"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        if "registration_date" in field_dict:
            # Must look like a date, not a reg number
            assert "29-08-2025" in field_dict["registration_date"]

    def test_cylinders_not_authority(self):
        """cylinders should not pick up registration authority value."""
        text = """No.of Cylinders
Registralion Authorily
AHMEDABAD EAST"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        # "Registralion Authorily" should be treated as a label, not a value
        if "cylinders" in field_dict:
            assert "AHMEDABAD" not in field_dict["cylinders"]

    def test_back_reg_number_not_maker_name(self):
        """registration_number on back should not pick up maker name."""
        text = """GJ08147349
Regr Number
MARUTI SUZUKI INDIA LTD
GJ27TG4232
Model Name:
TOUR S CNG"""
        fields = self.mapper.map_fields(text, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        # Should get the actual reg number, not the maker name
        assert "MARUTI" not in field_dict["registration_number"]

    def test_mh_front_merged_reg_date(self):
        """MH format: reg number and date merged on same line should be split."""
        text = """Indian Union Vehicle Registration Certificate
Issued by Government of Maharashtra
Regn. Validity
Regn. Number.. ..Date of Regn.
As per Fitness
MH04MH1036 ..: 06-11-2024
Owner
16:11-2024
Chassis Number.
Serial
MALB341CLRM300255
Engine/Motor Number
G4LARM044609.
Owner Name
RISHIKA TOURS AND TRAVELS
Fuel :
Son/Wife/.Daughter of.(ln case of Individual Owner)
PETROL/CNG :
NA
Address:
Emission Norms
GHODBUNDER ROAD BUDHHAVIHAR,THANEWEST,
BHARATSTAGEVIA
DONNGARI PADAThane,MH400615"""
        fields = self.mapper.map_fields(text, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        # Registration number should be clean (no date appended)
        assert "registration_number" in field_dict
        assert field_dict["registration_number"] == "MH04MH1036"
        # Registration date should be extracted
        assert "registration_date" in field_dict
        assert "06-11-2024" in field_dict["registration_date"]
        # Chassis should skip "Serial" label and get actual value
        assert "chassis_number" in field_dict
        assert field_dict["chassis_number"] == "MALB341CLRM300255"
        # Engine number should be extracted (engine/motor number alias)
        assert "engine_number" in field_dict
        assert "G4LARM044609" in field_dict["engine_number"]
        # Owner name
        assert "owner_name" in field_dict
        assert field_dict["owner_name"] == "RISHIKA TOURS AND TRAVELS"
        # Fuel type
        assert "fuel_type" in field_dict
