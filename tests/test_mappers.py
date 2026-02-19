import pytest
from app.mappers.base import BaseMapper
from app.mappers.receipt import ReceiptMapper


def test_base_mapper_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseMapper()


def test_receipt_mapper_maps_fields(sample_raw_text_receipt):
    mapper = ReceiptMapper()
    fields = mapper.map_fields(sample_raw_text_receipt)

    field_dict = {f["label"]: f["value"] for f in fields}
    assert "vendor" in field_dict
    assert "Big Bazaar" in field_dict["vendor"] or "BIG BAZAAR" in field_dict["vendor"]
    assert "date" in field_dict
    assert "total" in field_dict or "grand_total" in field_dict


def test_receipt_mapper_document_type():
    mapper = ReceiptMapper()
    assert mapper.document_type() == "receipt"


def test_receipt_mapper_empty_text():
    mapper = ReceiptMapper()
    fields = mapper.map_fields("")
    assert fields == []
