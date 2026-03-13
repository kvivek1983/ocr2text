from thefuzz import fuzz
from app.config import settings

EXACT_MATCH_FIELDS = {
    "chassis_number",
    "engine_number",
    "registration_number",
    "dl_number",
    "aadhaar_number",
}

FUZZY_MATCH_FIELDS = {
    "owner_name",
    "holder_name",
    "father_name",
    "address",
}

CRITICAL_FIELDS = {"chassis_number", "engine_number", "registration_number"}


class FieldComparator:
    def compare_field(
        self,
        field_name: str,
        mapper_value,
        llm_value,
        govt_value,
    ) -> dict:
        # Determine which values to compare: prefer govt_value vs llm_value
        if govt_value is not None:
            val_a = str(govt_value).strip().upper() if govt_value else ""
            val_b = str(llm_value).strip().upper() if llm_value else ""
        else:
            val_a = str(mapper_value).strip().upper() if mapper_value else ""
            val_b = str(llm_value).strip().upper() if llm_value else ""

        if field_name in EXACT_MATCH_FIELDS:
            is_match = val_a == val_b
            similarity_score = 1.0 if is_match else 0.0
            match_type = "exact"
        elif field_name in FUZZY_MATCH_FIELDS:
            ratio = fuzz.token_sort_ratio(val_a, val_b) / 100.0
            similarity_score = ratio
            is_match = ratio >= settings.FUZZY_NAME_MATCH_THRESHOLD
            match_type = "fuzzy"
        else:
            # Default: fuzzy
            ratio = fuzz.token_sort_ratio(val_a, val_b) / 100.0
            similarity_score = ratio
            is_match = ratio >= settings.FUZZY_NAME_MATCH_THRESHOLD
            match_type = "fuzzy"

        return {
            "field_name": field_name,
            "mapper_value": mapper_value,
            "llm_value": llm_value,
            "govt_value": govt_value,
            "is_match": is_match,
            "similarity_score": similarity_score,
            "match_type": match_type,
        }

    def compute_match_score(self, comparisons: list) -> float:
        total_weight = 0.0
        weighted_sum = 0.0

        for comp in comparisons:
            field_name = comp["field_name"]
            score = comp["similarity_score"]
            weight = 2.0 if field_name in CRITICAL_FIELDS else 1.0
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight
