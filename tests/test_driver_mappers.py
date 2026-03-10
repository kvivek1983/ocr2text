# tests/test_driver_mappers.py
from app.mappers.driving_license import DrivingLicenseMapper
from app.mappers.rc_book import RCBookMapper
from app.mappers.insurance import InsuranceMapper


def test_driving_license_mapper(sample_raw_text_driving_license):
    mapper = DrivingLicenseMapper()
    fields = mapper.map_fields(sample_raw_text_driving_license)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "license_number" in field_dict
    assert "KA01" in field_dict["license_number"]
    assert "name" in field_dict
    assert mapper.document_type() == "driving_license"


def test_driving_license_empty():
    mapper = DrivingLicenseMapper()
    assert mapper.map_fields("") == []


def test_rc_book_mapper(sample_raw_text_rc_book):
    mapper = RCBookMapper()
    fields = mapper.map_fields(sample_raw_text_rc_book)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "registration_number" in field_dict
    assert "KA01AB1234" in field_dict["registration_number"]
    assert "owner_name" in field_dict
    assert mapper.document_type() == "rc_book"


def test_rc_book_empty():
    mapper = RCBookMapper()
    assert mapper.map_fields("") == []


def test_rc_book_gujarat_smartcard():
    """Test against real Gujarat smart-card RC OCR output."""
    raw = """Government of Gujarat
Certificate of Registration
Reg. No.  GJ01DX6778  Date of Reg  25/06/2012
Chassis No.
MBJB2ZBT200037980
Engine No.
2NRV053813
Owner Name  PATEL MITTAL  Owner Sr. No.  02
Vehicle Class  CAR TAXI
Son/Daughter/Wife of
BHARATBHAI
Fuel Used  PET/CNG
Address  T-302, C/O INDRAPATH FLAT, OPP SARVODAY-3,
VASNA PARK, GHATLODIA, AHMEDABAD"""

    mapper = RCBookMapper()
    fields = mapper.map_fields(raw)
    fd = {f["label"]: f["value"] for f in fields}

    assert fd["registration_number"] == "GJ01DX6778"
    assert fd["registration_date"] == "25/06/2012"
    assert fd["chassis_number"] == "MBJB2ZBT200037980"
    assert fd["engine_number"] == "2NRV053813"
    assert fd["owner_name"] == "PATEL MITTAL"
    assert fd["owner_serial_number"] == "02"
    assert fd["vehicle_class"] == "CAR TAXI"
    assert fd["father_or_spouse_name"] == "BHARATBHAI"
    assert fd["fuel_type"] == "PET/CNG"
    assert "INDRAPATH FLAT" in fd["address"]
    assert "AHMEDABAD" in fd["address"]


def test_rc_book_multiline_address():
    """Address spans multiple lines."""
    raw = """Reg. No. MH12DE5678
Owner Name  JOHN DOE
Address  FLAT 101, BUILDING A,
SECTOR 5, VASHI,
NAVI MUMBAI 400703
Fuel Used  DIESEL"""

    mapper = RCBookMapper()
    fields = mapper.map_fields(raw)
    fd = {f["label"]: f["value"] for f in fields}

    assert fd["registration_number"] == "MH12DE5678"
    assert "VASHI" in fd["address"]
    assert "NAVI MUMBAI" in fd["address"]


def test_rc_book_noisy_ocr():
    """Handle OCR with dots/periods in labels."""
    raw = """Regd. No.  TN01AB9999
Owner's Name  KUMAR S
Eng. No.  G4FCAU123456
Ch. No.  MALA51CR5GT012345
Date of Regd.  10/11/2018
Veh. Class  Motor Car
Colour  SILVER"""

    mapper = RCBookMapper()
    fields = mapper.map_fields(raw)
    fd = {f["label"]: f["value"] for f in fields}

    assert fd["registration_number"] == "TN01AB9999"
    assert "KUMAR" in fd["owner_name"]
    assert fd["engine_number"] == "G4FCAU123456"
    assert fd["chassis_number"] == "MALA51CR5GT012345"
    assert fd["registration_date"] == "10/11/2018"
    assert fd["vehicle_class"] == "Motor Car"
    assert fd["color"] == "SILVER"


def test_insurance_mapper(sample_raw_text_insurance):
    mapper = InsuranceMapper()
    fields = mapper.map_fields(sample_raw_text_insurance)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "policy_number" in field_dict
    assert "insurer" in field_dict
    assert mapper.document_type() == "insurance"


def test_insurance_empty():
    mapper = InsuranceMapper()
    assert mapper.map_fields("") == []
