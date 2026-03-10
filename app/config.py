from pydantic_settings import BaseSettings
from typing import Dict, Optional


# Default engine per document type.
# Override via ENGINE_MAP env var as JSON, e.g.:
#   ENGINE_MAP='{"receipt":"easyocr","invoice":"tesseract"}'
DEFAULT_ENGINE_MAP: Dict[str, str] = {
    "receipt": "easyocr",
    "invoice": "easyocr",
    "petrol_receipt": "easyocr",
    "driving_license": "tesseract",
    "rc_book": "tesseract",
    "insurance": "tesseract",
    "odometer": "tesseract",
    "fuel_pump_reading": "tesseract",
}


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ocr_db"

    # Google Cloud Vision
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # OCR Settings
    DEFAULT_ENGINE: str = "easyocr"
    ENGINE_MAP: Dict[str, str] = DEFAULT_ENGINE_MAP
    ENABLE_PREPROCESSING: bool = True
    CONFIDENCE_THRESHOLD: float = 0.5

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_engine_for_type(self, document_type: Optional[str] = None) -> str:
        """Resolve the best engine for a given document type."""
        if document_type and document_type in self.ENGINE_MAP:
            return self.ENGINE_MAP[document_type]
        return self.DEFAULT_ENGINE


settings = Settings()
