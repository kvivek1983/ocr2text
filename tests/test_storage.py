import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.storage.database import Base
from app.storage.models import Extraction
from app.storage.repository import ExtractionRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def test_create_extraction(db_session):
    repo = ExtractionRepository(db_session)
    extraction = repo.create(
        image_hash="abc123",
        document_type="receipt",
        engine_used="paddle",
        paddle_confidence=0.92,
        paddle_raw_text="raw text here",
        paddle_fields=[{"label": "vendor", "value": "Big Bazaar"}],
        paddle_time_ms=100,
    )
    assert extraction.id is not None
    assert extraction.document_type == "receipt"
    assert extraction.paddle_confidence == 0.92


def test_get_extraction_by_hash(db_session):
    repo = ExtractionRepository(db_session)
    repo.create(
        image_hash="abc123",
        document_type="receipt",
        engine_used="paddle",
    )
    result = repo.get_by_image_hash("abc123")
    assert result is not None
    assert result.image_hash == "abc123"


def test_get_extraction_by_hash_not_found(db_session):
    repo = ExtractionRepository(db_session)
    result = repo.get_by_image_hash("nonexistent")
    assert result is None
