from app.core.document_detector import DocumentDetector


def test_detect_receipt(sample_raw_text_receipt):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_receipt)
    assert doc_type == "receipt"
    assert confidence > 0.5


def test_detect_invoice(sample_raw_text_invoice):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_invoice)
    assert doc_type == "invoice"
    assert confidence > 0.5


def test_detect_driving_license(sample_raw_text_driving_license):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_driving_license)
    assert doc_type == "driving_license"
    assert confidence > 0.5


def test_detect_rc_book(sample_raw_text_rc_book):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_rc_book)
    assert doc_type == "rc_book"
    assert confidence > 0.5


def test_detect_insurance(sample_raw_text_insurance):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_insurance)
    assert doc_type == "insurance"
    assert confidence > 0.5


def test_detect_petrol_receipt(sample_raw_text_petrol_receipt):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_petrol_receipt)
    assert doc_type == "petrol_receipt"
    assert confidence > 0.5


def test_detect_odometer(sample_raw_text_odometer):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_odometer)
    assert doc_type == "odometer"
    assert confidence > 0.5


def test_detect_fuel_pump(sample_raw_text_fuel_pump):
    detector = DocumentDetector()
    doc_type, confidence = detector.detect(sample_raw_text_fuel_pump)
    assert doc_type == "fuel_pump_reading"
    assert confidence > 0.5


def test_detect_unknown():
    detector = DocumentDetector()
    doc_type, confidence = detector.detect("random text with no keywords")
    assert doc_type == "unknown"
    assert confidence == 0.0
