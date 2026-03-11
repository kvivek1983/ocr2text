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
