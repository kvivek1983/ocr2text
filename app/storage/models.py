import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String, Text, Index
from sqlalchemy.types import JSON

from app.storage.database import Base


# =============================================================================
# 1. document_validations — unified (replaces rc_validations, dl_validations, aadhaar_validations)
# =============================================================================
class DocumentValidation(Base):
    """
    Unified document validation record for all doc types (RC, DL, Aadhaar).
    Front and back are uploaded separately — linked by driver_id + doc_type.
    A record is created on front upload and updated when back is submitted.
    """
    __tablename__ = "document_validations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identifiers
    driver_id = Column(String(100), nullable=True, index=True)
    doc_type = Column(String(20), nullable=False, index=True)   # 'rc_book' | 'driving_license' | 'aadhaar'
    doc_number = Column(String(50), nullable=True, index=True)  # registration_number / dl_number / aadhaar_number

    # URLs — front set on creation, back set when submitted
    front_url = Column(Text, nullable=True)
    back_url = Column(Text, nullable=True)

    # Status
    overall_status = Column(String(20), nullable=False, default="pending_back", index=True)
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)

    # Quality (Layer A)
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)
    front_issues = Column(JSON, nullable=True)
    back_issues = Column(JSON, nullable=True)

    # OCR raw text (always saved — Google Vision output)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)

    # Govt verification link
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)

    # Review workflow
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_doc_val_driver_doctype", "driver_id", "doc_type"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("overall_status", "pending_back")
        kwargs.setdefault("verification_status", "pending")
        kwargs.setdefault("approval_method", "pending")
        kwargs.setdefault("requires_review", False)
        super().__init__(**kwargs)


# =============================================================================
# 2. llm_extractions — unified (replaces rc/dl/aadhaar_llm_extractions)
# =============================================================================
class LLMExtraction(Base):
    __tablename__ = "llm_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    doc_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Model info
    model_provider = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    prompt_version = Column(String(20), nullable=True)

    # Input (kept for audit — what was sent to LLM)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    system_prompt_used = Column(Text, nullable=True)

    # Output
    extracted_fields = Column(JSON, nullable=False)   # THE source of truth
    llm_raw_response = Column(JSON, nullable=True)
    llm_confidence = Column(Float, nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)

    # Cost tracking
    extraction_time_ms = Column(Integer, nullable=True)
    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    cost_inr = Column(Numeric(10, 4), nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "success")
        super().__init__(**kwargs)


# =============================================================================
# 3. govt_verifications — unified (replaces rc/dl/aadhaar_govt_verifications)
# =============================================================================
class GovtVerification(Base):
    __tablename__ = "govt_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    doc_type = Column(String(20), nullable=False)
    reseller_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Status
    status = Column(String(20), default="pending", nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)

    # Response
    response_time_ms = Column(Integer, nullable=True)
    api_cost_inr = Column(Numeric(10, 4), nullable=True)
    raw_response = Column(JSON, nullable=True)
    govt_fields = Column(JSON, nullable=True)    # All govt fields in one JSON column
    error_message = Column(Text, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("attempt_number", 1)
        super().__init__(**kwargs)


# =============================================================================
# 4. field_comparisons — unified (replaces rc/dl/aadhaar_field_comparisons)
# =============================================================================
class FieldComparison(Base):
    __tablename__ = "field_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=False, index=True)
    doc_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    field_name = Column(String(50), nullable=False)
    comparison_type = Column(String(30), nullable=False)   # 'llm_vs_govt'
    llm_value = Column(Text, nullable=True)
    govt_value = Column(Text, nullable=True)
    is_match = Column(Boolean, nullable=True)
    similarity_score = Column(Float, nullable=True)
    match_method = Column(String(20), nullable=True)


# =============================================================================
# 5. govt_resellers — UNCHANGED
# =============================================================================
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


# =============================================================================
# 6. driver_onboarding_status — UPDATED (removed validation_id FKs)
# =============================================================================
class DriverOnboardingStatus(Base):
    __tablename__ = "driver_onboarding_status"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarding_status = Column(String(20), nullable=False, default="incomplete")
    rc_status = Column(String(20), nullable=True)
    dl_status = Column(String(20), nullable=True)
    aadhaar_status = Column(String(20), nullable=True)
    cross_doc_checks = Column(JSON, nullable=True)
    cross_doc_passed = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("onboarding_status", "incomplete")
        super().__init__(**kwargs)
