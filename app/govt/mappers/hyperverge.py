from typing import Dict, Any
from app.govt.mappers.base import BaseGovtMapper


class HyperVergeMapper(BaseGovtMapper):
    def normalize(self, raw_response: dict, doc_type: str) -> Dict[str, Any]:
        if doc_type == "rc_book":
            return self._normalize_rc(raw_response)
        return {}

    def _normalize_rc(self, raw: dict) -> Dict[str, Any]:
        result = raw.get("result", {})

        # Auto-detect format: flat (result.rcInfo) vs nested (result.data.rcData)
        rc_info = result.get("rcInfo")
        if rc_info is not None:
            return self._normalize_rc_flat(rc_info)

        rc_data = result.get("data", {}).get("rcData", {})
        return self._normalize_rc_nested(rc_data)

    def _normalize_rc_flat(self, rc_info: dict) -> Dict[str, Any]:
        insurance_details = rc_info.get("vehicle_insurance_details", {})
        return {
            "owner_name": rc_info.get("owner_name"),
            "chassis_number": rc_info.get("chassis_no"),
            "engine_number": rc_info.get("engine_no"),
            "fuel_type": rc_info.get("fuel_descr"),
            "vehicle_class": rc_info.get("vehicle_class_desc"),
            "rc_status": rc_info.get("status"),
            "registration_number": rc_info.get("reg_no"),
            "fitness_upto": rc_info.get("fit_upto"),
            "insurance_upto": insurance_details.get("insurance_upto"),
        }

    def _normalize_rc_nested(self, rc_data: dict) -> Dict[str, Any]:
        insurance_details = rc_data.get("vehicleInsuranceDetails", {})
        return {
            "owner_name": rc_data.get("ownerName"),
            "chassis_number": rc_data.get("chassisNo"),
            "engine_number": rc_data.get("engineNo"),
            "fuel_type": rc_data.get("fuelDescr"),
            "vehicle_class": rc_data.get("vehicleClassDesc"),
            "rc_status": rc_data.get("status"),
            "registration_number": rc_data.get("regNo"),
            "fitness_upto": rc_data.get("fitUpto"),
            "insurance_upto": insurance_details.get("insuranceUpto"),
        }
