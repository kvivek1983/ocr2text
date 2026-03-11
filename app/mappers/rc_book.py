import re
from typing import Dict, List, Optional

from .base import BaseMapper

# Common fields — appear on both sides (varies by state), used as merge key
COMMON_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "regn no", "regn. number", "registration no", "reg no", "vehicle no",
        "reg. no", "regn. no", "regn number",
        # OCR typo tolerance
        "regr number", "regr. number", "regr no",
    ],
    # Gujarat has engine/chassis on FRONT; other states on BACK — extract from either side
    "engine_number": [
        "engine/motor no", "engine no", "engine number", "eng no", "eng. no",
    ],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
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
        # OCR typo tolerance
        "registralion authority", "registralion authorily",
    ],
}

BACK_FIELD_ALIASES: Dict[str, List[str]] = {
    "vehicle_make": [
        "maker's name", "vehicle make", "manufacturer", "maker", "make",
    ],
    "vehicle_model": [
        "model name", "model namo", "vehicle model", "maker model", "model",
    ],
    "vehicle_type": [
        "vehicle class", "body type", "type of body", "veh. class",
    ],
    "color": ["colour", "color", "vehicle colour"],
    "seating_capacity": [
        "seating(in all) capacity", "seating capacity", "seating(in all)",
        "seats", "no. of seats", "seating cap",
        # OCR typo tolerance
        "seating(in all gapacity",
    ],
    "manufacturing_date": [
        "month-year of mfg", "month/year of mfg", "mfg date",
        "manufacturing date", "mfg. date", "month-year of mfg.",
        # OCR typo: merged text
        "month-yearofmfg",
    ],
    "unladen_weight": [
        "unladen/ laden weight", "unladen/laden weight",
        "unladen weight", "ulw", "unladen wt", "ul weight",
        # OCR typo: merged text
        "unladenladen weight",
    ],
    "cubic_capacity": [
        "cubic cap.", "cubic capacity", "cubic cap", "cc", "engine cc",
        # OCR typo
        "cublc cap",
    ],
    "wheelbase": ["wheel base", "wheelbase"],
    "cylinders": [
        "no. of cylinders", "no of cyl", "cylinders", "noof cyl",
        "no.of cylinders",
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

# Indian vehicle registration number pattern (e.g., GJ27TG4232, KA01AB1234)
_REG_NUMBER_PATTERN = re.compile(
    r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{3,5})\b", re.IGNORECASE
)

# Known fuel types for fallback extraction
_FUEL_TYPES = [
    "PETROL", "DIESEL", "CNG", "LPG", "ELECTRIC", "HYBRID",
    "PETROL/CNG", "PETROL/LPG", "DIESEL/CNG",
    "PETROLCNG", "PETROLLPG", "DIESELCNG",
]


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

        # Fallback extractions for fields that are hard to get via label matching
        if "registration_number" not in used_labels:
            found = self._fallback_registration_number(lines)
            if found:
                fields.append(found)
                used_labels.add("registration_number")

        if side == "front" and "fuel_type" not in used_labels:
            found = self._fallback_fuel_type(lines)
            if found:
                fields.append(found)
                used_labels.add("fuel_type")

        return fields

    def _try_extract(
        self, alias: str, label: str, lines: List[str], used_labels: set
    ) -> Optional[Dict[str, str]]:
        """Try to extract a field value using an alias.

        Handles two patterns:
        1. Same-line: "Label: Value" or "Label Value"
        2. Next-line: Label on one line, value on the next non-empty,
           non-label line (looks ahead up to 3 lines)
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
            # Check if this line contains our alias
            match = same_line_pattern.search(line)
            if not match and not label_only_pattern.match(line):
                continue

            # Try same-line extraction first
            if match:
                value = match.group(1).strip()
                value = value.rstrip(":").rstrip("-").strip()
                # Accept if it's a real value (not a label keyword or descriptor)
                if value and len(value) > 1 and not self._is_label_or_descriptor(value):
                    return {"label": label, "value": value}

            # Same-line failed or was rejected — look ahead up to 3 lines
            for offset in range(1, 4):
                if i + offset >= len(lines):
                    break
                next_value = lines[i + offset].strip()
                next_value = next_value.rstrip(":").rstrip("-").strip()
                # Skip empty lines, single-char lines, and label-like text
                if not next_value or len(next_value) <= 1:
                    continue
                if self._is_label_or_descriptor(next_value):
                    continue
                return {"label": label, "value": next_value}

        return None

    def _is_label_or_descriptor(self, text: str) -> bool:
        """Check if text looks like a label or descriptor rather than a value.

        Prevents extracting label text as field values when doing next-line lookahead.
        """
        text_lower = text.lower().strip()

        # Short label keywords (exact match for short strings)
        label_keywords = [
            "name", "number", "date", "type", "capacity", "weight",
            "authority", "norms", "upto", "validity", "owner", "fuel",
            "maker", "model", "colour", "color", "address", "form",
        ]
        if len(text_lower) <= 8 and text_lower in label_keywords:
            return True

        # Descriptor phrases in parentheses (e.g., "(In case of Individual Owner)")
        if text_lower.startswith("(") and text_lower.endswith(")"):
            return True

        # Known field label prefixes — if the line starts with any of these,
        # it's likely a label, not a value
        label_indicator_words = [
            "regn", "reg ", "regr", "date of", "valid", "upto", "authority",
            "in case of", "norms", "fitness", "owner", "fuel", "address",
            "maker", "model", "chassis", "engine", "seating", "financier",
            "hypothec", "insurance", "registration", "emission", "cubic",
            "unladen", "wheel", "month", "standing", "body type", "vehicle",
            "son/wife", "s/w/d", "s/o", "d/o", "w/o",
        ]
        for indicator in label_indicator_words:
            if text_lower.startswith(indicator):
                return True

        # Check if text matches any known field alias (it's a label, not a value)
        all_alias_sets = [COMMON_FIELD_ALIASES, FRONT_FIELD_ALIASES, BACK_FIELD_ALIASES]
        for alias_dict in all_alias_sets:
            for aliases in alias_dict.values():
                for alias in aliases:
                    if text_lower == alias.lower():
                        return True

        return False

    def _fallback_registration_number(self, lines: List[str]) -> Optional[Dict[str, str]]:
        """Fallback: find registration number by regex pattern in the text."""
        for line in lines:
            match = _REG_NUMBER_PATTERN.search(line)
            if match:
                value = match.group(1).replace(" ", "")
                # Validate: Indian reg numbers are 8-12 chars
                if 8 <= len(value) <= 12:
                    return {"label": "registration_number", "value": value}
        return None

    def _fallback_fuel_type(self, lines: List[str]) -> Optional[Dict[str, str]]:
        """Fallback: find fuel type by matching known fuel type values."""
        for line in lines:
            line_upper = line.strip().upper()
            for fuel in _FUEL_TYPES:
                if fuel == line_upper or line_upper == fuel.replace("/", ""):
                    # Normalize merged OCR text back to standard form
                    normalized = fuel if "/" in fuel else self._normalize_fuel(line_upper)
                    return {"label": "fuel_type", "value": normalized}
        return None

    @staticmethod
    def _normalize_fuel(text: str) -> str:
        """Normalize merged fuel strings like PETROLCNG -> PETROL/CNG."""
        mappings = {
            "PETROLCNG": "PETROL/CNG",
            "PETROLLPG": "PETROL/LPG",
            "DIESELCNG": "DIESEL/CNG",
        }
        return mappings.get(text, text)

    def document_type(self) -> str:
        return "rc_book"
