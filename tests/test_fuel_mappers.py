# tests/test_fuel_mappers.py
from app.mappers.petrol_receipt import PetrolReceiptMapper
from app.mappers.odometer import OdometerMapper
from app.mappers.fuel_pump_reading import FuelPumpReadingMapper


def test_petrol_receipt_mapper(sample_raw_text_petrol_receipt):
    mapper = PetrolReceiptMapper()
    fields = mapper.map_fields(sample_raw_text_petrol_receipt)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "fuel_type" in field_dict
    assert "total_amount" in field_dict
    assert mapper.document_type() == "petrol_receipt"


def test_petrol_receipt_empty():
    mapper = PetrolReceiptMapper()
    assert mapper.map_fields("") == []


def test_odometer_mapper(sample_raw_text_odometer):
    mapper = OdometerMapper()
    fields = mapper.map_fields(sample_raw_text_odometer)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "reading_km" in field_dict
    assert "45230" in field_dict["reading_km"]
    assert mapper.document_type() == "odometer"


def test_odometer_empty():
    mapper = OdometerMapper()
    assert mapper.map_fields("") == []


def test_fuel_pump_reading_mapper(sample_raw_text_fuel_pump):
    mapper = FuelPumpReadingMapper()
    fields = mapper.map_fields(sample_raw_text_fuel_pump)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert "pump_reading_start" in field_dict or "pump_reading_end" in field_dict
    assert mapper.document_type() == "fuel_pump_reading"


def test_fuel_pump_reading_empty():
    mapper = FuelPumpReadingMapper()
    assert mapper.map_fields("") == []
