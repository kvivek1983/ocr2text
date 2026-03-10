import re
from typing import Dict, List

from .base import BaseMapper

# Lines to skip when detecting vendor name
_SKIP_VENDOR_RE = re.compile(
    r"(?i)^\s*(total\s*slip|invoice|tax\s*invoice|receipt|bill|copy)\s*$"
)

# Aliases for key-value header fields (order matters for extraction priority)
RECEIPT_FIELD_ALIASES: Dict[str, List[str]] = {
    "vendor": [],
    "gstin": ["gstin", "gst no", "gst in", "gst"],
    "date": ["date", "dt", "bill date"],
    "bill_no": ["billno", "bill no", "receipt no", "invoice no", "order no"],
    "total": ["grand total", "bill total", "net amount", "total"],
    "subtotal": ["subtotal", "sub total", "basic amount"],
    "sgst": ["sgst"],
    "cgst": ["cgst"],
    "igst": ["igst"],
    "service_charge": ["service charge", "srv chgs"],
    "payment_method": ["payment mode", "payment method", "payment"],
}

# Patterns that indicate the start of the items table header
_ITEM_HEADER_RE = re.compile(
    r"(?i)\b(item|description|particular)\b",
)
# Patterns that indicate we've moved past the items section
_ITEM_END_RE = re.compile(
    r"(?i)^\s*(sub\s*total|subtotal|total\s*qty|grand\s*total|bill\s*total"
    r"|basic\s*amount|net\s*amount|total\b|sgst|cgst|igst|service\s*charge"
    r"|srv\s*chg|add\s*:|thank|round)",
)
# Line items: 4-column (name qty price amount) — qty can be int or decimal
_LINE_ITEM_4COL_RE = re.compile(
    r"^(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,.]+)\s+([\d,.]+)\s*$"
)
# Line items: 3-column (name qty amount) — qty can be int or decimal
_LINE_ITEM_3COL_RE = re.compile(
    r"^(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,.]+)\s*$"
)
# Lines that are clearly not food items (headers, separators, metadata)
_NOT_ITEM_RE = re.compile(
    r"(?i)^[-=\s]*$|^(tax|gst|vat|base\s*amt|hsn|sac)\b"
)


class ReceiptMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields: List[Dict[str, str]] = []
        lines = raw_text.strip().split("\n")
        used_labels: set = set()

        # Vendor: first meaningful non-empty line
        for line in lines:
            stripped = line.strip()
            if not stripped or re.match(r"^[\d\s:/-]+$", stripped):
                continue
            if _SKIP_VENDOR_RE.match(stripped):
                continue
            # Skip separator lines
            if re.match(r"^[-=*_]+$", stripped):
                continue
            fields.append({"label": "vendor", "value": stripped})
            used_labels.add("vendor")
            break

        # Extract key-value header fields
        for label, aliases in RECEIPT_FIELD_ALIASES.items():
            if label in used_labels or not aliases:
                continue
            for alias in aliases:
                # Use word boundary to prevent "gst" matching "gstin" or
                # "tax" matching "tax invoice"
                if label == "gstin":
                    pattern = re.compile(
                        rf"(?i)\b{re.escape(alias)}\s*(?:no)?\s*[.:\-]*\s*(.+)",
                    )
                else:
                    pattern = re.compile(
                        rf"(?i)\b{re.escape(alias)}\s*[.:\-]*\s*(.+)",
                    )
                for line in lines:
                    # Skip lines where alias is part of a longer word
                    # e.g., "tax" should not match "TAX INVOICE NO:"
                    if label == "total":
                        # For "total", skip lines that say "total gst", "total vat",
                        # "total qty", "total slip" — these aren't the bill total
                        if re.search(r"(?i)\btotal\s+(gst|vat|uat|qty|slip|tax)\b", line):
                            continue
                    if label in ("sgst", "cgst"):
                        # For SGST/CGST, prefer lines with % to get tax amount
                        pass

                    match = pattern.search(line)
                    if match and label not in used_labels:
                        value = match.group(1).strip()

                        # Skip empty values (e.g., "CUSTOMER GSTIN :")
                        if not value or value == ":" or re.match(r"^[:\-.\s]*$", value):
                            continue

                        # For GSTIN, validate it looks like a GSTIN (alphanumeric, 15 chars)
                        if label == "gstin":
                            gstin_match = re.search(r"[A-Z0-9]{15}", value)
                            if gstin_match:
                                value = gstin_match.group(0)
                            elif not re.search(r"[A-Z0-9]{10,}", value):
                                continue

                        # For numeric fields, extract just the amount
                        if label in ("total", "subtotal", "sgst", "cgst", "igst",
                                     "service_charge"):
                            num = _extract_amount(value)
                            if num:
                                value = num
                            else:
                                continue

                        # For bill_no, stop at next key-value pair on same line
                        if label == "bill_no":
                            cut = re.split(r"\s{2,}|\t", value)
                            value = cut[0].strip()
                            # Skip if it looks like a column header
                            if re.match(r"(?i)^(amount|value|qty|price)\s*$", value):
                                continue

                        # For date, extract just the date portion and validate
                        if label == "date":
                            cut = re.split(r"\s{2,}|\t", value)
                            value = cut[0].strip()
                            # Must contain a digit to look like a date
                            if not re.search(r"\d", value):
                                # The date might be on the next line (header/value format)
                                line_idx = lines.index(line)
                                if line_idx + 1 < len(lines):
                                    next_line = lines[line_idx + 1].strip()
                                    next_cut = re.split(r"\s{2,}|\t", next_line)
                                    if next_cut and re.search(r"\d", next_cut[0]):
                                        value = next_cut[0].strip()
                                    else:
                                        continue
                                else:
                                    continue

                        if value:
                            fields.append({"label": label, "value": value})
                            used_labels.add(label)
                            break
                if label in used_labels:
                    break

        # Extract line items
        line_items = _extract_line_items(lines)
        if line_items:
            for item in line_items:
                fields.append({"label": "line_item", "value": item})

        return fields

    def document_type(self) -> str:
        return "receipt"


