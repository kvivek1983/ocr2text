# Pipeline Simplification Spec: Google Vision + Haiku

## Problem

Current `/verify/document` pipeline has 7+ layers built for PaddleOCR that are now redundant with Google Vision + Claude Haiku:
- Preprocessing (grayscale, denoise, threshold) — Google Vision handles internally
- Regex mappers (~500 lines for RC alone) — LLM does this better
- Document detector — caller always provides `image_type`
- Generic field extractor — LLM replaces it
- Quality Layer B checks mapper output, not LLM output — produces misleading rejection reasons
- `extraction_service.extract()` does OCR + mapper + quality + authenticity in one call, then LLM runs separately — tangled responsibilities

## New Pipeline

```
POST /verify/document
  │
  ├─ 1. Fetch image (image_bytes from URL)
  │
  ├─ 2. IN PARALLEL:
  │     ├─ a) Google Vision OCR → raw_text, confidence
  │     └─ b) Image Quality Layer A (blur, brightness, resolution on image_bytes)
  │
  ├─ 3. QUALITY GATE:
  │     ├─ IF quality_score < threshold → REJECT immediately (no LLM call, save cost)
  │     │   └─ Return: status=rejected, quality_score, rejection_reasons, structured_data=null
  │     └─ IF quality_score >= threshold → continue
  │
  ├─ 4. LLM Haiku extraction (raw_text → structured_data)
  │
  ├─ 5. Field completeness check on LLM output (new Layer B)
  │     └─ Check mandatory fields are non-null in structured_data
  │
  ├─ 6. Store in DB:
  │     ├─ Validation record (front/back flow unchanged)
  │     ├─ Google Vision raw_text (always saved)
  │     └─ LLM extraction result (if called)
  │
  └─ 7. Return response
```

## What Changes

### REMOVE from `/verify/document` flow (comment out, don't delete):

| Component | File | Why Remove |
|-----------|------|-----------|
| `extraction_service.extract()` | `app/core/extraction_service.py` | Orchestrates old pipeline; replace with direct Google Vision call |
| `ImagePreprocessor` | `app/core/preprocessor.py` | Google Vision handles preprocessing |
| `DocumentDetector` | `app/core/document_detector.py` | Caller always provides `image_type` |
| `FieldExtractor` (generic) | `app/core/field_extractor.py` | LLM replaces it |
| Regex mappers | `app/mappers/rc_book.py` etc. | LLM replaces them |
| Quality Layer B (old) | `app/core/image_quality.py` `assess_completeness()` | Was checking mapper fields; replaced by LLM field check |
| Document authenticity | `app/core/document_validator.py` | Structural checks on OCR text are unreliable; LLM can detect fake docs if needed |

### KEEP:

| Component | File | Why Keep |
|-----------|------|---------|
| Google Vision engine | `app/engines/google_engine.py` | Core OCR |
| Image Quality Layer A | `app/core/image_quality.py` `assess_image_properties()` | Pre-OCR quality gate (blur, brightness, resolution) |
| LLM Extractor | `app/llm/extractor.py` | Structured field extraction |
| LLM Prompts | `app/llm/prompts/*.txt` | Field extraction instructions |
| DB models | `app/storage/models.py` | Data persistence |
| Repositories | `app/storage/repository.py` | CRUD |
| Front/back upload logic | `app/api/verify_routes.py` | Two-step upload flow |
| Engine router | `app/core/router.py` | Engine abstraction |

### KEEP BUT UNUSED (for `/validate/rc-book` legacy endpoint):

| Component | File | Notes |
|-----------|------|-------|
| `extraction_service.extract()` | `app/core/extraction_service.py` | Still used by `/validate/rc-book`, `/extract/*` endpoints |
| Regex mappers | `app/mappers/*` | Still used by legacy endpoints |
| All old quality/auth code | `app/core/*` | Still used by legacy endpoints |

## New `/verify/document` Flow (Detail)

### Step 1: Fetch Image
```python
image_bytes = fetch_image_url(request.image_url)
```
No change.

### Step 2: Parallel — Google Vision OCR + Image Quality

```python
async def _ocr():
    engine = engine_router.get_engine("google")
    return engine.extract(image_bytes)

async def _quality():
    return quality_assessor.assess_image_properties(image_bytes)

ocr_result, quality_a = await asyncio.gather(_ocr(), _quality())
raw_text = ocr_result["raw_text"]
ocr_confidence = ocr_result["confidence"]
```

