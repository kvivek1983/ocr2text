import re
from typing import List, Dict


class FieldExtractor:
    """Extract generic key-value pairs from raw OCR text."""

    DELIMITERS = [r":\s*", r"\s*-\s+", r"\s{2,}"]

    def extract(self, raw_text: str) -> List[Dict[str, str]]:
        """Extract key-value pairs from raw OCR text."""
        if not raw_text.strip():
            return []

        fields = []
        pattern = re.compile(
            r"^(.+?)(?:" + "|".join(self.DELIMITERS) + r")(.+)$"
        )

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if match:
                label = match.group(1).strip()
                value = match.group(2).strip()
                if label and value and len(label) < 50:
                    fields.append({"label": label, "value": value})

        return fields
