import re
from typing import Dict, List

from .base import BaseMapper

FUEL_PUMP_READING_FIELD_ALIASES: Dict[str, List[str]] = {
    "pump_number": ["pump no", "pump", "nozzle", "dispenser"],
    "fuel_type": ["fuel", "product"],
    "date": ["date"],
    "pump_reading_start": [
        "opening reading",
        "initial reading",
        "opening",
        "start",
    ],
    "pump_reading_end": [
        "closing reading",
        "final reading",
        "closing",
        "end",
    ],
    "quantity_dispensed": [
        "quantity dispensed",
        "quantity",
        "liters",
        "dispensed",
    ],
}


class FuelPumpReadingMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in FUEL_PUMP_READING_FIELD_ALIASES.items():
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
                        if value:
                            fields.append({"label": label, "value": value})
                            used_labels.add(label)
                            break
                if label in used_labels:
                    break

        return fields

    def document_type(self) -> str:
        return "fuel_pump_reading"
