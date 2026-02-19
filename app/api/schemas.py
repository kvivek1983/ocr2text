from typing import Any, Dict, List, Optional
from pydantic import BaseModel, model_validator


class ExtractionRequest(BaseModel):
    image: Optional[str] = None
    image_url: Optional[str] = None
    document_type: Optional[str] = None
    engine: str = "auto"
    include_raw_text: bool = True

    @model_validator(mode="after")
    def check_image_source(self):
        if not self.image and not self.image_url:
            raise ValueError("Either 'image' (base64) or 'image_url' must be provided")
        return self


class FieldResult(BaseModel):
    label: str
    value: str


class ExtractionResponse(BaseModel):
    success: bool
    document_type: Optional[str] = None
    confidence: float = 0.0
    fields: List[FieldResult] = []
    raw_text: Optional[str] = None
    processing_time_ms: int = 0


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
