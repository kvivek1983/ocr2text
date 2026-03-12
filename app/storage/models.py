import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
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
    """Stores RC book validation results for production quality review."""
    __tablename__ = "rc_validations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Input identifiers
    driver_id = Column(String(100), nullable=True, index=True)
    front_url = Column(Text, nullable=False)
    back_url = Column(Text, nullable=False)

    # Overall outcome
    overall_status = Column(String(20), nullable=False, index=True)
    # "accepted" | "needs_review" | "rejected"

    # Per-side quality scores
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)

    # Issues per side (lists of strings)
    front_issues = Column(JSON, nullable=True)   # e.g. ["Blurry image", "Missing fuel_type"]
    back_issues = Column(JSON, nullable=True)

    # Extracted fields per side
    front_fields = Column(JSON, nullable=True)   # {label: value, ...}
    back_fields = Column(JSON, nullable=True)

    # Merged key fields (for quick lookup)
    merged_fields = Column(JSON, nullable=True)  # best-effort merged {label: value, ...}
    registration_number = Column(String(20), nullable=True, index=True)

    # Review workflow
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
