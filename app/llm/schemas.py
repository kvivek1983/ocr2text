from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator


class RCExtractionFields(BaseModel):
    registration_number: Optional[str] = None
    owner_name: Optional[str] = None
    father_name: Optional[str] = None
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_number: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    registration_date: Optional[str] = None
    validity_date: Optional[str] = None
    rto_code: Optional[str] = None
    rto_name: Optional[str] = None
    insurance_upto: Optional[str] = None
    fitness_upto: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    seat_capacity: Optional[str] = None
    emission_norms: Optional[str] = None


class DLExtractionFields(BaseModel):
    dl_number: Optional[str] = None
    holder_name: Optional[str] = None
    father_husband_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    blood_group: Optional[str] = None
    issue_date: Optional[str] = None
    validity_nt: Optional[str] = None
    validity_tr: Optional[str] = None
    issuing_authority: Optional[str] = None
    cov_details: Optional[List[Dict[str, str]]] = None
    address: Optional[str] = None


class AadhaarExtractionFields(BaseModel):
    aadhaar_number: Optional[str] = None
    holder_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    father_name: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None


class LLMExtractionMetadata(BaseModel):
    llm_provider: str
    llm_model: str
    extraction_time_ms: int
    prompt_version: str
    ocr_engine: str = "google_vision"


class LLMExtractionResult(BaseModel):
    extracted_fields: Dict[str, Any]
    metadata: LLMExtractionMetadata
    raw_response: Dict[str, Any]
    system_prompt_used: str
    status: str = "success"
    error_message: Optional[str] = None
    token_input: int = 0
    token_output: int = 0
    cost_inr: float = 0.0


class VerifyDocumentRequest(BaseModel):
    image_type: str
    side: str
    driver_id: str
    image_url: str

    @field_validator("image_type")
    @classmethod
    def validate_image_type(cls, v):
        valid = ("rc_book", "driving_license", "aadhaar")
        if v not in valid:
            raise ValueError(f"image_type must be one of {valid}")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v):
        if v not in ("front", "back"):
            raise ValueError("side must be 'front' or 'back'")
        return v


class VerifyDocumentResponse(BaseModel):
    request_id: str
    status: str
    quality_score: float
    rejection_reasons: List[str] = []
    message: str
    structured_data: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[LLMExtractionMetadata] = None
