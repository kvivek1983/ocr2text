import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.types import JSON

from app.storage.database import Base


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)

    image_hash = Column(String(64), index=True)
    document_type = Column(String(50), index=True)

    paddle_confidence = Column(Float, nullable=True)
    paddle_raw_text = Column(Text, nullable=True)
    paddle_fields = Column(JSON, nullable=True)
    paddle_time_ms = Column(Integer, nullable=True)

    google_confidence = Column(Float, nullable=True)
    google_raw_text = Column(Text, nullable=True)
    google_fields = Column(JSON, nullable=True)
    google_time_ms = Column(Integer, nullable=True)

    comparison_score = Column(Float, nullable=True)
    field_comparison = Column(JSON, nullable=True)
    recommended_engine = Column(String(20), nullable=True)

    engine_used = Column(String(20))
    request_metadata = Column(JSON, nullable=True)


class RCValidation(Base):
    """
    Stores RC book validation results for production quality review.
    Front and back are uploaded separately — linked by driver_id.
    A record is created on front upload and updated when back is submitted.
    """
    __tablename__ = "rc_validations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Input identifiers
    driver_id = Column(String(100), nullable=True, index=True)

    # URLs — front set on creation, back set when submitted
    front_url = Column(Text, nullable=True)
    back_url = Column(Text, nullable=True)

    # Per-upload status
    # "pending_back" | "accepted" | "needs_review" | "rejected"
    overall_status = Column(String(20), nullable=False, default="pending_back", index=True)

    # Per-side quality scores
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)

    # Issues per side (lists of strings)
    front_issues = Column(JSON, nullable=True)
    back_issues = Column(JSON, nullable=True)

    # Extracted fields per side
    front_fields = Column(JSON, nullable=True)   # {label: value, ...}
    back_fields = Column(JSON, nullable=True)

    # Merged key fields (populated after back is submitted)
    merged_fields = Column(JSON, nullable=True)
    registration_number = Column(String(20), nullable=True, index=True)

    # Review workflow
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)

    # --- New verification pipeline columns ---
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    mapper_raw_output = Column(JSON, nullable=True)


