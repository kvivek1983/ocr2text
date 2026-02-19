from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ocr_db"

    # Google Cloud Vision
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # OCR Settings
    DEFAULT_ENGINE: str = "paddle"
    ENABLE_PREPROCESSING: bool = True
    CONFIDENCE_THRESHOLD: float = 0.5

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
