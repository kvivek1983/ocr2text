import re
from typing import Dict, List

from .base import BaseMapper

PETROL_RECEIPT_FIELD_ALIASES: Dict[str, List[str]] = {
    "station_name": [],
    "station_address": [],
    "date": ["date"],
    "time": ["time"],
    "fuel_type": ["fuel", "product"],
    "quantity_liters": ["quantity", "qty", "liters", "litres"],
    "rate_per_liter": ["rate", "price", "unit price"],
    "total_amount": ["total amount", "net amount", "total", "amount"],
    "vehicle_number": ["vehicle no", "reg no"],
    "payment_mode": ["payment", "mode"],
    "bill_number": ["bill no", "receipt no", "transaction id"],
    "nozzle_number": ["nozzle", "dispenser", "pump no"],
}


class PetrolReceiptMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        # Station name: first non-empty line
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not re.match(r"^[\d\s:/-]+$", line_stripped):
                fields.append({"label": "station_name", "value": line_stripped})
                used_labels.add("station_name")
                break

        # Station address: second non-empty line (if it looks like an address)
        non_empty_lines = [l.strip() for l in lines if l.strip()]
        if len(non_empty_lines) > 1:
            second_line = non_empty_lines[1]
            if not re.match(r"(?i)^\s*(date|time|bill|fuel|qty|rate|total|vehicle|nozzle|payment)", second_line):
                fields.append({"label": "station_address", "value": second_line})
                used_labels.add("station_address")

        # Extract key-value fields
        for label, aliases in PETROL_RECEIPT_FIELD_ALIASES.items():
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
        return "petrol_receipt"
