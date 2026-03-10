import re
from typing import Dict, List, Optional

from .base import BaseMapper

# Aliases for each field — order within each list matters (first match wins).
# Patterns are tried with flexible separator: optional colon/dash/dot + spaces.
RC_BOOK_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "regn. number", "regn number", "reg. no", "reg no",
        "registration no", "vehicle no", "regd. no", "regd no",
    ],
    "registration_date": [
        "date of regn", "date of reg", "date of registration",
        "reg date", "regd date", "date of regd",
    ],
    "registration_validity": [
        "regn. validity", "regn validity", "registration validity",
        "valid upto", "validity",
    ],
    "owner_name": [
        "owner name", "owner's name", "registered owner", "owner",
    ],
    "owner_serial_number": [
        "owner sr. no", "owner sr no", "owner serial no", "owner serial",
    ],
    "father_or_spouse_name": [
        "son/daughter/wife of", "son / wife / daughter of",
        "son/daughter of", "s/d/w of", "s/o", "d/o", "w/o", "s/d/o",
    ],
    "address": ["address"],
    "vehicle_class": [
        "vehicle class", "class of vehicle", "veh. class", "veh class",
    ],
    "body_type": [
        "body type",
    ],
    "vehicle_make": [
        "maker's name", "maker name", "vehicle make", "make",
        "manufacturer",
    ],
    "vehicle_model": [
        "model name", "model", "vehicle model",
    ],
    "fuel_type": [
        "fuel used", "fuel type", "type of fuel", "fuel",
    ],
    "engine_number": [
        "engine / motor number", "engine/motor number",
        "engine no", "eng. no", "eng no", "motor number",
    ],
    "chassis_number": [
        "chassis number", "chassis no", "ch. no", "ch no", "chasis no",
    ],
    "ownership_transfer_date": [
        "ownership tr. date", "ownership tr date", "ownership transfer date",
    ],
    "fitness_validity": [
        "fitness upto", "fitness valid till", "valid till",
    ],
    "seating_capacity": [
        "seating capacity", "seat cap", "seats",
        "seating (in all)", "seating",
    ],
    "color": ["colour", "color"],
    "emission_norms": [
        "emission norms", "emission norm", "bharat stage",
    ],
    "rto": [
        "registration authority", "registering authority", "rto",
    ],
    "financer_name": [
        "financer name", "financier name", "hypothecation",
    ],
    "cubic_capacity": [
        "cubic capacity", "cc",
    ],
    "horse_power": [
        "horse power", "hp", "bhp",
    ],
    "wheel_base": [
        "wheel base",
    ],
    "unladen_weight": [
        "unladen", "kerb weight",
    ],
    "laden_weight": [
        "laden", "gross vehicle weight",
    ],
    "number_of_cylinders": [
        "number of cylinders", "no. of cylinders", "cylinders",
    ],
    "month_year_of_manufacture": [
        "month-year of mfg", "month year of mfg", "year of manufacture",
        "year of mfg", "mfg year",
    ],
    "card_issue_date": [
        "card issue date",
    ],
    "state": ["state"],
}

# Direct regex patterns for fields that appear in well-known formats
# on Indian RC cards (smart-card or printed).
_DIRECT_PATTERNS: Dict[str, re.Pattern] = {
    # Registration numbers like GJ01DX6778, KA01AB1234, MH12DE5678
    "registration_number": re.compile(
        r"\b([A-Z]{2}\d{2}[A-Z]{0,3}\d{4})\b"
    ),
    # Chassis numbers: 17-char VIN or manufacturer-specific (>12 alphanumeric)
    "chassis_number": re.compile(
        r"\b([A-Z0-9]{12,17})\b"
    ),
    # Engine numbers: alphanumeric, typically 6-17 chars with mix of letters/digits
    "engine_number": re.compile(
        r"\b(\d[A-Z0-9]{5,16})\b"
    ),
}


class RCBookMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields: List[Dict[str, str]] = []
        lines = raw_text.strip().split("\n")
        used_labels: set = set()

        # Pass 1: alias-based key-value extraction
        for label, aliases in RC_BOOK_FIELD_ALIASES.items():
            value = _find_by_aliases(lines, aliases)
            if value and label not in used_labels:
                # Post-process specific fields
                value = _postprocess(label, value)
                if value:
                    fields.append({"label": label, "value": value})
                    used_labels.add(label)

        # Pass 2: fallback to direct pattern matching for critical fields
        for label, pattern in _DIRECT_PATTERNS.items():
            if label in used_labels:
                continue
            value = _find_by_pattern(lines, pattern)
            if value:
                fields.append({"label": label, "value": value})
                used_labels.add(label)

        # Pass 3: multi-line address assembly
        if "address" in used_labels:
            _expand_address(fields, lines)

        return fields

    def document_type(self) -> str:
        return "rc_book"


