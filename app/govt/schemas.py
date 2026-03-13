from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class RCGovtFields(BaseModel):
    owner_name: Optional[str] = None
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_number: Optional[str] = None
    registration_number: Optional[str] = None
    rc_status: Optional[str] = None
    fitness_upto: Optional[str] = None
    insurance_upto: Optional[str] = None
    extra_fields: Dict[str, Any] = {}

class DLGovtFields(BaseModel):
    holder_name: Optional[str] = None
    father_husband_name: Optional[str] = None
    dob: Optional[str] = None
    dl_number: Optional[str] = None
    dl_status: Optional[str] = None
    validity_nt: Optional[str] = None
    validity_tr: Optional[str] = None
    cov_details: Optional[list] = None
    issuing_authority: Optional[str] = None
    extra_fields: Dict[str, Any] = {}

class AadhaarGovtFields(BaseModel):
    holder_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None
    aadhaar_status: Optional[str] = None
    extra_fields: Dict[str, Any] = {}

class GovtVerificationResult(BaseModel):
    status: str
    reseller_code: str
    normalized_fields: Dict[str, Any]
    raw_response: Dict[str, Any]
    response_time_ms: int = 0
    api_cost_inr: float = 0.0
    error_message: Optional[str] = None
