"""
Backfill script: transform MySQL rc_master rows into Postgres-compatible format.
Maps critical fields to named columns, everything else into govt_fields JSONB dict.
"""
from typing import Dict, Any


# Critical fields → named columns
CRITICAL_FIELD_MAP = {
    "rc_number": "govt_registration_number",
    "owner_name": "govt_owner_name",
    "vehicle_chasi_number": "govt_chassis_number",
    "vehicle_engine_number": "govt_engine_number",
    "fuel_type": "govt_fuel_type",
    "vehicle_category": "govt_vehicle_class",
    "rc_status": "govt_rc_status",
    "fit_up_to": "govt_fitness_upto",
    "insurance_upto": "govt_insurance_upto",
    "vehicle_class": "govt_vehicle_class",  # alias
}


def transform_rc_master_row(mysql_row: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a MySQL rc_master row into Postgres format.

    Critical fields map to named columns. Everything else goes into govt_fields dict.
    The full original row is preserved as raw_response.
    """
    result = {}
    govt_fields = {}

    for key, value in mysql_row.items():
        pg_key = CRITICAL_FIELD_MAP.get(key)
        if pg_key:
            result[pg_key] = value
        else:
            govt_fields[key] = value

    result["govt_fields"] = govt_fields
    result["raw_response"] = mysql_row.copy()

    return result


def transform_rc_detail_row(mysql_row: Dict[str, Any], s3_base_url: str = "") -> Dict[str, Any]:
    """Transform a MySQL rc_detail row into Postgres format.

    Concatenates reg number parts, prepends S3 base URL to image paths,
    maps is_approve to overall_status/approval_method.
    """
    reg_parts = []
    for key in ("reg_state", "reg_rto", "reg_series", "reg_number"):
        if mysql_row.get(key):
            reg_parts.append(str(mysql_row[key]))

    registration_number = "".join(reg_parts) if reg_parts else mysql_row.get("rc_number", "")

    front_url = mysql_row.get("front_image", "")
    back_url = mysql_row.get("back_image", "")
    if s3_base_url:
        if front_url and not front_url.startswith("http"):
            front_url = f"{s3_base_url}/{front_url}"
        if back_url and not back_url.startswith("http"):
            back_url = f"{s3_base_url}/{back_url}"

    is_approve = mysql_row.get("is_approve")
    if is_approve == 1:
        overall_status = "accepted"
        approval_method = "manual_approved"
    elif is_approve == 0:
        overall_status = "rejected"
        approval_method = "manual_rejected"
    else:
        overall_status = "pending"
        approval_method = None

    return {
        "registration_number": registration_number,
        "front_url": front_url,
        "back_url": back_url,
        "overall_status": overall_status,
        "approval_method": approval_method,
        "driver_id": str(mysql_row.get("driver_id", "")),
        "raw_detail": mysql_row.copy(),
    }
