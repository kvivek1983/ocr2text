import re
from typing import Dict, List, Optional

from .base import BaseMapper

# Common field — appears on both sides, used as merge key
COMMON_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "registration no", "regn no", "reg no", "vehicle no",
        "reg. no", "regn. no",
    ],
}

FRONT_FIELD_ALIASES: Dict[str, List[str]] = {
    "owner_name": ["registered owner", "owner's name", "owner name", "owner"],
    "father_name": ["s/o", "d/o", "w/o", "s/w/d of", "son of", "daughter of", "wife of"],
    "address": ["address", "permanent address", "present address"],
    "vehicle_make": [
        "maker's name", "vehicle make", "manufacturer", "maker", "make",
    ],
    "vehicle_model": ["model", "vehicle model", "maker model"],
    "fuel_type": ["fuel type", "fuel used", "type of fuel", "fuel"],
    "vehicle_type": ["body type", "vehicle class", "type of body", "veh. class"],
    "color": ["colour", "color", "vehicle colour"],
    "seating_capacity": ["seating capacity", "seats", "no. of seats", "seating cap"],
    "registration_date": [
        "date of registration", "regn date", "date of reg", "reg date",
    ],
    "fitness_expiry": ["fitness upto", "fit upto", "fitness valid till", "valid till"],
    "tax_expiry": ["tax upto", "tax valid till", "tax paid upto"],
    "rto": ["rto", "registering authority", "registration authority", "reg. authority"],
}

BACK_FIELD_ALIASES: Dict[str, List[str]] = {
    "engine_number": ["engine no", "engine number", "eng no", "eng. no"],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
    ],
    "manufacturing_date": [
        "mfg date", "manufacturing date", "month/year of mfg", "mfg. date",
    ],
    "unladen_weight": ["unladen weight", "ulw", "unladen wt", "ul weight"],
    "cubic_capacity": ["cubic capacity", "cc", "engine cc", "cubic cap"],
    "wheelbase": ["wheelbase", "wheel base"],
    "cylinders": ["no of cyl", "cylinders", "no. of cylinders", "noof cyl"],
    "emission_norms": ["emission norms", "bs", "bharat stage", "emission standard"],
    "hypothecation": ["hypothecation", "financer", "hp", "hypothecated to"],
    "insurance_validity": ["insurance upto", "insurance valid till", "ins. upto"],
    "standing_capacity": ["standing capacity"],
}

# Side detection indicators (fields unique to each side, excluding registration_number)
FRONT_INDICATORS = ["owner", "address", "fuel type", "body type", "colour", "seating"]
BACK_INDICATORS = ["engine no", "chassis no", "cubic capacity", "wheelbase", "cylinders", "unladen weight"]

FRONT_MANDATORY = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
BACK_MANDATORY = ["registration_number", "engine_number", "chassis_number"]


def _detect_side(raw_text: str) -> str:
    """Auto-detect front vs back based on field indicators in OCR text."""
    text_lower = raw_text.lower()
    front_score = sum(1 for ind in FRONT_INDICATORS if ind in text_lower)
    back_score = sum(1 for ind in BACK_INDICATORS if ind in text_lower)
    return "back" if back_score > front_score else "front"


class RCBookMapper(BaseMapper):
    def map_fields(self, raw_text: str, side: Optional[str] = None) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        # Auto-detect side if not provided
        if side is None:
            side = _detect_side(raw_text)

        # Select field set based on side
        if side == "back":
            side_aliases = BACK_FIELD_ALIASES
        else:
            side_aliases = FRONT_FIELD_ALIASES

        # Always include common fields
        all_aliases = {**COMMON_FIELD_ALIASES, **side_aliases}

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in all_aliases.items():
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
                        # Strip trailing colons and extra whitespace
                        value = value.rstrip(":").strip()
                        if value:
                            fields.append({"label": label, "value": value})
                            used_labels.add(label)
                            break
                if label in used_labels:
                    break

        return fields

    def document_type(self) -> str:
        return "rc_book"