**Image Quality Layer A** checks (on raw image_bytes, no OpenCV dependency needed):
- Blur score (Laplacian variance)
- Brightness score (mean pixel value)
- Resolution score (image dimensions)
- Returns: `quality_score` (0.0 - 1.0), `is_acceptable`, `feedback[]`

### Step 3: Quality Gate

```python
if not quality_a["is_acceptable"]:
    # Store record with rejection, skip LLM call
    # ... store validation record ...
    return VerifyDocumentResponse(
        status="rejected",
        quality_score=quality_a["overall_score"],
        rejection_reasons=quality_a["feedback"],
        message="Please re-upload a clearer photo",
        structured_data=None,
        extraction_metadata=None,
    )
```

**Saves ~₹0.5 per rejected image** (no Haiku call).

### Step 4: LLM Extraction (only if quality passed)

```python
llm_result = await _llm_extractor.extract(
    ocr_text_front=raw_text if request.side == "front" else None,
    ocr_text_back=raw_text if request.side == "back" else None,
    document_type=request.image_type,
    side=request.side,
)
```

No change to LLM extractor itself.

### Step 5: Field Completeness (New Layer B)

Check LLM output for mandatory fields instead of old mapper output:

```python
MANDATORY_FIELDS = {
    "rc_book": {
        "front": ["registration_number", "owner_name", "fuel_type", "registration_date"],
        "back": ["registration_number", "manufacturer"],
    },
    "driving_license": {
        "front": ["dl_number", "holder_name", "date_of_birth"],
        "back": ["dl_number"],
    },
    "aadhaar": {
        "front": ["aadhaar_number", "holder_name"],
        "back": ["aadhaar_number"],
    },
}

def check_field_completeness(extracted_fields, doc_type, side):
    mandatory = MANDATORY_FIELDS.get(doc_type, {}).get(side, [])
    missing = [f for f in mandatory if not extracted_fields.get(f)]
    completeness_score = (len(mandatory) - len(missing)) / len(mandatory) if mandatory else 1.0
    return completeness_score, missing
```

This replaces the old Layer B that checked regex mapper output.

### Step 6: Store in DB

Same front/back logic, but store data differently:

```python
if request.side == "front":
    record = repo.create(
        driver_id=request.driver_id,
        front_url=request.image_url,
        overall_status="pending_back",
        front_quality_score=quality_a["overall_score"],
        front_issues=quality_a["feedback"],
        front_fields={},  # No mapper fields — LLM fields stored in llm_extractions table
        ocr_raw_text_front=raw_text,  # Always save Google Vision raw output
    )
```

**Always save `ocr_raw_text_front/back`** — this is the Google Vision raw data for audit/debugging.

### Step 7: Response

```python
# Combine quality Layer A + completeness Layer B
combined_score = 0.3 * quality_a["overall_score"] + 0.7 * completeness_score

if llm_result.status == "success" and len(missing_fields) <= 1:
    status = "accepted"
    structured_data = llm_result.extracted_fields
else:
    status = "rejected"
    structured_data = llm_result.extracted_fields  # Still return partial data
    # Note: return structured_data even on rejection so client can show what was extracted
```

## Data Saved

For every request (even rejected):
- `ocr_raw_text_front/back` — Google Vision raw text (always)
- `front_quality_score/back_quality_score` — Layer A score
- `front_issues/back_issues` — Quality feedback

For quality-passed requests:
- `rc_llm_extractions` row — full LLM result, tokens, cost, extracted fields

## Config Changes

```python
# New threshold for quality gate (skip LLM if below)
QUALITY_GATE_THRESHOLD: float = 0.4  # Layer A minimum to proceed to LLM

# Existing (unchanged)
QUALITY_SCORE_THRESHOLD: float = 0.6  # Combined score for acceptance
```

## Cost Impact

| Scenario | Before (per image) | After (per image) |
|----------|--------------------|--------------------|
| Good image | Google Vision + Mapper + LLM | Google Vision + LLM |
| Bad image | Google Vision + Mapper + LLM | Google Vision only (LLM skipped) |
| Savings on bad image | — | ~₹0.5 saved (no Haiku call) |

## DB DDL Simplification

### Problem

Current schema has **15 tables** with heavy duplication:
- RC, DL, Aadhaar each have 4 nearly identical tables (Validation, LLMExtraction, GovtVerification, FieldComparison) = 12 tables
- `extractions` table is obsolete (was for Paddle vs Google comparison)
- Denormalized fields in LLMExtraction tables duplicate the `extracted_fields` JSON column
- `front_fields`, `back_fields`, `merged_fields`, `mapper_raw_output` columns are mapper-era leftovers

### Current → Simplified

