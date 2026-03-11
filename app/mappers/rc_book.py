import re
from typing import Dict, List, Optional, Set

from .base import BaseMapper

# Date pattern: DD-MM-YYYY, DD/MM/YYYY, MM-YYYY, etc.
# OCR typos for month names: Scp→Sep
_MONTH_NAMES = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Scp|Oct|Nov|Dec)'
_DATE_PATTERN = re.compile(
    r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'                  # DD-MM-YYYY, DD/MM/YYYY
    r'|\d{1,2}[-/]\d{2,4}'                             # MM-YYYY
    rf'|\d{{1,2}}[-/]?{_MONTH_NAMES}[-/]?\d{{4}}',    # 24Sep-2025, 24Sep2025, 15-Jan-2026
    re.IGNORECASE,
)
# Strict date pattern for validation — requires 4-digit year to avoid garbled partial dates
_STRICT_DATE_PATTERN = re.compile(
    r'\d{1,2}[-/]\d{1,2}[-/]\d{4}'                    # DD-MM-YYYY
    r'|\d{1,2}[-/]\d{4}'                               # MM-YYYY (4-digit year only)
    rf'|\d{{1,2}}[-/]?{_MONTH_NAMES}[-/]?\d{{4}}',    # DD-Mon-YYYY
    re.IGNORECASE,
)

# Common fields — appear on both sides (varies by state), used as merge key
COMMON_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "regn no", "regn. number", "registration no", "reg no", "vehicle no",
        "reg. no", "regn. no", "regn number",
        # mParivahan / digital RC format
        "vehicle number", "reg no :",
        # OCR typo tolerance
        "regr number", "regr. number", "regr no",
        "vchiclo number", "vchicle number",
        # Form 23 / OCR typo variants
        "roglstratlon",
    ],
    # Gujarat has engine/chassis on FRONT; other states on BACK — extract from either side
    "engine_number": [
        "engine/motor no", "engine/motor number", "engine no", "engine number",
        "eng no", "eng. no",
        # MH format: spaces around slash
        "engine / motor no", "engine / motor number",
        # mParivahan digital RC / KA format
        "engine no.", "engine/motor number.",
        # OCR merged/period variants
        "engine/motor.no", "engine/motor.number",
        # OCR merged (no space)
        "engine/motorno",
        # Form 23 variants
        "engineno", "engineno.",
    ],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
        # MH format: space before "number"
        "chassis number ",
        # mParivahan / KA format
        "chassis no.",
        # OCR merged variant
        "chassisno",
    ],
}

