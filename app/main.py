# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router, _get_session_factory
from app.storage.database import Base

app = FastAPI(
    title="OCR Document Verification",
    description="Verify documents (RC, DL, Aadhaar) using Google Vision + Claude Haiku",
    version="2.0.0",
)

app.include_router(router)

from app.api.verify_routes import verify_router
app.include_router(verify_router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"success": False, "error": "VALIDATION_ERROR", "message": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "ENGINE_ERROR", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )


@app.on_event("startup")
def startup():
    """Initialise database tables on startup."""
    try:
        from sqlalchemy import create_engine
        from app.config import settings
        import app.storage.models  # noqa: F401 — registers models with Base metadata
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        )
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not initialise database: {e}")