def _find_by_aliases(
    lines: List[str], aliases: List[str]
) -> Optional[str]:
    """Search lines for any alias and return the captured value.

    Handles two layouts:
      1. Label and value on the same line: "Reg. No.  GJ01DX6778"
      2. Label on one line, value on the next: "Chassis No.\\nMBJB2ZBT200037980"
    """
    for alias in aliases:
        # Build pattern: alias followed by optional separator, then value
        pattern = re.compile(
            rf"(?i)\b{re.escape(alias)}\.?\s*[:\-.]?\s*(.*)",
        )
        for i, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                # Strip trailing separators or noise
                value = re.sub(r"[:\-.\s]+$", "", value).strip()
                if value:
                    return value
                # Value on next line
                if i + 1 < len(lines):
                    next_val = lines[i + 1].strip()
                    if next_val:
                        return next_val
    return None


def _find_by_pattern(lines: List[str], pattern: re.Pattern) -> Optional[str]:
    """Find a value by direct regex across all lines."""
    for line in lines:
        match = pattern.search(line)
        if match:
            return match.group(1).strip()
    return None


def _postprocess(label: str, value: str) -> str:
    """Clean up extracted values based on field type."""
    if label == "registration_number":
        # Normalize spacing: "GJ 01 DX 6778" -> "GJ01DX6778"
        condensed = re.sub(r"\s+", "", value)
        reg_match = re.match(r"[A-Z]{2}\d{2}[A-Z]{0,3}\d{4}", condensed)
        if reg_match:
            return reg_match.group(0)
        return value

    if label in ("chassis_number", "engine_number"):
        # Extract the alphanumeric ID, stripping surrounding noise
        id_match = re.search(r"[A-Z0-9]{6,17}", value)
        if id_match:
            return id_match.group(0)
        return value

    if label == "registration_date":
        # Extract date portion (DD/MM/YYYY or similar)
        date_match = re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", value)
        if date_match:
            return date_match.group(0)
        return value

    if label == "owner_serial_number":
        num_match = re.search(r"\d+", value)
        if num_match:
            return num_match.group(0)
        return value

    if label == "fuel_type":
        # Normalize: "PET/CNG" stays, "Petrol" stays
        return value.upper() if "/" in value else value

    # For name fields, trim trailing noise from same-line keys
    if label in ("owner_name", "father_or_spouse_name"):
        # Stop at next key-value pair on same line (two+ spaces or tab)
        parts = re.split(r"\s{2,}|\t", value)
        return parts[0].strip()

    return value


def _expand_address(
    fields: List[Dict[str, str]], lines: List[str]
) -> None:
    """Assemble multi-line addresses.

    RC book addresses often span 2-3 lines. After the initial match,
    collect continuation lines until we hit another known field label.
    """
    addr_idx = next(
        (i for i, f in enumerate(fields) if f["label"] == "address"), None
    )
    if addr_idx is None:
        return

    current_addr = fields[addr_idx]["value"]

    # Find which line the address starts on
    addr_line_idx = None
    for i, line in enumerate(lines):
        if re.search(r"(?i)\baddress\b", line) and current_addr[:10] in line:
            addr_line_idx = i
            break

    if addr_line_idx is None:
        return

    # Collect continuation lines
    label_re = re.compile(
        r"(?i)^\s*("
        + "|".join(
            re.escape(a)
            for aliases in RC_BOOK_FIELD_ALIASES.values()
            for a in aliases
        )
        + r")\b"
    )
    extra_parts = []
    for line in lines[addr_line_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            break
        if label_re.match(stripped):
            break
        # Looks like continuation — alphanumeric, commas, typical address text
        if re.search(r"[A-Za-z]", stripped):
            extra_parts.append(stripped)
        else:
            break

    if extra_parts:
        full_address = current_addr.rstrip(",. ") + ", " + ", ".join(
            p.strip(",. ") for p in extra_parts
        )
        fields[addr_idx]["value"] = full_address
