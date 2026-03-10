import re
from typing import Dict, List

from .base import BaseMapper

# Aliases for key-value header fields (order matters for extraction priority)
RECEIPT_FIELD_ALIASES: Dict[str, List[str]] = {
    "vendor": [],
    "gstin": ["gstin", "gst no", "gst in"],
    "date": ["date", "dt", "bill date"],
    "bill_no": ["billno", "bill no", "receipt no", "invoice no"],
    "total": ["bill total", "grand total", "total amount", "net amount", "total"],
    "subtotal": ["subtotal", "sub total"],
    "sgst": ["sgst"],
    "cgst": ["cgst"],
    "igst": ["igst"],
    "service_charge": ["service charge"],
    "tax": ["tax", "vat"],
    "payment_method": ["payment mode", "payment method", "payment"],
}

# Patterns that indicate the start of the items table header
_ITEM_HEADER_RE = re.compile(
    r"(?i)\b(item|description|particular)\b",
)
# Patterns that indicate we've moved past the items section
_ITEM_END_RE = re.compile(
    r"(?i)^\s*(sub\s*total|subtotal|total\s*qty|grand\s*total|bill\s*total"
    r"|total\b|sgst|cgst|igst|tax\b|service\s*charge|thank|round)",
)
# A line item: text followed by qty, price, amount numbers (4-column: name qty price amount)
_LINE_ITEM_4COL_RE = re.compile(
    r"^(.+?)\s+(\d+)\s+([\d,.]+)\s+([\d,.]+)\s*$"
)
# A line item: text followed by qty and amount (3-column: name qty amount)
_LINE_ITEM_3COL_RE = re.compile(
    r"^(.+?)\s+(\d+)\s+([\d,.]+)\s*$"
)


class ReceiptMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields: List[Dict[str, str]] = []
        lines = raw_text.strip().split("\n")
        used_labels: set = set()

        # Vendor: first non-empty line that isn't purely numbers/dates
        for line in lines:
            stripped = line.strip()
            if stripped and not re.match(r"^[\d\s:/-]+$", stripped):
                fields.append({"label": "vendor", "value": stripped})
                used_labels.add("vendor")
                break

        # Extract key-value header fields
        for label, aliases in RECEIPT_FIELD_ALIASES.items():
            if label in used_labels or not aliases:
                continue
            for alias in aliases:
                pattern = re.compile(
                    rf"(?i)\b{re.escape(alias)}\s*[.:\-]*\s*(.+)",
                )
                for line in lines:
                    match = pattern.search(line)
                    if match and label not in used_labels:
                        value = match.group(1).strip()
                        # For numeric fields, extract just the amount
                        if label in ("total", "subtotal", "sgst", "cgst", "igst",
                                     "tax", "service_charge"):
                            num = _extract_amount(value)
                            if num:
                                value = num
                        # For bill_no, stop at next key-value pair on same line
                        if label == "bill_no":
                            cut = re.split(r"\s{2,}|\t", value)
                            value = cut[0].strip()
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
    """Pull the first decimal/number from a string like 'Rs.10101.00' or '2.5% 240.50'."""
    # If it has a percentage, grab the amount after it
    pct_match = re.search(r"[\d.]+%\s*([\d,]+\.?\d*)", text)
    if pct_match:
        return pct_match.group(1).replace(",", "")
    # Otherwise grab the last number (most likely the amount)
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

        # Try 4-column: ItemName  Qty  Price  Amount
        match = _LINE_ITEM_4COL_RE.match(stripped)
        if match:
            name = _clean_item_name(match.group(1))
            qty = match.group(2)
            amount = match.group(4)
            items.append(f"{name} x {qty} = {amount}")
            continue

        # Try 3-column: ItemName  Qty  Amount
        match = _LINE_ITEM_3COL_RE.match(stripped)
        if match:
            name = _clean_item_name(match.group(1))
            qty = match.group(2)
            amount = match.group(3)
            items.append(f"{name} x {qty} = {amount}")
            continue

        # Fallback: line with at least one number that looks like an item
        nums = re.findall(r"[\d,]+\.?\d+", stripped)
        text_part = re.sub(r"[\d,]+\.?\d+", "", stripped).strip(" \t-:,")
        if nums and text_part and len(text_part) > 2:
            amount = nums[-1] if len(nums) > 1 else nums[0]
            items.append(f"{_clean_item_name(text_part)} = {amount}")

    return items


def _clean_item_name(name: str) -> str:
    """Normalize whitespace in an item name."""
    return re.sub(r"\s+", " ", name).strip()
