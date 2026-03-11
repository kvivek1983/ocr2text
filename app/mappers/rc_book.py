import re
from typing import Dict, List, Optional, Set

from .base import BaseMapper

# Date pattern: DD-MM-YYYY, DD/MM/YYYY, MM-YYYY, etc.
_DATE_PATTERN = re.compile(
    r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'   # DD-MM-YYYY, DD/MM/YYYY
    r'|\d{1,2}[-/]\d{2,4}'              # MM-YYYY
    r'|\d{1,2}[A-Za-z]{3,9}[-/]?\d{4}' # 24Sep-2025, 24Sep2025
)

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
        "engine/motor no", "engine/motor number", "engine no", "engine number",
        "eng no", "eng. no",
        # OCR merged/period variants
        "engine/motor.no", "engine/motor.number",
        # OCR merged (no space)
        "engine/motorno",
    ],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
        # OCR merged variant
        "chassisno",
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
    "hypothecation": ["hypothecation", "financier", "financer", "financler", "hp", "hypothecated to"],
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
# Allow alphanumeric in middle segment to handle OCR misreads (e.g., T→1)
# Two alternatives: strict (letters-only middle) handles merged text better;
# OCR-tolerant (alphanumeric middle) handles misreads but requires word boundary
_REG_NUMBER_PATTERN = re.compile(
    r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})(?=\d*[A-Za-z]|\b)"
    r"|\b([A-Z]{2}\s*\d{1,2}\s*[A-Z0-9]{1,3}\s*\d{3,4})\b",
    re.IGNORECASE,
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

        lines = raw_text.strip().split("\n")

        # Try both line orderings and pick the better result
        # (handles rotated/upside-down images where OCR reads bottom-to-top)
        normal_fields = self._extract_fields(lines, side)
        reversed_fields = self._extract_fields(list(reversed(lines)), side)

        normal_score = self._score_extraction(normal_fields, side)
        reversed_score = self._score_extraction(reversed_fields, side)
        fields = reversed_fields if reversed_score > normal_score else normal_fields

        return fields

    @staticmethod
    def _score_extraction(fields: List[Dict[str, str]], side: str) -> float:
        """Score extraction quality to choose between normal and reversed line order.

        Scores based on: mandatory field count + field value plausibility.
        """
        mandatory = FRONT_MANDATORY if side == "front" else BACK_MANDATORY
        field_dict = {f["label"]: f["value"] for f in fields}
        score = 0.0

        # +10 per mandatory field found
        for m in mandatory:
            if m in field_dict:
                score += 10

        # +5 per non-mandatory field
        score += 5 * (len(fields) - sum(1 for f in fields if f["label"] in mandatory))

        # Value plausibility bonuses
        owner = field_dict.get("owner_name", "")
        if owner:
            # Owner name should be mostly letters/spaces, not a serial number
            alpha_ratio = sum(1 for c in owner if c.isalpha() or c == ' ') / max(len(owner), 1)
            score += 10 * alpha_ratio  # 0-10 bonus

        chassis = field_dict.get("chassis_number", "")
        if chassis:
            # VIN/chassis is typically 17 chars, alphanumeric
            if 15 <= len(chassis) <= 20:
                score += 5

        return score

    def _extract_fields(self, lines: List[str], side: str) -> List[Dict[str, str]]:
        """Core extraction logic on a list of lines."""
        if side == "back":
            side_aliases = BACK_FIELD_ALIASES
        else:
            side_aliases = FRONT_FIELD_ALIASES

        all_aliases = {**COMMON_FIELD_ALIASES, **side_aliases}

        fields = []
        used_labels: set = set()

        for label, aliases in all_aliases.items():
            if label in used_labels:
                continue
            for alias in aliases:
                found = self._try_extract(alias, label, lines, used_labels)
                if found:
                    fields.append(found)
                    used_labels.add(label)
                    break

        # Fallback extractions
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

        if side == "front" and "registration_date" not in used_labels:
            existing_values = {f["value"] for f in fields}
            found = self._fallback_registration_date(lines, existing_values)
            if found:
                fields.append(found)
                used_labels.add("registration_date")

        return fields

    # Fields that must match a date pattern
    _DATE_FIELDS: Set[str] = {
        "registration_date", "fitness_expiry",
        "tax_expiry", "manufacturing_date", "insurance_validity",
    }
    # Fields that must match a registration number pattern
    _REG_NUMBER_FIELDS: Set[str] = {"registration_number"}
    # Fields that must be numeric (small integers)
    _NUMERIC_FIELDS: Set[str] = {"cylinders", "seating_capacity"}

    def _validate_field_value(self, label: str, value: str) -> bool:
        """Field-specific validation to prevent wrong value extraction."""
        if label in self._DATE_FIELDS:
            return bool(_DATE_PATTERN.search(value))
        if label in self._REG_NUMBER_FIELDS:
            return bool(_REG_NUMBER_PATTERN.search(value))
        if label in self._NUMERIC_FIELDS:
            # Must contain at least one digit and be predominantly numeric
            stripped = value.strip()
            return bool(re.match(r'^\d{1,3}$', stripped))
        return True

    def _clean_field_value(self, label: str, value: str) -> str:
        """Extract clean value from merged OCR text (e.g., reg number + date on same line)."""
        if label in self._REG_NUMBER_FIELDS:
            match = _REG_NUMBER_PATTERN.search(value)
            if match:
                return (match.group(1) or match.group(2)).replace(" ", "")
        if label in self._DATE_FIELDS:
            match = _DATE_PATTERN.search(value)
            if match:
                return match.group(0)
        return value

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
                if value and len(value) > 1 and not self._is_label_or_descriptor(value, current_label=label):
                    if self._validate_field_value(label, value):
                        cleaned = self._clean_field_value(label, value)
                        return {"label": label, "value": cleaned}

            # Same-line failed or was rejected — look ahead up to 3 lines
            for offset in range(1, 4):
                if i + offset >= len(lines):
                    break
                next_value = lines[i + offset].strip()
                next_value = next_value.rstrip(":").rstrip("-").strip()
                # Skip empty lines, single-char lines, and label-like text
                if not next_value or len(next_value) <= 1:
                    continue
                if self._is_label_or_descriptor(next_value, current_label=label):
                    continue
                if not self._validate_field_value(label, next_value):
                    continue
                cleaned = self._clean_field_value(label, next_value)
                return {"label": label, "value": cleaned}

        return None

    def _is_label_or_descriptor(self, text: str, current_label: Optional[str] = None) -> bool:
        """Check if text looks like a label or descriptor rather than a value.

        Prevents extracting label text as field values when doing next-line lookahead.
        If current_label is provided, aliases belonging to that field are NOT
        treated as labels (they could be valid values for that field).
        """
        text_lower = text.lower().strip()

        # Short label keywords (exact match for short strings)
        label_keywords = [
            "name", "number", "date", "type", "capacity", "weight",
            "authority", "norms", "upto", "validity", "owner", "fuel",
            "maker", "model", "colour", "color", "address", "form",
            "serial",
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
            "hypothec", "insurance", "registration", "registralion", "emission", "cubic", "financler",
            "unladen", "wheel", "month", "standing", "body type", "vehicle",
            "son/wife", "son /wife", "son/", "s/w/d", "s/o", "d/o", "w/o",
            "card issue", "serial",
        ]
        for indicator in label_indicator_words:
            if text_lower.startswith(indicator):
                return True

        # Check if text matches any known field alias (it's a label, not a value)
        # Skip aliases belonging to current_label — those could be valid values
        all_alias_sets = [COMMON_FIELD_ALIASES, FRONT_FIELD_ALIASES, BACK_FIELD_ALIASES]
        for alias_dict in all_alias_sets:
            for field_label, aliases in alias_dict.items():
                if field_label == current_label:
                    continue
                for alias in aliases:
                    if text_lower == alias.lower():
                        return True

        return False

    def _fallback_registration_number(self, lines: List[str]) -> Optional[Dict[str, str]]:
        """Fallback: find registration number by regex pattern in the text."""
        for line in lines:
            match = _REG_NUMBER_PATTERN.search(line)
            if match:
                value = (match.group(1) or match.group(2)).replace(" ", "")
                # Validate: Indian reg numbers are 8-12 chars
                if 8 <= len(value) <= 12:
                    return {"label": "registration_number", "value": value}
        return None

    def _fallback_registration_date(
        self, lines: List[str], existing_values: Set[str]
    ) -> Optional[Dict[str, str]]:
        """Fallback: find registration date by looking for DD-MM-YYYY near date labels."""
        # Full date pattern: DD-MM-YYYY or DD/MM/YYYY
        full_date = re.compile(r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})')
        for line in lines:
            match = full_date.search(line)
            if match:
                date_val = match.group(1)
                # Skip dates already used by other fields
                if date_val in existing_values:
                    continue
                # Skip if the line looks like "card issue date"
                if "card issue" in line.lower():
                    continue
                return {"label": "registration_date", "value": date_val}
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
