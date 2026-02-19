import re
from typing import Dict, List

from .base import BaseMapper

INSURANCE_FIELD_ALIASES: Dict[str, List[str]] = {
    "policy_number": ["policy no", "policy number"],
    "insurer": ["insurer", "insurance company"],
    "insured_name": ["insured", "policy holder"],
    "vehicle_number": ["vehicle no"],
    "vehicle_make_model": ["vehicle", "make model"],
    "policy_type": ["policy type", "cover type", "type"],
    "start_date": ["effective from", "start date"],
    "expiry_date": ["effective to", "valid till", "expiry"],
    "premium": ["premium"],
    "idv": ["idv"],
    "coverage": ["cover", "coverage"],
    "nominee": ["nominee"],
}


class InsuranceMapper(BaseMapper):
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in INSURANCE_FIELD_ALIASES.items():
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
        return "insurance"
