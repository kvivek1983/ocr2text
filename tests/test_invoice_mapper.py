from app.mappers.invoice import InvoiceMapper


def test_invoice_mapper_maps_fields(sample_raw_text_invoice):
    mapper = InvoiceMapper()
    fields = mapper.map_fields(sample_raw_text_invoice)

    field_dict = {f["label"]: f["value"] for f in fields}
    assert "invoice_number" in field_dict
    assert "INV-2024-001" in field_dict["invoice_number"]
    assert "date" in field_dict
    assert "total" in field_dict


def test_invoice_mapper_document_type():
    mapper = InvoiceMapper()
    assert mapper.document_type() == "invoice"


def test_invoice_mapper_empty_text():
    mapper = InvoiceMapper()
    fields = mapper.map_fields("")
    assert fields == []