| Before (15 tables) | After (5 tables) |
|---------------------|-------------------|
| `extractions` | **DROP** — obsolete Paddle/Google comparison |
| `rc_validations` | → `document_validations` (with `doc_type` column) |
| `dl_validations` | → `document_validations` |
| `aadhaar_validations` | → `document_validations` |
| `rc_llm_extractions` | → `llm_extractions` (with `doc_type` column) |
| `dl_llm_extractions` | → `llm_extractions` |
| `aadhaar_llm_extractions` | → `llm_extractions` |
| `rc_govt_verifications` | → `govt_verifications` (with `doc_type` column) |
| `dl_govt_verifications` | → `govt_verifications` |
| `aadhaar_govt_verifications` | → `govt_verifications` |
| `rc_field_comparisons` | → `field_comparisons` (with `doc_type` column) |
| `dl_field_comparisons` | → `field_comparisons` |
| `aadhaar_field_comparisons` | → `field_comparisons` |
| `govt_resellers` | **KEEP** — unchanged |
| `driver_onboarding_status` | **KEEP** — unchanged |

### New Schema (5 tables)

#### 1. `document_validations` (unified)

```sql
CREATE TABLE document_validations (
    id              VARCHAR(36) PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    -- Identifiers
    driver_id       VARCHAR(100) INDEX,
    doc_type        VARCHAR(20) NOT NULL INDEX,  -- 'rc_book' | 'driving_license' | 'aadhaar'
    doc_number      VARCHAR(50) INDEX,           -- registration_number / dl_number / aadhaar_number

    -- URLs
    front_url       TEXT,
    back_url        TEXT,

    -- Status
    overall_status          VARCHAR(20) NOT NULL DEFAULT 'pending_back' INDEX,  -- pending_back | accepted | rejected | needs_review
    verification_status     VARCHAR(20) NOT NULL DEFAULT 'pending' INDEX,       -- pending | verified | failed
    approval_method         VARCHAR(20) NOT NULL DEFAULT 'pending',             -- pending | auto | manual | govt
    approved_at             TIMESTAMP,

    -- Quality (Layer A)
    front_quality_score     FLOAT,
    back_quality_score      FLOAT,
    front_issues            JSON,   -- ["blurry", "too dark"]
    back_issues             JSON,

    -- OCR raw text (always saved)
    ocr_raw_text_front      TEXT,
    ocr_raw_text_back       TEXT,

    -- Govt verification link
    govt_match_score        FLOAT,
    llm_extraction_id       VARCHAR(36),
    govt_verification_id    VARCHAR(36),

    -- Review workflow
    requires_review         BOOLEAN DEFAULT FALSE INDEX,
    reviewed_at             TIMESTAMP,
    reviewed_by             VARCHAR(100),
    review_notes            TEXT
);
-- Compound index for common query
CREATE INDEX idx_doc_val_driver_doctype ON document_validations(driver_id, doc_type);
```

**Removed columns:**
- `front_fields`, `back_fields`, `merged_fields` — mapper output, replaced by LLM `extracted_fields`
- `mapper_raw_output` — no more mapper

#### 2. `llm_extractions` (unified)

```sql
CREATE TABLE llm_extractions (
    id                  VARCHAR(36) PRIMARY KEY,
    validation_id       VARCHAR(36) INDEX,
    doc_type            VARCHAR(20) NOT NULL,     -- 'rc_book' | 'driving_license' | 'aadhaar'
    created_at          TIMESTAMP DEFAULT NOW(),

    -- Model info
    model_provider      VARCHAR(20) NOT NULL,     -- 'anthropic' | 'openai'
    model_name          VARCHAR(50) NOT NULL,      -- 'claude-haiku-4-5-20251001'
    prompt_version      VARCHAR(20),

    -- Input
    ocr_raw_text_front  TEXT,
    ocr_raw_text_back   TEXT,
    system_prompt_used  TEXT,

    -- Output
    extracted_fields    JSON NOT NULL,             -- THE source of truth for all fields
    llm_raw_response    JSON,
    llm_confidence      FLOAT,
    status              VARCHAR(20) DEFAULT 'success' NOT NULL,
    error_message       TEXT,

    -- Cost tracking
    extraction_time_ms  INTEGER,
    token_input         INTEGER,
    token_output        INTEGER,
    cost_inr            NUMERIC(10,4)
);
```

**Removed:** All denormalized fields (`registration_number`, `owner_name`, `dl_number`, `holder_name`, etc.). Use `extracted_fields->'registration_number'` in queries instead. PostgreSQL JSON operators make this easy:
```sql
-- Find by registration number
SELECT * FROM llm_extractions
WHERE extracted_fields->>'registration_number' = 'MH12AB1234';
```

