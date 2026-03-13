from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ocr_db"

    # Google Cloud Vision
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # OCR Settings
    DEFAULT_ENGINE: str = "google"
    ENABLE_PREPROCESSING: bool = True
    CONFIDENCE_THRESHOLD: float = 0.5

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False

    # LLM
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL_ANTHROPIC: str = "claude-haiku-4-5-20251001"
    LLM_MODEL_OPENAI: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LLM_TIMEOUT_SECONDS: int = 30

    # Quality thresholds
    QUALITY_SCORE_THRESHOLD: float = 0.6
    BLUR_THRESHOLD: float = 0.5
    BRIGHTNESS_MIN: float = 0.3
    BRIGHTNESS_MAX: float = 0.9

    # Auto-approval thresholds
    AUTO_APPROVAL_QUALITY_THRESHOLD: float = 0.7
    AUTO_APPROVAL_MATCH_THRESHOLD: float = 0.85
    FUZZY_NAME_MATCH_THRESHOLD: float = 0.85

    # Admin
    ADMIN_API_KEY: Optional[str] = None

    # Govt reseller keys (referenced by name in govt_resellers.auth_config)
    GRIDLINES_API_KEY: Optional[str] = None
    CASHFREE_API_KEY: Optional[str] = None
    HYPERVERGE_API_KEY: Optional[str] = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
