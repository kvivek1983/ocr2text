# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router, engine_router

app = FastAPI(
    title="OCR Document Extraction System",
    description="Extract structured data from documents using dual OCR engines",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "ENGINE_ERROR",
            "message": str(exc),
            "confidence": 0.0,
        },
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "ENGINE_ERROR",
            "message": str(exc),
            "confidence": 0.0,
        },
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "confidence": 0.0,
        },
    )


@app.on_event("startup")
def startup():
    """Register OCR engines on startup."""
    try:
        from app.engines.paddle_engine import PaddleEngine
        engine_router.register_engine("paddle", PaddleEngine())
    except Exception as e:
        print(f"Warning: Could not load PaddleOCR engine: {e}")

    try:
        from app.engines.google_engine import GoogleVisionEngine
        engine_router.register_engine("google", GoogleVisionEngine())
    except Exception as e:
        print(f"Warning: Could not load Google Vision engine: {e}")

    try:
        from app.engines.easyocr_engine import EasyOCREngine
        engine_router.register_engine("easyocr", EasyOCREngine())
    except Exception as e:
        print(f"Warning: Could not load EasyOCR engine: {e}")

    try:
        from app.engines.tesseract_engine import TesseractEngine
        engine_router.register_engine("tesseract", TesseractEngine())
    except Exception as e:
        print(f"Warning: Could not load Tesseract engine: {e}")
