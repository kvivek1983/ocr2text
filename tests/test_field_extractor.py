from app.core.field_extractor import FieldExtractor


def test_extract_key_value_pairs():
    raw_text = """Invoice No: INV-2024-001
Date: 15/01/2024
Total: Rs.1234.00
Vendor: ABC Corp"""

    extractor = FieldExtractor()
    fields = extractor.extract(raw_text)

    assert any(f["label"].lower() == "invoice no" and "INV-2024-001" in f["value"] for f in fields)
    assert any(f["label"].lower() == "date" and "15/01/2024" in f["value"] for f in fields)
    assert any(f["label"].lower() == "total" and "1234" in f["value"] for f in fields)


def test_extract_handles_multiline():
    raw_text = """BIG BAZAAR
MG Road, Bangalore
Grand Total: 913.50"""

    extractor = FieldExtractor()
    fields = extractor.extract(raw_text)

    assert any("grand total" in f["label"].lower() for f in fields)


def test_extract_empty_text():
    extractor = FieldExtractor()
    fields = extractor.extract("")
    assert fields == []