FRONT_FIELD_ALIASES: Dict[str, List[str]] = {
    "owner_name": [
        "registered owner", "owner's name", "owner name",
        # OCR typo tolerance
        "owncr name", "owncrname", "ownername",
        # mParivahan / virtual RC typos
        "owncr namo", "owncrname",
        # UP paper RC format typos ("C" for "O", "f" for "e")
        "cwnor nama", "cwnor name", "ownrf name", "ownrf nama",
        # TN format typos ("Q" for "O")
        "qwner name", "qwnername",
        # KA format
        "ownername",
        # UP format ("OwName" merged OCR)
        "owname",
        # GJ/TN format OCR typos ("Owier", "Owncr", "Ownor")
        "owier name", "owier",
        "ownor name", "ownorname", "ownor",
        # MH format OCR merge ("OwnerNarne" = Owner Name with 'rn'→'rn' merge)
        "ownernarne", "ownernarme",
        # Short alias last (most greedy)
        "owner",
    ],
    "father_name": [
        "son/wife/daughter of", "s/w/d of",
        "s/o", "d/o", "w/o", "son of", "daughter of", "wife of",
    ],
    "address": ["address", "permanent address", "present address"],
    "fuel_type": [
        "fuel type", "fuel used", "type of fuel",
        # mParivahan / KA format
        "fuel",
        # OCR typos for "Fuel"
        "ftel", "fues", "fue",
    ],
    "registration_date": [
        "date of registration", "date of regn", "regn date", "date of reg", "reg date",
        # mParivahan / digital RC format
        "registration date",
        # KA old format
        "rec.date", "rec. date",
        # OCR typo (Registratlon with transposed chars)
        "registration dato", "registratlon date", "registraton date",
        # Heavily garbled OCR labels (UP paper format)
        "dafo of rogh", "dafo of regn",
        # TN format: merged label with no spaces
        "dateofregn",
    ],
    "registration_validity": [
        "regn validity", "regn. validity", "registration validity",
        # OCR typo: double-l "Valldity"
        "regn. valldity", "regn valldity",
        # MH format: validity is "As per Fitness" (no fixed date)
        "as per fitness", "as par fitness",
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
        "maker's name", "vehicle make", "manufacturer", "maker",
        # mParivahan / digital RC format
        "maker name",
        # KA old paper booklet format
        "mfr",
        # OCR typos for "Maker's Name"
        "makor's namo", "makor's name", "maker's namo",
        # OCR splits "Maker's Name" across lines — match partial
        "maker's namex", "maker' s name",
        # OCR "Maters Name" / "Mater's Name" (GJ format typo)
        "maters name", "mater's name",
        # OCR drops the 'r' from "Maker's" → "Make's Name"
        "make's name",
        # "make" removed — too greedy, matches inside "Maker's Name" → "r's Name"
    ],
    "vehicle_model": [
        "model name", "model namo", "model namie", "vehicle model", "maker model", "model",
    ],
    "vehicle_type": [
        "vehicle class", "body type", "type of body", "veh. class",
    ],
    "color": ["colour", "color", "vehicle colour"],
    "seating_capacity": [
        "seating(in all) capacity", "seating capacity", "seating(in all)",
        # MH format: spaces around parens
        "seating (in all)", "seating (in all) / standing", "seating (in a)",
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
# Engine/chassis are COMMON fields (front for MH/GJ, back for some other states)
# Back mandatory: only fields reliably present on back across all state formats
BACK_MANDATORY = ["registration_number", "vehicle_make"]

# Valid Indian state/UT registration code prefixes
_VALID_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ",
    "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP",
    "MZ", "NL", "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK",
    "UP", "UT", "WB",
}

# Indian vehicle registration number pattern (e.g., GJ27TG4232, KA01AB1234)
# Allow alphanumeric in middle segment to handle OCR misreads (e.g., T→1)
# Two alternatives: strict (letters-only middle) handles merged text better;
# OCR-tolerant (alphanumeric middle) handles misreads but requires word boundary
_REG_NUMBER_PATTERN = re.compile(
    r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})(?=\d+[-/]|\d*[A-Za-z]|\b)"
    r"|\b([A-Z]{2}\s*\d{1,2}\s*[A-Z0-9]{1,3}\s*\d{3,4})\b",
    re.IGNORECASE,
)

