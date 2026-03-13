from app.config import Settings


def test_default_settings():
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
    )
    assert settings.DEFAULT_ENGINE == "paddle"
    assert settings.ENABLE_PREPROCESSING is True
    assert settings.CONFIDENCE_THRESHOLD == 0.5
    assert settings.API_HOST == "0.0.0.0"
    assert settings.API_PORT == 8000
    assert settings.DEBUG is False


def test_custom_settings():
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
        DEFAULT_ENGINE="google",
        ENABLE_PREPROCESSING=False,
        CONFIDENCE_THRESHOLD=0.7,
    )
    assert settings.DEFAULT_ENGINE == "google"
    assert settings.ENABLE_PREPROCESSING is False
    assert settings.CONFIDENCE_THRESHOLD == 0.7


def test_llm_config_defaults():
    """New LLM config fields have sensible defaults."""
    from app.config import Settings
    s = Settings(DATABASE_URL="postgresql://x:x@localhost/test")
    assert s.LLM_PROVIDER == "anthropic"
    assert s.LLM_MODEL_ANTHROPIC == "claude-haiku-4-5-20251001"
    assert s.LLM_MODEL_OPENAI == "gpt-4o-mini"
    assert s.LLM_TIMEOUT_SECONDS == 30
    assert s.QUALITY_SCORE_THRESHOLD == 0.6
    assert s.AUTO_APPROVAL_QUALITY_THRESHOLD == 0.7
    assert s.AUTO_APPROVAL_MATCH_THRESHOLD == 0.85
    assert s.FUZZY_NAME_MATCH_THRESHOLD == 0.85
    assert s.ADMIN_API_KEY is None