def _extract_amount(text: str) -> str:
    """Pull the amount from a string like 'Rs.10101.00' or '2.5% 240.50'.

    Always returns the last number on the line, which is typically the amount
    (even when a base amount precedes it on SGST/CGST lines).
    """
    nums = re.findall(r"[\d,]+\.?\d*", text)
    if nums:
        return nums[-1].replace(",", "")
    return ""


def _extract_line_items(lines: List[str]) -> List[str]:
    """Extract individual line items as 'name x qty = amount' strings."""
    items: List[str] = []
    in_items = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect item table header
        if not in_items and _ITEM_HEADER_RE.search(stripped):
            in_items = True
            continue

        # Detect end of items section
        if in_items and _ITEM_END_RE.match(stripped):
            break

        if not in_items:
            continue

        # Skip non-item lines (tax rows, headers, separators)
        if _NOT_ITEM_RE.match(stripped):
            continue

        # Try 4-column: ItemName  Qty  Price  Amount
        match = _LINE_ITEM_4COL_RE.match(stripped)
        if match:
            name = _clean_item_name(match.group(1))
            qty = _format_qty(match.group(2))
            amount = match.group(4)
            items.append(f"{name} x {qty} = {amount}")
            continue

        # Try 3-column: ItemName  Qty  Amount
        match = _LINE_ITEM_3COL_RE.match(stripped)
        if match:
            name = _clean_item_name(match.group(1))
            qty = _format_qty(match.group(2))
            amount = match.group(3)
            items.append(f"{name} x {qty} = {amount}")
            continue

        # Fallback: line with at least one number that looks like an item
        nums = re.findall(r"[\d,]+\.?\d+", stripped)
        text_part = re.sub(r"[\d,]+\.?\d+", "", stripped).strip(" \t-:,>")
        if nums and text_part and len(text_part) > 2:
            amount = nums[-1] if len(nums) > 1 else nums[0]
            items.append(f"{_clean_item_name(text_part)} = {amount}")

    return items


def _clean_item_name(name: str) -> str:
    """Normalize whitespace and strip leading markers from item name."""
    name = re.sub(r"^[>\-*•]+\s*", "", name)  # Strip leading > - * bullets
    return re.sub(r"\s+", " ", name).strip()


def _format_qty(qty: str) -> str:
    """Format quantity: '1.0' -> '1', '2.5' -> '2.5'."""
    try:
        f = float(qty)
        return str(int(f)) if f == int(f) else qty
    except ValueError:
        return qty