# Known fuel types for fallback extraction
_FUEL_TYPES = [
    "PETROL", "DIESEL", "CNG", "LPG", "ELECTRIC", "HYBRID",
    "PETROL/CNG", "PETROL/LPG", "DIESEL/CNG",
    "PETROLCNG", "PETROLLPG", "DIESELCNG",
    # OCR typos (G→O, G→6, etc.)
    "PETROLCNO", "PETROL/CNO",
    # OCR 'I' or 'U' for '/' between PETROL and CNG
    "PETROLICNG", "PETROUCNG", "PETROLILPG",
    # OCR 'Q' for 'O' in PETROL
    "PETRQL",
    # E20 ethanol blend variants (OCR garbled)
    "PETROL(E20)/CNG", "PETROL(E20)CNG",
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

        vehicle_make = field_dict.get("vehicle_make", "")
        if vehicle_make:
            # Vehicle make should be a reasonable name (>=5 chars, mostly alpha)
            if len(vehicle_make) >= 5:
                score += 5
            else:
                score -= 10  # penalize implausibly short make values like "r's Name"
            # Multi-word makes look more like real company names (e.g. "MARUTI SUZUKI INDIA LTD")
            if ' ' in vehicle_make:
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
    # Fields that must be numeric (decimals/integers, e.g. 1462.00 or 2740)
    _NUMERIC_DECIMAL_FIELDS: Set[str] = {"cubic_capacity", "wheelbase", "unladen_weight"}

    # Fields that must look like a VIN/chassis (alphanumeric, 15-20 chars)
    _VIN_FIELDS: Set[str] = {"chassis_number"}

    def _validate_field_value(self, label: str, value: str) -> bool:
        """Field-specific validation to prevent wrong value extraction."""
        if label in self._DATE_FIELDS:
            return bool(_STRICT_DATE_PATTERN.search(value))
        if label in self._REG_NUMBER_FIELDS:
            match = _REG_NUMBER_PATTERN.search(value)
            if not match:
                return False
            # Validate state code prefix
            reg = (match.group(1) or match.group(2)).replace(" ", "").upper()
            return reg[:2] in _VALID_STATE_CODES
        if label in self._NUMERIC_FIELDS:
            stripped = value.strip()
            return bool(re.match(r'^\d{1,3}$', stripped))
        if label in self._NUMERIC_DECIMAL_FIELDS:
            stripped = value.strip()
            # Must START with a digit — e.g. "1462.00", "2740", "1197 CC", "875 KG"
            # Reject label fragments like "/ Horse Power(BHP/Kw)" that start with non-digits
            return bool(re.match(r'^\d', stripped))
        if label in self._VIN_FIELDS:
            stripped = re.sub(r'[\s.\-~]', '', value)
            # VIN/chassis: 15-22 alphanumeric chars, not a date or reg number
            if not (15 <= len(stripped) <= 22 and re.match(r'^[A-Z0-9]+$', stripped, re.IGNORECASE)):
                return False
            # Reject if it looks like a date
            if _DATE_PATTERN.search(value):
                return False
            return True
        if label == "vehicle_make":
            v = value.strip().lower()
            # Reject label fragments
            if v.startswith("'s") or v.startswith("s.name") or v.startswith("n ") or "financer" in v or "financier" in v:
                return False
            # Reject vehicle class/type labels (e.g. "Vehicle Class: Motor Cab (LPV)")
            if "class" in v or "motor cab" in v or "body type" in v:
                return False
            # Reject if it looks like a registration number
            if _REG_NUMBER_PATTERN.search(value):
                return False
            # Reject if entirely non-alphanumeric (e.g. "......" from garbled OCR)
            if not re.search(r'[A-Za-z0-9]', value):
                return False
            # Reject if starts with non-letter/non-digit (e.g. "#gasbabon Aurarty")
            if not re.match(r'^[A-Za-z0-9]', value.strip()):
                return False
            # Reject if starts with a digit (vehicle makes start with letters)
            if re.match(r'^\d', value.strip()):
                return False
            # Reject if all digits (not a vehicle make)
            if re.match(r'^\d+$', value.strip()):
                return False
            # Reject if first 3 chars contain a digit (e.g. "G01MT0071" = garbled reg number)
            prefix = value.strip()[:3]
            if len(prefix) >= 2 and re.search(r'\d', prefix):
                return False
        if label == "registration_validity":
            v = value.strip().lower()
            # Accept date values OR "as per fitness" (MH format)
            if _DATE_PATTERN.search(value):
                return True
            if "fitness" in v or "as per" in v:
                return True
            return False
        if label == "emission_norms":
            v = value.strip().upper()
            # Must contain a known emission standard keyword
            if not any(kw in v for kw in ["BHARAT", "BS", "EURO", "STAGE"]):
                return False
        if label == "fuel_type":
            v = value.strip().upper()
            # Must contain a known fuel keyword
            if not any(kw in v for kw in ["PETROL", "DIESEL", "CNG", "LPG", "ELECTRIC", "HYBRID"]):
                return False
        if label == "owner_name":
            v = value.strip()
            # Reject implausibly short names (label fragments like "Namr", "Name", "ship.", etc.)
            if len(v) < 6:
                return False
            # Reject if it looks like a date
            if _DATE_PATTERN.search(v):
                return False
            # Reject if it looks like an engine/chassis number (mixed letters+digits, no spaces)
            if len(v) >= 10 and ' ' not in v and re.search(r'\d', v) and re.match(r'^[A-Z0-9.]+$', v, re.IGNORECASE):
                return False
            # Reject fitness-related values
            if "fitness" in v.lower() or "fltness" in v.lower():
                return False
            # Reject OCR-truncated label fragments (e.g. "gine/Motor Number", "ner Name")
            if re.search(r'(?i)(motor|engine|number|chassis|regn|reg\.)', v):
                return False
        return True

    def _clean_field_value(self, label: str, value: str) -> str:
        """Extract clean value from merged OCR text (e.g., reg number + date on same line)."""
        if label in self._VIN_FIELDS:
            return re.sub(r'[\s.\-~]', '', value).upper()
        if label in self._REG_NUMBER_FIELDS:
            match = _REG_NUMBER_PATTERN.search(value)
            if match:
                return (match.group(1) or match.group(2)).replace(" ", "")
        if label in self._DATE_FIELDS:
            match = _DATE_PATTERN.search(value)
            if match:
                return match.group(0)
        if label == "fuel_type":
            return self._normalize_fuel(value.strip())
        if label == "owner_name":
            # Strip trailing "Son/Wife/Daughter of" merged text (with or without preceding space)
            cleaned = re.split(r'(?i)\s*son.{0,6}w[il]|\s*[Ss]\s*/\s*[Ww]\s*/\s*[Dd]', value)[0].strip()
            return cleaned if cleaned else value
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
        # Pattern: alias followed by optional colon/dash, then value on same line.
        # (?!\w) prevents alias from matching as prefix of a longer word
        # (e.g., "owner" should not match "Ownership" line → captures "ship." as value)
        same_line_pattern = re.compile(
            rf"(?i)(?:^|(?<=\s)){escaped}(?!\w)\s*[:\-.]?\s*(.+)",
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
                # Strip leading/trailing colons, dashes, semicolons (OCR artifacts)
                value = re.sub(r'^[:\-.\s;]+', '', value).rstrip(":.-;").strip()
                # Accept if it's a real value (not a label keyword or descriptor)
                if value and len(value) > 1 and not self._is_label_or_descriptor(value, current_label=label):
                    if self._validate_field_value(label, value):
                        cleaned = self._clean_field_value(label, value)
                        return {"label": label, "value": cleaned}

            # Special case: alias text IS also the value (e.g. "As per Fitness" for registration_validity)
            # Only applies when the alias itself passes a strict field validator
            if label == "registration_validity":
                alias_as_value = alias.strip().title()
                if "fitness" in alias_as_value.lower() or "as per" in alias_as_value.lower():
                    return {"label": label, "value": alias_as_value}

            # Same-line failed or was rejected — look ahead up to 5 lines
            for offset in range(1, 6):
                if i + offset >= len(lines):
                    break
                next_value = lines[i + offset].strip()
                next_value = re.sub(r'^[:\-.\s;]+', '', next_value).rstrip(":.-;").strip()
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
            "serial", "na", "nil", "details", "active", "status",
        ]
        if len(text_lower) <= 8 and text_lower in label_keywords:
            return True

        # Descriptor phrases in parentheses (e.g., "(In case of Individual Owner)")
        stripped = text_lower.rstrip(".,;:")
        if stripped.startswith("(") and stripped.endswith(")"):
            return True
        # "In case of" descriptor without parentheses
        # Exception: owner_name values may contain "son/wife/daughter of (in case of individual owner)"
        # which is cleaned away by _clean_field_value — don't reject those here
        if current_label != "owner_name" and ("in case of" in text_lower or "in cse of" in text_lower):
            return True

        # Known field label prefixes — if the line starts with any of these,
        # it's likely a label, not a value
        label_indicator_words = [
            "regn", "reg ", "regr", "date of", "valid", "upto", "authority",
            "in case of", "norms", "fitness", "owner", "fuel", "address",
            "maker", "model", "chassis", "engine", "seating", "financier",
            "hypothec", "insurance", "registration", "registralion", "emission", "cubic", "financler",
            "owncr", "ownername", "ownernamr", "owncrname", "ownrf", "owname", "owier", "ownor", "horse power", "bhp",
            "cardissue", "card issue date",  # OCR merging of "Card Issue Date"
            "sharat stage", "bharat stage",  # Emission norm values mistaken for owner_name
            "card ", "card tsw", "sertal",  # OCR garbling of "Card Issue Date" / "Serial"
            "wheet",  # OCR typo for "wheel" (e.g. "Wheet Base(mm)")
            "hsrp", "front.hsrp", "rear.hsrp",  # High Security Registration Plate labels
            "carg", "card issue", "petrol", "diesel", "cng", "lpg", "electric",
            "individual", "asper",
            "'s.name", "'sname", "s.name",
            "unladen", "wheel", "month", "standing", "body type",
            "vehicle", "vehide", "vehcle", "vehile",  # OCR typos for "vehicle"
            "son/wife", "son /wife", "son/", "s/w/d", "s/o", "d/o", "w/o",
            "card issue", "serial",
            "registration authority", "registralion authority", "registratlon authority",
            "registering authority", "registrelton",  # OCR garbling of "Registration"
            "dy rto", "rto ", "financer name", "financer ", "number of",
            "aeyn",  # OCR garbling of "Regn" (e.g. "Aeyn Nunber" = "Regn. Number")
            "cubic cap", "horse power", "bhp", "kw",
            # mParivahan / digital RC labels
            "mobile no", "ownership", "vehicle age", "vehicle status",
            "emission norm", "fitness valid", "tax valid", "insurance valid",
            "pucc", "permit valid", "seat capacity", "standing capacity",
            "vehicle description",
            # KA format labels
            "sayd of", "body", "no.of cyl", "unladenwt", "mfg.date", "seating",
            "stdgislfr", "reg/fc upto",
            # Weight/dimension labels
            "gross", "laden", "unladen weight", "gross vehicle", "gross comb",
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
                # Validate: Indian reg numbers are 8-12 chars with valid state code
                if 8 <= len(value) <= 12 and value[:2].upper() in _VALID_STATE_CODES:
                    return {"label": "registration_number", "value": value}
        return None

    def _fallback_registration_date(
        self, lines: List[str], existing_values: Set[str]
    ) -> Optional[Dict[str, str]]:
        """Fallback: find registration date by looking for DD-MM-YYYY near date labels."""
        # Full date pattern: DD-MM-YYYY, DD/MM/YYYY, or DDMmm-YYYY (e.g. 24Sep-2025)
        full_date = re.compile(
            rf'(\d{{1,2}}[-/]\d{{1,2}}[-/]\d{{4}}|\d{{1,2}}{_MONTH_NAMES}[-/]?\d{{4}})',
            re.IGNORECASE,
        )
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
        # Pass 1: exact line match
        for line in lines:
            line_upper = line.strip().upper()
            for fuel in _FUEL_TYPES:
                if fuel == line_upper or line_upper == fuel.replace("/", ""):
                    normalized = fuel if "/" in fuel else self._normalize_fuel(line_upper)
                    return {"label": "fuel_type", "value": normalized}
        # Pass 2: regex extraction from merged/garbled lines
        fuel_regex = re.compile(
            r'(PETROL|DIESEL)\s*(?:[\(/]?E\d+.{0,2})?\s*[/\\]?\s*(CNG|LPG)',
            re.IGNORECASE,
        )
        single_fuel = re.compile(r'\b(PETROL|DIESEL|CNG|LPG|ELECTRIC|HYBRID)\b', re.IGNORECASE)
        for line in lines:
            m = fuel_regex.search(line)
            if m:
                return {"label": "fuel_type", "value": f"{m.group(1).upper()}/{m.group(2).upper()}"}
        # Pass 3: single fuel type anywhere in text
        for line in lines:
            m = single_fuel.search(line)
            if m:
                return {"label": "fuel_type", "value": m.group(1).upper()}
        return None

    @staticmethod
    def _normalize_fuel(text: str) -> str:
        """Normalize merged fuel strings like PETROLCNG -> PETROL/CNG."""
        mappings = {
            "PETROLCNG": "PETROL/CNG",
            "PETROLCNO": "PETROL/CNG",
            "PETROLICNG": "PETROL/CNG",  # OCR 'I' for '/'
            "PETROUCNG": "PETROL/CNG",   # OCR 'U' for '/'
            "PETRQL": "PETROL",          # OCR 'Q' for 'O'
            "PETROLLPG": "PETROL/LPG",
            "PETROLILPG": "PETROL/LPG",  # OCR 'I' for '/'
            "DIESELCNG": "DIESEL/CNG",
        }
        return mappings.get(text, text)

    def document_type(self) -> str:
        return "rc_book"
