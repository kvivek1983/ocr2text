import re
from typing import Dict, List

from .base import BaseMapper

RECEIPT_FIELD_ALIASES: Dict[str, List[str]] = {
    "vendor": [],
    "date": ["date", "dt", "bill date"],
    "total": ["grand total", "total", "amount", "net amount"],
    "subtotal": ["subtotal", "sub total"],
    "tax": ["tax", "gst", "vat", "cgst", "sgst"],
    "payment_method": ["cash", "card", "upi", "payment mode", "payment"],
    "bill_no": ["bill no", "receipt no", "invoice no"],
}


class ReceiptMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        # Vendor: first non-empty line
        for line in lines:
            line = line.strip()
            if line and not re.match(r"^[\d\s:/-]+$", line):
                fields.append({"label": "vendor", "value": line})
                used_labels.add("vendor")
                break

        # Extract key-value fields
        for label, aliases in RECEIPT_FIELD_ALIASES.items():
            if label in used_labels or not aliases:
                continue
            for alias in aliases:
                pattern = re.compile(
                    rf"(?i){re.escape(alias)}\s*[:\-]?\s*(.+)",
                )
                for line in lines:
                    match = pattern.search(line)
                    if match and label not in used_labels:
                        value = match.group(1).strip()
                        if value:
                            fields.append({"label": label, "value": value})
                            used_labels.add(label)
                            break
                if label in used_labels:
                    break

        return fields

    def document_type(self) -> str:
        return "receipt"
