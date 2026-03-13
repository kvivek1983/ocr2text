from typing import Dict, Any
from app.govt.mappers.base import BaseGovtMapper


class GridlinesMapper(BaseGovtMapper):
    def normalize(self, raw_response: dict, doc_type: str) -> Dict[str, Any]:
        if doc_type == "rc_book":
            return self._normalize_rc(raw_response)
        return {}

    def _normalize_rc(self, raw: dict) -> Dict[str, Any]:
        rc_data = raw.get("data", {}).get("rc_data", {})
        owner_data = rc_data.get("owner_data", {})
        vehicle_data = rc_data.get("vehicle_data", {})
        insurance_data = rc_data.get("insurance_data", {})

        return {
            "owner_name": owner_data.get("name"),
            "chassis_number": vehicle_data.get("chassis_number"),
            "engine_number": vehicle_data.get("engine_number"),
            "fuel_type": vehicle_data.get("fuel_type"),
            "vehicle_class": vehicle_data.get("category"),
            "rc_status": rc_data.get("status"),
            "insurance_upto": insurance_data.get("expiry_date"),
            "registration_number": None,
            "fitness_upto": None,
        }
