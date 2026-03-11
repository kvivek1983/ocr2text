import re
from typing import Dict, List, Optional

from .base import BaseMapper

# Common field — appears on both sides, used as merge key
COMMON_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "regn no", "regn. number", "registration no", "reg no", "vehicle no",
        "reg. no", "regn. no", "regn number",
    ],
}

FRONT_FIELD_ALIASES: Dict[str, List[str]] = {
    "owner_name": ["registered owner", "owner's name", "owner name", "owner"],
    "father_name": [
        "son/wife/daughter of", "s/w/d of",
        "s/o", "d/o", "w/o", "son of", "daughter of", "wife of",
    ],
    "address": ["address", "permanent address", "present address"],
    "fuel_type": ["fuel type", "fuel used", "type of fuel", "fuel"],
    "registration_date": [
        "date of registration", "date of regn", "regn date", "date of reg", "reg date",
    ],
    "registration_validity": [
        "regn validity", "regn. validity", "registration validity",
        "as per fitness",
    ],
    "fitness_expiry": ["fitness upto", "fit upto", "fitness valid till", "valid till"],
    "tax_expiry": ["tax upto", "tax valid till", "tax paid upto"],
    "emission_norms": ["emission norms", "bharat stage", "emission standard"],
    "ownership": ["ownership"],
    "rto": [
        "rto", "registering authority", "registration authority", "reg. authority",
    ],
}

BACK_FIELD_ALIASES: Dict[str, List[str]] = {
    "vehicle_make": [
        "maker's name", "vehicle make", "manufacturer", "maker", "make",
    ],
    "vehicle_model": ["model name", "model", "vehicle model", "maker model"],
    "vehicle_type": [
        "vehicle class", "body type", "type of body", "veh. class",
    ],
    "color": ["colour", "color", "vehicle colour"],
    "seating_capacity": [
        "seating(in all) capacity", "seating capacity", "seating(in all)",
        "seats", "no. of seats", "seating cap",
    ],
    "engine_number": [
        "engine/motor no", "engine no", "engine number", "eng no", "eng. no",
    ],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
    ],
    "manufacturing_date": [
        "month-year of mfg", "month/year of mfg", "mfg date",
        "manufacturing date", "mfg. date", "month-year of mfg.",
    ],
    "unladen_weight": [
        "unladen/ laden weight", "unladen/laden weight",
        "unladen weight", "ulw", "unladen wt", "ul weight",
    ],
    "cubic_capacity": [
        "cubic cap.", "cubic capacity", "cubic cap", "cc", "engine cc",
    ],
    "wheelbase": ["wheel base", "wheelbase"],
    "cylinders": [
        "no. of cylinders", "no of cyl", "cylinders", "noof cyl",
    ],
    "hypothecation": ["hypothecation", "financier", "financer", "hp", "hypothecated to"],
    "insurance_validity": ["insurance upto", "insurance valid till", "ins. upto"],
    "standing_capacity": ["standing capacity"],
}

# Side detection indicators
FRONT_INDICATORS = [
    "owner", "address", "fuel", "son/wife/daughter",
    "s/o", "ownership", "emission norms",
]
BACK_INDICATORS = [
    "maker", "model", "cubic cap", "wheel base", "wheelbase",
    "cylinders", "unladen", "body type", "colour", "seating",
    "financier", "horse power",
]

FRONT_MANDATORY = [
    "registration_number", "owner_name", "fuel_type", "registration_date",
]
BACK_MANDATORY = ["registration_number", "vehicle_make", "engine_number", "chassis_number"]


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
                found = self._try_extract(alias, label, lines, used_labels)
                if found:
                    fields.append(found)
                    used_labels.add(label)
                    break

        return fields

    def _try_extract(
        self, alias: str, label: str, lines: List[str], used_labels: set
    ) -> Optional[Dict[str, str]]:
        """Try to extract a field value using an alias.

        Handles two patterns:
        1. Same-line: "Label: Value" or "Label Value"
        2. Next-line: Label on one line, value on the next line
        """
        if label in used_labels:
            return None

        escaped = re.escape(alias)
        # Pattern: alias followed by optional colon/dash, then value on same line
        same_line_pattern = re.compile(
            rf"(?i)(?:^|(?<=\s)){escaped}\s*[:\-.]?\s*(.+)",
        )
        # Pattern: alias is the entire line (or most of it) — value is on next line
        label_only_pattern = re.compile(
            rf"(?i)^\s*{escaped}\s*[:\-.]?\s*$",
        )

        for i, line in enumerate(lines):
            # Try same-line extraction first
            match = same_line_pattern.search(line)
            if match:
                value = match.group(1).strip()
                value = value.rstrip(":").rstrip("-").strip()
                # Reject if the captured value is just another label keyword
                if value and len(value) > 1 and not self._is_label_text(value):
                    return {"label": label, "value": value}

            # Try label-only pattern: value is on the next line
            if label_only_pattern.match(line) and i + 1 < len(lines):
                next_value = lines[i + 1].strip()
                next_value = next_value.rstrip(":").rstrip("-").strip()
                if next_value and len(next_value) > 1 and not self._is_label_text(next_value):
                    return {"label": label, "value": next_value}

        return None

    def _is_label_text(self, text: str) -> bool:
        """Check if text looks like a label rather than a value."""
        label_keywords = [
            "name", "number", "date", "type", "capacity", "weight",
            "authority", "norms", "upto", "validity",
        ]
        text_lower = text.lower().strip()
        # If the text is very short and matches a label keyword, skip it
        if len(text_lower) <= 6 and text_lower in label_keywords:
            return True
        return False

    def document_type(self) -> str:
        return "rc_book"
