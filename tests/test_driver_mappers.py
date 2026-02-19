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
