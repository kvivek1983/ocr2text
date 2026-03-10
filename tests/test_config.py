from app.config import Settings


def test_default_settings():
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
    )
    assert settings.DEFAULT_ENGINE == "easyocr"
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


def test_engine_map_defaults():
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
    )
    assert settings.ENGINE_MAP["receipt"] == "easyocr"
    assert settings.ENGINE_MAP["driving_license"] == "tesseract"
    assert settings.get_engine_for_type("receipt") == "easyocr"
    assert settings.get_engine_for_type("driving_license") == "tesseract"
    assert settings.get_engine_for_type("unknown_type") == "easyocr"
    assert settings.get_engine_for_type(None) == "easyocr"


def test_engine_map_custom():
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
        ENGINE_MAP={"receipt": "tesseract", "invoice": "google"},
    )
    assert settings.get_engine_for_type("receipt") == "tesseract"
    assert settings.get_engine_for_type("invoice") == "google"
    # Falls back to DEFAULT_ENGINE for unmapped types
    assert settings.get_engine_for_type("driving_license") == "easyocr"
