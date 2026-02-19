import re
from typing import Dict, List

from .base import BaseMapper

RC_BOOK_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": ["registration no", "reg no", "vehicle no"],
    "owner_name": ["owner", "name"],
    "father_name": ["s/o", "d/o"],
    "address": ["address"],
    "vehicle_make": ["vehicle make", "make", "manufacturer"],
    "vehicle_model": ["model"],
    "vehicle_type": ["vehicle type", "type", "body type"],
    "fuel_type": ["fuel type", "fuel"],
    "engine_number": ["engine no"],
    "chassis_number": ["chassis no"],
    "registration_date": ["date of registration", "reg date"],
    "expiry_date": ["valid till", "fitness upto"],
    "seating_capacity": ["seating capacity", "seats"],
    "color": ["colour", "color"],
    "rto": ["rto"],
}


class RCBookMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in RC_BOOK_FIELD_ALIASES.items():
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
        return "rc_book"