class GovtReseller(Base):
    __tablename__ = "govt_resellers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    name = Column(String(100), nullable=False)
    provider_code = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    supported_doc_types = Column(JSON, nullable=True)
    endpoints_by_doc_type = Column(JSON, nullable=True)
    response_mappers_by_doc_type = Column(JSON, nullable=True)
    request_template = Column(JSON, nullable=True)
    auth_config = Column(JSON, nullable=True)
    timeout_ms = Column(Integer, default=10000, nullable=False)
    circuit_state = Column(String(20), default="closed", nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_failure_at = Column(DateTime, nullable=True)
    total_requests = Column(Integer, default=0, nullable=False)
    successful_requests = Column(Integer, default=0, nullable=False)
    avg_response_ms = Column(Integer, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("is_active", True)
        kwargs.setdefault("circuit_state", "closed")
        super().__init__(**kwargs)


class RCLLMExtraction(Base):
    __tablename__ = "rc_llm_extractions"

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "success")
        super().__init__(**kwargs)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    model_provider = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    prompt_version = Column(String(20), nullable=True)
    llm_raw_response = Column(JSON, nullable=True)
    system_prompt_used = Column(Text, nullable=True)
    extracted_fields = Column(JSON, nullable=False)
    llm_confidence = Column(Float, nullable=True)
    extraction_time_ms = Column(Integer, nullable=True)
    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    cost_inr = Column(Numeric(10, 4), nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    # RC-specific denormalized fields
    registration_number = Column(String(20), nullable=True)
    owner_name = Column(String(200), nullable=True)
    vehicle_class = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    chassis_number = Column(String(50), nullable=True)
    engine_number = Column(String(50), nullable=True)
    registration_date = Column(DateTime, nullable=True)
    validity_date = Column(DateTime, nullable=True)
    rto_code = Column(String(20), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model_field = Column("model", String(100), nullable=True)


class RCGovtVerification(Base):
    __tablename__ = "rc_govt_verifications"

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("attempt_number", 1)
        super().__init__(**kwargs)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    reseller_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending", nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    api_cost_inr = Column(Numeric(10, 4), nullable=True)
    raw_response = Column(JSON, nullable=True)
    govt_fields = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    govt_registration_number = Column(String(20), nullable=True, index=True)
    govt_owner_name = Column(String(200), nullable=True)
    govt_chassis_number = Column(String(50), nullable=True)
    govt_engine_number = Column(String(50), nullable=True)
    govt_fuel_type = Column(String(50), nullable=True)
    govt_vehicle_class = Column(String(50), nullable=True)
    govt_rc_status = Column(String(20), nullable=True)
    govt_fitness_upto = Column(DateTime, nullable=True)
    govt_insurance_upto = Column(DateTime, nullable=True)


class RCFieldComparison(Base):
    __tablename__ = "rc_field_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    field_name = Column(String(50), nullable=False)
    comparison_type = Column(String(30), nullable=False)
    mapper_value = Column(Text, nullable=True)
    llm_value = Column(Text, nullable=True)
    govt_value = Column(Text, nullable=True)
    is_match = Column(Boolean, nullable=True)
    similarity_score = Column(Float, nullable=True)
    match_method = Column(String(20), nullable=True)
    winner = Column(String(20), nullable=True)


class DLValidation(Base):
    """
    Stores DL (Driving Licence) validation results.
    Front and back are uploaded separately — linked by driver_id.
    """
    __tablename__ = "dl_validations"

    def __init__(self, **kwargs):
        kwargs.setdefault("overall_status", "pending_back")
        kwargs.setdefault("verification_status", "pending")
        kwargs.setdefault("approval_method", "pending")
        kwargs.setdefault("requires_review", False)
        super().__init__(**kwargs)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    driver_id = Column(String(100), nullable=True, index=True)
    front_url = Column(Text, nullable=True)
    back_url = Column(Text, nullable=True)
    overall_status = Column(String(20), nullable=False, default="pending_back", index=True)
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)
    front_issues = Column(JSON, nullable=True)
    back_issues = Column(JSON, nullable=True)
    front_fields = Column(JSON, nullable=True)
    back_fields = Column(JSON, nullable=True)
    merged_fields = Column(JSON, nullable=True)
    dl_number = Column(String(20), nullable=True, index=True)
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
    # Verification pipeline columns
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    mapper_raw_output = Column(JSON, nullable=True)


class DLLLMExtraction(Base):
    __tablename__ = "dl_llm_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    model_provider = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    prompt_version = Column(String(20), nullable=True)
    llm_raw_response = Column(JSON, nullable=True)
    system_prompt_used = Column(Text, nullable=True)
    extracted_fields = Column(JSON, nullable=False)
    llm_confidence = Column(Float, nullable=True)
    extraction_time_ms = Column(Integer, nullable=True)
    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    cost_inr = Column(Numeric(10, 4), nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    # DL-specific denormalized fields
    dl_number = Column(String(20), nullable=True)
    holder_name = Column(String(200), nullable=True)
    father_husband_name = Column(String(200), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    blood_group = Column(String(10), nullable=True)
    issue_date = Column(DateTime, nullable=True)
    validity_nt = Column(DateTime, nullable=True)
    validity_tr = Column(DateTime, nullable=True)
    issuing_authority = Column(String(200), nullable=True)
    cov_details = Column(JSON, nullable=True)
    address = Column(Text, nullable=True)


class DLGovtVerification(Base):
    __tablename__ = "dl_govt_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    reseller_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending", nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    api_cost_inr = Column(Numeric(10, 4), nullable=True)
    raw_response = Column(JSON, nullable=True)
    govt_fields = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    govt_dl_number = Column(String(20), nullable=True, index=True)
    govt_holder_name = Column(String(200), nullable=True)
    govt_father_husband_name = Column(String(200), nullable=True)
    govt_dob = Column(DateTime, nullable=True)
    govt_dl_status = Column(String(20), nullable=True)
    govt_validity_nt = Column(DateTime, nullable=True)
    govt_validity_tr = Column(DateTime, nullable=True)
    govt_cov_details = Column(JSON, nullable=True)
    govt_issuing_authority = Column(String(200), nullable=True)


class DLFieldComparison(Base):
    __tablename__ = "dl_field_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    field_name = Column(String(50), nullable=False)
    comparison_type = Column(String(30), nullable=False)
    mapper_value = Column(Text, nullable=True)
    llm_value = Column(Text, nullable=True)
    govt_value = Column(Text, nullable=True)
    is_match = Column(Boolean, nullable=True)
    similarity_score = Column(Float, nullable=True)
    match_method = Column(String(20), nullable=True)
    winner = Column(String(20), nullable=True)


class AadhaarValidation(Base):
    """
    Stores Aadhaar card validation results.
    Front and back are uploaded separately — linked by driver_id.
    """
    __tablename__ = "aadhaar_validations"

    def __init__(self, **kwargs):
        kwargs.setdefault("overall_status", "pending_back")
        kwargs.setdefault("verification_status", "pending")
        kwargs.setdefault("approval_method", "pending")
        kwargs.setdefault("requires_review", False)
        super().__init__(**kwargs)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    driver_id = Column(String(100), nullable=True, index=True)
    front_url = Column(Text, nullable=True)
    back_url = Column(Text, nullable=True)
    overall_status = Column(String(20), nullable=False, default="pending_back", index=True)
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)
    front_issues = Column(JSON, nullable=True)
    back_issues = Column(JSON, nullable=True)
    front_fields = Column(JSON, nullable=True)
    back_fields = Column(JSON, nullable=True)
    merged_fields = Column(JSON, nullable=True)
    aadhaar_number = Column(String(20), nullable=True, index=True)
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
    # Verification pipeline columns
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    mapper_raw_output = Column(JSON, nullable=True)


class AadhaarLLMExtraction(Base):
    __tablename__ = "aadhaar_llm_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    model_provider = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    prompt_version = Column(String(20), nullable=True)
    llm_raw_response = Column(JSON, nullable=True)
    system_prompt_used = Column(Text, nullable=True)
    extracted_fields = Column(JSON, nullable=False)
    llm_confidence = Column(Float, nullable=True)
    extraction_time_ms = Column(Integer, nullable=True)
    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    cost_inr = Column(Numeric(10, 4), nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    # Aadhaar-specific denormalized fields
    aadhaar_number = Column(String(20), nullable=True)
    holder_name = Column(String(200), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(10), nullable=True)
    father_name = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    pin_code = Column(String(10), nullable=True)


class AadhaarGovtVerification(Base):
    __tablename__ = "aadhaar_govt_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    reseller_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending", nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    api_cost_inr = Column(Numeric(10, 4), nullable=True)
    raw_response = Column(JSON, nullable=True)
    govt_fields = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    govt_aadhaar_number = Column(String(20), nullable=True, index=True)
    govt_holder_name = Column(String(200), nullable=True)
    govt_dob = Column(DateTime, nullable=True)
    govt_gender = Column(String(10), nullable=True)
    govt_address = Column(Text, nullable=True)
    govt_pin_code = Column(String(10), nullable=True)
    govt_aadhaar_status = Column(String(20), nullable=True)
    verification_method = Column(String(20), default="demographic", nullable=False)


class AadhaarFieldComparison(Base):
    __tablename__ = "aadhaar_field_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    field_name = Column(String(50), nullable=False)
    comparison_type = Column(String(30), nullable=False)
    mapper_value = Column(Text, nullable=True)
    llm_value = Column(Text, nullable=True)
    govt_value = Column(Text, nullable=True)
    is_match = Column(Boolean, nullable=True)
    similarity_score = Column(Float, nullable=True)
    match_method = Column(String(20), nullable=True)
    winner = Column(String(20), nullable=True)


class DriverOnboardingStatus(Base):
    __tablename__ = "driver_onboarding_status"

    def __init__(self, **kwargs):
        kwargs.setdefault("onboarding_status", "incomplete")
        super().__init__(**kwargs)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarding_status = Column(String(20), nullable=False, default="incomplete")
    rc_validation_id = Column(String(36), nullable=True)
    rc_status = Column(String(20), nullable=True)
    dl_validation_id = Column(String(36), nullable=True)
    dl_status = Column(String(20), nullable=True)
    aadhaar_validation_id = Column(String(36), nullable=True)
    aadhaar_status = Column(String(20), nullable=True)
    cross_doc_checks = Column(JSON, nullable=True)
    cross_doc_passed = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
