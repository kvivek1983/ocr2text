# OCR2Text — Project Memory

## Quick Reference
- **Stack:** FastAPI, SQLAlchemy 2.x, Google Vision API, Claude Haiku (Anthropic)
- **Deploy:** https://ocr2text-production.up.railway.app
- **DB:** PostgreSQL on Railway
- **Repos:** Bitbucket (ez_onewaycab/orc2text), GitHub (kvivek1983/ocr2text)
- **Endpoint:** `POST /verify/document` — single endpoint for all doc types (rc_book, driving_license, aadhaar)

## Critical Rules
- SQLAlchemy 2.x `Column(default=...)` does NOT apply at `__init__` time — use `__init__` overrides with `kwargs.setdefault()`
- Use `Numeric(10,4)` for cost columns, never Float
- `datetime.utcnow()` is deprecated in Python 3.12+ — use `datetime.now(timezone.utc)` in new code
- Claude Haiku returns JSON wrapped in markdown fences — always use `_extract_json()` to parse LLM responses
- Google Vision auth: use `GOOGLE_CREDENTIALS_JSON` env var (base64-encoded service account JSON) on Railway

## Pipeline
```
POST /verify/document
  1. Fetch image
  2. Image Quality Check (OpenCV — blur/brightness/resolution)
  3. Quality Gate: reject if layer_a_score < 0.4 (skips Vision + LLM = save cost)
  4. Google Vision OCR (only if quality passed)
  5. LLM Haiku extraction (raw_text → structured JSON)
  5. Field completeness check (Layer B)
  6. Store in DB + return response
```

## Backlog
- [ ] Build fuzzy logic on Google Vision raw text dataset — identify state/RTO, pass hints to Haiku prompts
- [x] Move quality check BEFORE Google Vision API call (done — saves Vision + LLM cost)
- [x] Allow any-order upload (front/back) — done, either side can be first + re-upload updates existing record
- [ ] Enable govt verification once reseller keys configured
- [ ] Seed `govt_resellers` table with Gridlines, Cashfree, HyperVerge configs
- [ ] Implement DL/Aadhaar govt mapper normalize methods
- [ ] Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` across codebase
- [ ] Add OCR text-length check after Vision (< 20 chars → reject as "no document detected")

## Pre-Deploy Checklist
- [ ] App imports clean: `python3 -c "from app.main import app"`
- [ ] Verify env vars: ANTHROPIC_API_KEY, GOOGLE_CREDENTIALS_JSON, ADMIN_API_KEY
- [ ] DB tables auto-created on startup via `Base.metadata.create_all()`
