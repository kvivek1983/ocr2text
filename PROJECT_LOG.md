# OCR Core — Project Log

## Project Overview

OCR document extraction system built with FastAPI, supporting multiple OCR engines (PaddleOCR, EasyOCR, Tesseract) and 8 document types. Deployed at `ocr2text-production.up.railway.app` on Railway.

**Stack:** Python 3.11, FastAPI, Pydantic, OpenCV, SQLAlchemy, PostgreSQL, Docker + Nginx

---

## Architecture

```
app/
  api/          - FastAPI routes + Pydantic schemas
  core/         - Extraction pipeline, preprocessor, document detector
  engines/      - OCR engine plugins (paddle, easyocr, tesseract, google)
  mappers/      - Document-type field mappers (receipt, invoice, RC book, etc.)
  storage/      - SQLAlchemy models + repository
  comparison/   - Multi-engine comparison + metrics
  utils/        - Image/text utilities
tests/          - pytest suite (93+ tests)
```

**Key patterns:**
- Plugin architecture: `BaseOCREngine` abstract class, engines registered at startup
- Mapper registry: `BaseMapper` per document type, alias-based regex field extraction
- Pipeline: image preprocessing -> OCR -> document detection -> field mapping

---

## Changelog

### 2026-03-11 — RC Book Extraction Enhancement (in progress)

**Goal:** Enhance RC book extraction for Indian Registration Certificates with front/back support, image quality feedback, document authenticity validation, and multi-engine comparison.

**Design decisions:**
- Front/back are separate API calls; client merges using `registration_number` (common to both sides)
- `side` parameter added to `ExtractionRequest` — "front", "back", or null (auto-detect)
- Image quality: two layers — Layer A (pre-OCR: blur, brightness, resolution) + Layer B (post-OCR: mandatory field completeness)
- Document authenticity: structural checks (critical, pass/fail) + visual checks (confidence-only, OpenCV)
- Multi-engine comparison via new `/compare/rc-book` endpoint for testing phase
- All new response fields optional — backward compatible

**Front mandatory fields (5):** registration_number, owner_name, vehicle_make, fuel_type, registration_date
**Back mandatory fields (3):** registration_number, engine_number, chassis_number

**Commits:**
- `5fcaff5` — Design spec: `docs/superpowers/specs/2026-03-11-rc-book-extraction-enhancement-design.md`
- `35e605e` — Implementation plan: `docs/superpowers/plans/2026-03-11-rc-book-extraction-enhancement.md`
- `dc6d12b` — Task 1: Add `side: Optional[str] = None` to BaseMapper + all 7 mappers
- `0599840` — Task 2: RC book front/back mapper tests (20 tests)
- `927874b` — Task 3: RC book mapper with front/back side support, auto-detection
- `2d77997` — Tasks 4+6: Image quality (18 tests) + document authenticity (17 tests) — red phase
- `0825c7d` — Tasks 5+7: Image quality assessor + document validator implementations — green phase
- Tasks 8-15 in progress...

**Implementation plan (15 tasks, 6 chunks):**
1. BaseMapper interface + RC book mapper expansion (front/back/common fields)
2. Image quality assessment module (`app/core/image_quality.py`)
3. Document authenticity validator (`app/core/document_validator.py`)
4. Schema updates + pipeline integration
5. N-engine comparator + `/compare/rc-book` endpoint
6. Final verification + deploy + live testing

### 2026-02-19 — Initial Build

**Commits (oldest to newest):**
- `c803e8e` — Driving license, RC book, insurance mappers
- `c3a6fb5` — Fuel tracking mappers (petrol receipt, odometer, fuel pump)
- `52503da` — Engine comparison system with metrics
- `628f71e` — Database models and extraction repository
- `bff9770` — Mapper registry for document type lookup
- `694e77c` — Pydantic request/response schemas
- `c43b165` — Extraction service orchestrator
- `8103aa2` — FastAPI application with routes and error handling
- `6d7a054` — Docker Compose + Nginx reverse proxy
- `5a2457e` — GitHub Actions CI/CD pipeline
- `03e64c4` — Dockerfile for OCR service
- `9e49510` — Fix: replace deprecated libgl1-mesa-glx with libgl1

---

## Deployment

- **Production:** `ocr2text-production.up.railway.app` (Railway)
- **CI/CD:** GitHub Actions — test on PR, build Docker on main push
- **Engines available:** paddle, easyocr, tesseract (Google Vision not configured)
- **Docker:** python:3.11-slim + OpenCV + Tesseract system deps

---

## Discussion Notes

### RC Book Format Observations
- Indian RC books come as smart cards (credit card sized) or older paper booklets
- Each state has 2-3 RC formats with different label text
- Smart card aspect ratio: ~1.586:1 (85.6mm x 54mm)
- Smart cards have characteristic blue/green header bands
- `registration_number` appears on both front and back — natural merge key
- Older paper RCs will pass structural authenticity but fail visual checks (by design)

### Quality Assessment Design
- Layer A (image properties) is advisory only — never short-circuits pipeline
- Layer B (field completeness) is the primary quality gate
- Blur alone doesn't fail quality — but blur + missing fields = unacceptable
- Per-document-type mandatory field counts drive the quality score
- Feedback messages are specific and actionable (not generic "bad image")

### Engine Comparison Strategy
- All 3 engines (paddle, easyocr, tesseract) to be compared during testing phase
- Recommendation: most mandatory fields > highest confidence > fastest processing
- Field agreement: full (all same), partial (majority agree), disagreement (all different)
- Goal: determine best default engine for Indian RC books

### Document Authenticity
- Structural checks (text-based) are critical — must pass for `is_authentic = True`
- Visual checks (OpenCV) are confidence-only — adjust score but don't block
- Paper-format RCs: structural passes, visual fails = authentic at lower confidence
- Fraud detection: someone printing RC text on plain paper will fail visual checks (no card edges, wrong aspect ratio, no color bands)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + engine list |
| GET | `/engines` | List registered engines |
| POST | `/extract` | Generic extraction (auto-detect type) |
| POST | `/extract/receipt` | Receipt extraction |
| POST | `/extract/invoice` | Invoice extraction |
| POST | `/extract/driving-license` | Driving license extraction |
| POST | `/extract/rc-book` | RC book extraction (supports `side`) |
| POST | `/extract/insurance` | Insurance policy extraction |
| POST | `/extract/petrol-receipt` | Petrol receipt extraction |
| POST | `/extract/odometer` | Odometer reading extraction |
| POST | `/extract/fuel-pump-reading` | Fuel pump reading extraction |
| POST | `/compare/rc-book` | Multi-engine comparison (planned) |

---

## Testing

- **Framework:** pytest + pytest-asyncio + pytest-cov
- **Current count:** 148 tests passing (as of Tasks 4-7)
- **Run:** `pytest tests/ -v --tb=short`
- **Live testing:** `curl -X POST https://ocr2text-production.up.railway.app/extract/rc-book -H "Content-Type: application/json" -d '{"image_url": "<URL>", "side": "front"}'`
