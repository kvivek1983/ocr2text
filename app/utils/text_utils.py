# app/utils/text_utils.py
import re
from typing import Optional
from datetime import datetime


def clean_text(text: str) -> str:
    """Clean and normalize raw OCR text."""
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


def normalize_amount(text: str) -> str:
    """Extract numeric amount from text like '₹1,234.00' -> '1234.00'."""
    if not text:
        return ""
    cleaned = re.sub(r"₹|Rs\.?", "", text).strip()
    cleaned = cleaned.replace(",", "")
    match = re.search(r"\d+\.?\d*", cleaned)
    return match.group(0) if match else ""


def normalize_date(text: str) -> Optional[str]:
    """Try to parse date string into YYYY-MM-DD format."""
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
    ]
    text = text.strip()
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
