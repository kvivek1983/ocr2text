from typing import Any, Dict, List, Optional
from pydantic import BaseModel, model_validator, field_validator


class ExtractionRequest(BaseModel):
    image: Optional[str] = None
    image_url: Optional[str] = None
    document_type: Optional[str] = None
    engine: str = "auto"
    include_raw_text: bool = True
    side: Optional[str] = None

    @model_validator(mode="after")
    def check_image_source(self):
        if not self.image and not self.image_url:
            raise ValueError("Either 'image' (base64) or 'image_url' must be provided")
        return self

    @field_validator("side")
    @classmethod
    def validate_side(cls, v):
        if v is not None and v not in ("front", "back"):
            raise ValueError("side must be 'front', 'back', or null")
        return v


class FieldResult(BaseModel):
    label: str
    value: str


class ImageQuality(BaseModel):
    overall_score: float
    is_acceptable: bool
    feedback: List[str] = []
    blur_score: float = 0.0
    brightness_score: float = 0.0
    resolution_score: float = 0.0
    completeness_score: float = 0.0
    missing_mandatory: List[str] = []


class DocumentAuthenticity(BaseModel):
    is_authentic: bool
    confidence: float
    structural: Dict[str, Any] = {}
    visual: Dict[str, Any] = {}


class ExtractionResponse(BaseModel):
    success: bool
    document_type: Optional[str] = None
    confidence: float = 0.0
    fields: List[FieldResult] = []
    raw_text: Optional[str] = None
    processing_time_ms: int = 0
    image_quality: Optional[ImageQuality] = None
    document_authenticity: Optional[DocumentAuthenticity] = None
    detected_side: Optional[str] = None


class ComparisonResponse(BaseModel):
    success: bool
    document_type: Optional[str] = None
    results: Dict[str, Any] = {}
    comparison: Dict[str, Any] = {}
    recommendation: Optional[str] = None
    comparison_id: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str
    confidence: float = 0.0


# --- RC Validation (production quality gate) ---

class RCValidationRequest(BaseModel):
    """Single-side RC upload. Front creates a new record; back updates it."""
    image_url: str
    side: str                     # "front" | "back"
    driver_id: str                # required — links front and back uploads

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v):
        if not v or v.strip().lower() in ("null", "none", ""):
            raise ValueError("image_url must be a valid URL, got null/empty value")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v):
        if v not in ("front", "back"):
            raise ValueError("side must be 'front' or 'back'")
        return v


class RCSideResult(BaseModel):
    """Quality + extraction result for one side of an RC."""
    quality_score: float
    is_acceptable: bool
    extracted_fields: Dict[str, str] = {}
    missing_mandatory: List[str] = []
    issues: List[str] = []
    blur_score: float = 0.0
    brightness_score: float = 0.0
    resolution_score: float = 0.0


class RCValidationResponse(BaseModel):
    success: bool
    validation_id: str
    side: str                     # which side was just uploaded
    # "pending_back" after front upload; final status after back upload
    overall_status: str
    requires_review: bool
    result: RCSideResult          # result for the uploaded side
    # Only populated after back is submitted:
    merged_fields: Dict[str, str] = {}
    issues: List[str] = []
    message: str = ""


class ReviewQueueItem(BaseModel):
    validation_id: str
    created_at: str
    driver_id: Optional[str]
    overall_status: str
    front_url: Optional[str]
    back_url: Optional[str]
    registration_number: Optional[str]
    # Per-side quality scores
    front_quality_score: Optional[float] = None
    back_quality_score: Optional[float] = None
    # Per-side extracted fields
    front_fields: Dict[str, str] = {}
    back_fields: Dict[str, str] = {}
    front_issues: List[str] = []
    back_issues: List[str] = []
    merged_fields: Dict[str, str] = {}
    # Review workflow
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    success: bool = True
    total: int
    items: List[ReviewQueueItem]


class MarkReviewedRequest(BaseModel):
    reviewed_by: str
    review_notes: Optional[str] = None
