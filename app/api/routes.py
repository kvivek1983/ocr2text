# app/api/routes.py
from fastapi import APIRouter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Database session factory (lazy-initialised on first use)
_SessionLocal = None


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db():
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "healthy"}