#### 3. `govt_verifications` (unified)

```sql
CREATE TABLE govt_verifications (
    id                  VARCHAR(36) PRIMARY KEY,
    validation_id       VARCHAR(36) INDEX,
    doc_type            VARCHAR(20) NOT NULL,
    reseller_id         VARCHAR(36) NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW(),

    -- Status
    status              VARCHAR(20) DEFAULT 'pending' NOT NULL,
    attempt_number      INTEGER DEFAULT 1,

    -- Response
    response_time_ms    INTEGER,
    api_cost_inr        NUMERIC(10,4),
    raw_response        JSON,
    govt_fields         JSON NOT NULL,             -- All govt fields in one JSON column
    error_message       TEXT
);
```

**Removed:** All denormalized govt fields (`govt_registration_number`, `govt_owner_name`, etc.). Use `govt_fields->>'registration_number'` instead.

#### 4. `field_comparisons` (unified)

```sql
CREATE TABLE field_comparisons (
    id                  VARCHAR(36) PRIMARY KEY,
    validation_id       VARCHAR(36) NOT NULL INDEX,
    doc_type            VARCHAR(20) NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW(),
    field_name          VARCHAR(50) NOT NULL,
    comparison_type     VARCHAR(30) NOT NULL,      -- 'llm_vs_govt' (no more 'mapper_vs_llm')
    llm_value           TEXT,
    govt_value          TEXT,
    is_match            BOOLEAN,
    similarity_score    FLOAT,
    match_method        VARCHAR(20)
);
```

**Removed:** `mapper_value`, `winner` columns — no more mapper.

#### 5. `govt_resellers` — UNCHANGED

#### 6. `driver_onboarding_status` — UPDATED

```sql
-- Change: remove doc-type-specific validation_id columns
-- Use document_validations table to look up by driver_id + doc_type instead
CREATE TABLE driver_onboarding_status (
    id                  VARCHAR(36) PRIMARY KEY,
    driver_id           VARCHAR(100) NOT NULL UNIQUE INDEX,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    onboarding_status   VARCHAR(20) NOT NULL DEFAULT 'incomplete',
    rc_status           VARCHAR(20),
    dl_status           VARCHAR(20),
    aadhaar_status      VARCHAR(20),
    cross_doc_checks    JSON,
    cross_doc_passed    BOOLEAN,
    notes               TEXT
);
```

**Removed:** `rc_validation_id`, `dl_validation_id`, `aadhaar_validation_id` — query `document_validations` by `driver_id + doc_type` instead.

### Summary

| Metric | Before | After |
|--------|--------|-------|
| Tables | 15 | 6 |
| Total columns (approx) | ~200 | ~70 |
| Denormalized fields | ~30 | 0 |
| Mapper-era columns | ~8 | 0 |

### Migration Strategy

Since this is early stage with no production data to preserve:
1. Drop all existing tables
2. Create new schema via `Base.metadata.create_all()`
3. Update `app/storage/models.py` with unified models
4. Update `app/storage/repository.py` CRUD methods
5. Update `verify_routes.py` to use new model names

### Legacy Endpoints

`/validate/rc-book` and `/extract/*` currently write to `rc_validations` / `rc_llm_extractions`. After DDL change, they would write to `document_validations` / `llm_extractions` with `doc_type='rc_book'`. This is a straightforward mapping.

## Files Modified

1. **`app/api/verify_routes.py`** — Rewrite `/verify/document` to use new pipeline
2. **`app/core/image_quality.py`** — Extract `assess_image_properties()` as standalone function usable without full extraction_service
3. **`app/storage/models.py`** — Replace 15 tables with 6 unified tables
4. **`app/storage/repository.py`** — Update CRUD for new unified models

## Files NOT Modified (legacy endpoints still use them)

- `app/core/extraction_service.py` — used by `/validate/rc-book`, `/extract/*`
- `app/mappers/*` — used by legacy endpoints
- `app/core/document_validator.py` — used by legacy endpoints
- `app/core/preprocessor.py` — used by legacy endpoints

## Testing

1. Test with good RC image (front + back) → should return accepted with structured_data
2. Test with blurry/dark image → should reject immediately without LLM call (check Railway logs for no Anthropic API call)
3. Test with good image but missing fields → should return with partial structured_data
4. Verify `ocr_raw_text_front/back` is always saved in DB
5. Verify `/validate/rc-book` still works (legacy path unchanged)
