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
