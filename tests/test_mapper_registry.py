# tests/test_mapper_registry.py
import pytest
from app.mappers import get_mapper, list_document_types


def test_get_mapper_receipt():
    mapper = get_mapper("receipt")
    assert mapper.document_type() == "receipt"


def test_get_mapper_invoice():
    mapper = get_mapper("invoice")
    assert mapper.document_type() == "invoice"


def test_get_mapper_driving_license():
    mapper = get_mapper("driving_license")
    assert mapper.document_type() == "driving_license"


def test_get_mapper_rc_book():
    mapper = get_mapper("rc_book")
    assert mapper.document_type() == "rc_book"


def test_get_mapper_insurance():
    mapper = get_mapper("insurance")
    assert mapper.document_type() == "insurance"


def test_get_mapper_petrol_receipt():
    mapper = get_mapper("petrol_receipt")
    assert mapper.document_type() == "petrol_receipt"


def test_get_mapper_odometer():
    mapper = get_mapper("odometer")
    assert mapper.document_type() == "odometer"


def test_get_mapper_fuel_pump_reading():
    mapper = get_mapper("fuel_pump_reading")
    assert mapper.document_type() == "fuel_pump_reading"


def test_get_mapper_unknown_raises():
    with pytest.raises(ValueError, match="No mapper"):
        get_mapper("nonexistent")


def test_list_document_types():
    types = list_document_types()
    assert "receipt" in types
    assert "invoice" in types
    assert "driving_license" in types
    assert len(types) == 8
