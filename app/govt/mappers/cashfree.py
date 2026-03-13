from typing import Dict, Any
from app.govt.mappers.base import BaseGovtMapper


class CashfreeMapper(BaseGovtMapper):
    def normalize(self, raw_response: dict, doc_type: str) -> Dict[str, Any]:
        if doc_type == "rc_book":
            return self._normalize_rc(raw_response)
        return {}

    def _normalize_rc(self, raw: dict) -> Dict[str, Any]:
        return {
            "owner_name": raw.get("owner"),
            "chassis_number": raw.get("chassis"),
            "engine_number": raw.get("engine"),
            "fuel_type": raw.get("type"),
            "vehicle_class": raw.get("class"),
            "rc_status": raw.get("rc_status"),
            "registration_number": raw.get("reg_no"),
            "insurance_upto": raw.get("vehicle_insurance_upto"),
            "fitness_upto": None,
        }
