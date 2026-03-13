from app.govt.mappers.base import BaseGovtMapper
from app.govt.schemas import RCGovtFields


class GridlinesMapper(BaseGovtMapper):
    def normalize(self, raw_response: dict, doc_type: str) -> RCGovtFields:
        if doc_type == "rc_book":
            return self._normalize_rc(raw_response)
        return RCGovtFields()

    def _normalize_rc(self, raw: dict) -> RCGovtFields:
        rc_data = raw.get("data", {}).get("rc_data", {})
        owner_data = rc_data.get("owner_data", {})
        vehicle_data = rc_data.get("vehicle_data", {})
        insurance_data = rc_data.get("insurance_data", {})

        return RCGovtFields(
            owner_name=owner_data.get("name"),
            chassis_number=vehicle_data.get("chassis_number"),
            engine_number=vehicle_data.get("engine_number"),
            fuel_type=vehicle_data.get("fuel_type"),
            vehicle_class=vehicle_data.get("category"),
            rc_status=rc_data.get("status"),
            insurance_upto=insurance_data.get("expiry_date"),
        )
