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


def test_receipt_mapper_extracts_tax_fields(sample_raw_text_receipt):
    mapper = ReceiptMapper()
    fields = mapper.map_fields(sample_raw_text_receipt)

    field_dict = {f["label"]: f["value"] for f in fields}
    assert "cgst" in field_dict
    assert "sgst" in field_dict
    assert "subtotal" in field_dict


def test_receipt_mapper_extracts_line_items(sample_raw_text_receipt):
    mapper = ReceiptMapper()
    fields = mapper.map_fields(sample_raw_text_receipt)

    line_items = [f["value"] for f in fields if f["label"] == "line_item"]
    assert len(line_items) >= 1


def test_receipt_mapper_extracts_gstin():
    text = """NIEESH KITCHEN & BAR
GSTIN:27ABMCS0263P1ZQ

Date: 28/02/26  Dine In: 48
Cashier: biller  Bill No.: 8266

Item       Qty  Price  Amount
Jamun Sour    1  520.00  520.00
Mineral Water 3   30.00   90.00

Sub Total: 9620.00
SGST 2.5%  240.50
CGST 2.5%  240.50
Grand Total: 10101.00"""

    mapper = ReceiptMapper()
    fields = mapper.map_fields(text)
    field_dict = {f["label"]: f["value"] for f in fields}

    assert field_dict["vendor"] == "NIEESH KITCHEN & BAR"
    assert "27ABMCS0263P1ZQ" in field_dict["gstin"]
    assert field_dict["date"] == "28/02/26  Dine In: 48"
    assert field_dict["bill_no"] == "8266"
    assert field_dict["total"] == "10101.00"
    assert field_dict["subtotal"] == "9620.00"
    assert field_dict["sgst"] == "240.50"
    assert field_dict["cgst"] == "240.50"

    line_items = [f["value"] for f in fields if f["label"] == "line_item"]
    assert len(line_items) >= 2


def test_receipt_mapper_document_type():
    mapper = ReceiptMapper()
    assert mapper.document_type() == "receipt"


def test_receipt_mapper_empty_text():
    mapper = ReceiptMapper()
    fields = mapper.map_fields("")
    assert fields == []
