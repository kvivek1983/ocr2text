import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.types import JSON

from app.storage.database import Base


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)

    image_hash = Column(String(64), index=True)
    document_type = Column(String(50), index=True)

    paddle_confidence = Column(Float, nullable=True)
    paddle_raw_text = Column(Text, nullable=True)
    paddle_fields = Column(JSON, nullable=True)
    paddle_time_ms = Column(Integer, nullable=True)

    google_confidence = Column(Float, nullable=True)
    google_raw_text = Column(Text, nullable=True)
    google_fields = Column(JSON, nullable=True)
    google_time_ms = Column(Integer, nullable=True)

    comparison_score = Column(Float, nullable=True)
    field_comparison = Column(JSON, nullable=True)
    recommended_engine = Column(String(20), nullable=True)

    engine_used = Column(String(20))
    request_metadata = Column(JSON, nullable=True)
