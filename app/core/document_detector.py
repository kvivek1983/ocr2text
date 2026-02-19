from typing import Dict, List, Tuple


DOCUMENT_SIGNATURES: Dict[str, List[str]] = {
    "receipt": [
        "TOTAL", "CASH", "CHANGE", "GST", "ITEMS", "QTY", "MRP",
        "SUBTOTAL", "BILL", "GRAND TOTAL",
    ],
    "invoice": [
        "INVOICE", "DUE DATE", "BILL TO", "PO NUMBER", "SUBTOTAL",
        "INVOICE NO", "TAX INVOICE",
    ],
    "driving_license": [
        "DL NO", "LICENCE", "DRIVING", "VALID TILL", "DOB", "CLASS",
        "RTO", "MCWG", "LMV", "TRANSPORT",
    ],
    "rc_book": [
        "REGISTRATION", "RC", "CHASSIS", "ENGINE NO", "OWNER",
        "VEHICLE", "FUEL TYPE", "REGISTERING AUTHORITY",
    ],
    "insurance": [
        "POLICY", "INSURER", "IDV", "PREMIUM", "INSURANCE",
        "COVER NOTE", "THIRD PARTY", "COMPREHENSIVE",
    ],
    "petrol_receipt": [
        "PETROL", "DIESEL", "FUEL", "LITRE", "LITER", "RATE",
        "PUMP", "NOZZLE",
    ],
    "odometer": [
        "KM", "KILOMETER", "ODOMETER", "READING", "SPEEDOMETER",
    ],
    "fuel_pump_reading": [
        "PUMP", "READING", "START", "END", "NOZZLE", "DISPENSER",
        "OPENING", "CLOSING", "DISPENSED",
    ],
}


class DocumentDetector:
    """Detect document type from raw OCR text using signature field matching."""

    def __init__(self):
        self.signatures = DOCUMENT_SIGNATURES

    def detect(self, raw_text: str) -> Tuple[str, float]:
        """
        Detect document type from raw text.
        Returns (document_type, confidence).
        """
        text_upper = raw_text.upper()
        best_type = "unknown"
        best_score = 0.0
        best_matches = 0

        for doc_type, keywords in self.signatures.items():
            matches = sum(1 for kw in keywords if kw in text_upper)
            if matches >= 2:
                score = matches / len(keywords)
                if matches > best_matches or (
                    matches == best_matches and score > best_score
                ):
                    best_type = doc_type
                    best_score = score
                    best_matches = matches

        if best_type == "unknown":
            return ("unknown", 0.0)

        return (best_type, round(best_score, 2))
