import re
from typing import Dict, List

from .base import BaseMapper

INVOICE_FIELD_ALIASES: Dict[str, List[str]] = {
    "invoice_number": ["invoice no", "inv no", "invoice #", "bill no"],
    "date": ["date", "invoice date"],
    "due_date": ["due date", "payment due"],
    "vendor": ["from", "seller", "company", "supplier"],
    "customer": ["to", "bill to", "customer", "buyer"],
    "subtotal": ["subtotal", "taxable amount"],
    "tax": ["tax", "gst", "vat", "igst"],
    "total": ["total", "amount due", "grand total", "net payable"],
    "gstin": ["gstin", "gst no", "tax id"],
}


class InvoiceMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in INVOICE_FIELD_ALIASES.items():
            if label in used_labels:
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
        return "invoice"
