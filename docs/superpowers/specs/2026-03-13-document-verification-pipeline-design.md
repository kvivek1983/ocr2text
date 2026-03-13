# Document Verification Pipeline — Design Spec

## Overview

Multi-document verification pipeline for driver onboarding. Accepts RC Book, Driving License, and Aadhaar card images. Runs OCR + quality checks + LLM extraction synchronously, govt API verification asynchronously, auto-approval engine after govt response. All built in parallel — each component toggleable via config.

## Documents in Scope

- **RC Book** (Registration Certificate) — vehicle ownership
- **Driving License** — driver identity + authorization
- **Aadhaar Card** — identity verification

---

## 1. Database Layer

### 1.1 Existing Tables (Modified)

**rc_validations** — ALTER to add:
- `verification_status` VARCHAR(20) DEFAULT 'pending'
- `approval_method` VARCHAR(20) DEFAULT 'pending'
- `approved_at` TIMESTAMP
- `govt_match_score` FLOAT
- `llm_extraction_id` VARCHAR(36) FK
- `govt_verification_id` VARCHAR(36) FK
- `ocr_raw_text_front` TEXT
- `ocr_raw_text_back` TEXT
- `mapper_raw_output` JSONB

### 1.2 Table Summary

**Total: 2 existing + 14 new = 16 tables in the system.**

Existing tables (2): `extractions` (untouched), `rc_validations` (ALTERed with new columns).

New tables (14):

**Shared (1):**
- `govt_resellers` — reseller registry with priority ordering, circuit breaker state, reliability stats, multi-doc-type support (`supported_doc_types`, `endpoints_by_doc_type`, `response_mappers_by_doc_type`)

**Per document type (4 tables x 3 doc types = 12):**
- `*_validations` (DL, Aadhaar) — same pattern as RC. Anchor table with image URLs, quality scores, raw OCR text, mapper output, verification/approval status, review workflow. Note: RC already exists, only DL + Aadhaar are new tables (2 new).
- `*_llm_extractions` (RC, DL, Aadhaar) — LLM output per extraction. Raw API response + system prompt preserved for prompt improvement loop. Denormalized key fields + token/cost tracking (3 new).
- `*_govt_verifications` (RC, DL, Aadhaar) — govt reseller API response per attempt. Raw response preserved. 10 critical fields denormalized, everything else in `govt_fields` JSONB. Attempt tracking for fallback chain (3 new).
- `*_field_comparisons` (RC, DL, Aadhaar) — field-level diff: mapper vs LLM vs govt. Fuzzy similarity scores. One row per field per comparison run (3 new).

**Cross-document (1):**
- `driver_onboarding_status` — one row per driver. FKs to active validation per doc type. Cross-doc checks JSONB. Onboarding status: incomplete -> in_progress -> verified -> blocked -> expired

**Concrete new table list (14):** govt_resellers, dl_validations, aadhaar_validations, rc_llm_extractions, dl_llm_extractions, aadhaar_llm_extractions, rc_govt_verifications, dl_govt_verifications, aadhaar_govt_verifications, rc_field_comparisons, dl_field_comparisons, aadhaar_field_comparisons, driver_onboarding_status. Total = 14 new tables + 1 ALTERed (rc_validations) + 1 untouched (extractions) = 16 in the system.

### 1.3 Key Design Principles

- **Raw data always preserved:** ocr_raw_text, mapper_raw_output, llm_raw_response, system_prompt_used, raw_response (govt). Never modified after storage.
- **Denormalize only what's queried:** 10 critical fields as columns per govt table, ~5 per LLM table. Everything else in JSONB.
- **VARCHAR(36) UUID PKs** using `uuid.uuid4()`. Matches existing codebase pattern.
- **NOT NULL on status columns:** `verification_status`, `approval_method`, `overall_status` are NOT NULL with defaults across all validation tables (including the ALTER to rc_validations).
- **Concurrency on driver_onboarding_status:** Use `SELECT FOR UPDATE` when updating a driver's onboarding row, since multiple document verifications for the same driver can complete concurrently. The upsert in `DriverOnboardingRepository` uses `ON CONFLICT (driver_id) DO UPDATE` with row-level locking.
- **cost_inr columns:** Use NUMERIC(10,4) instead of FLOAT for cost tracking columns (`cost_inr`, `api_cost_inr`) to avoid floating-point precision issues in aggregations.

### 1.4 State Machines (Application-Enforced)

**overall_status:** pending_back -> pending_extraction -> pending_verification -> pending_review -> approved / rejected

**verification_status:** pending -> in_progress -> verified -> mismatch -> not_found -> failed -> skipped

**approval_method:** pending -> auto_approved / auto_rejected / manual_review -> manual_approved / manual_rejected

### 1.5 Repository Pattern

New repositories in `app/storage/repository.py`:
- `DLValidationRepository`, `AadhaarValidationRepository` — same ops as existing `RCValidationRepository`
- `LLMExtractionRepository` — create, get_by_validation_id (generic across doc types)
- `GovtVerificationRepository` — create, get_by_validation_id, get_by_reg_number
- `FieldComparisonRepository` — bulk_create, get_by_validation_id
- `GovtResellerRepository` — get_active_ordered, update_stats, update_circuit_state
- `DriverOnboardingRepository` — upsert, get_by_driver_id, update_doc_status

### 1.6 SQL Execution

- SQLAlchemy models in `app/storage/models.py` using existing `DeclarativeBase`
- Tables auto-created via `Base.metadata.create_all()` on startup
- Raw SQL also run against Railway Postgres for indexes and FK constraints
- Schema files: `rc_verification_schema_v2.sql` (run first), `driver_onboarding_multi_doc_schema.sql` (run second)

---

## 2. LLM Extractor Module

### 2.1 Structure

```
app/llm/
├── __init__.py
├── extractor.py          # LLMExtractor class
├── schemas.py            # Pydantic models for LLM I/O
└── prompts/
    ├── rc_book_v1.txt
    ├── driving_license_v1.txt
    └── aadhaar_v1.txt
```

### 2.2 LLMExtractor Class

- **Two providers:** Anthropic (`claude-haiku-4-5-20251001`) + OpenAI (`gpt-4o-mini`)
- **Provider toggle:** `LLM_PROVIDER` env var sets default, can override per-call
- **Async clients:** `anthropic.AsyncAnthropic` and `openai.AsyncOpenAI`
- **Prompt loading:** Reads versioned `.txt` files from `app/llm/prompts/`, injects `{side}` variable
- **Response parsing:** LLM returns JSON -> parse into doc-specific Pydantic model -> fallback to raw JSON if parsing fails (status='partial')
- **Cost calculation:** Token counts from API response x per-token rate (configurable per model)
- **Error handling:** Timeout (30s default), API errors, JSON parse failures -> stored with status='failed' + error_message. **Retry policy:** 1 retry with 2s delay on timeout or 5xx errors. No retry on 4xx or parse failures.
- **Returns:** `LLMExtractionResult` with extracted_fields, metadata, raw_response, system_prompt_used

### 2.3 Pydantic Schemas

**Per doc type (extraction fields):**
- `RCExtractionFields` — registration_number, owner_name, vehicle_class, fuel_type, chassis_number, engine_number, manufacturer, model, registration_date, validity_date, rto_code, rto_name, insurance_upto, fitness_upto, body_type, color, seat_capacity, emission_norms
- `DLExtractionFields` — dl_number, holder_name, father_husband_name, date_of_birth, blood_group, issue_date, validity_nt, validity_tr, issuing_authority, cov_details, address
- `AadhaarExtractionFields` — aadhaar_number, holder_name, date_of_birth, gender, father_name, address, pin_code

**Shared:**
- `LLMExtractionResult` — extracted_fields, metadata (provider, model, tokens, cost, time_ms), raw_response, system_prompt_used, status, error_message
- `LLMExtractionMetadata` — llm_provider, llm_model, extraction_time_ms, prompt_version. Note: `ocr_engine` is included in the API response's `extraction_metadata` for convenience (so the caller sees the full picture) but it comes from the OCR step, not the LLM step.

**API schemas:**
- `VerifyDocumentRequest` — image_type ("rc_book" | "driving_license" | "aadhaar"), side ("front" | "back"), driver_id, image_url
- `VerifyDocumentResponse` — request_id, status ("accepted" | "rejected"), quality_score, authenticity_passed, rejection_reasons[], message, structured_data (nullable), extraction_metadata

### 2.4 System Prompts

Each prompt follows the same structure:
1. Role setup (expert at extracting from Indian document OCR text)
2. Context ({side} side, OCR errors expected)
3. Field list with format specifications
4. Rules (null for missing, date normalization, OCR error correction patterns)
5. "Return JSON only"

Prompt files are plain `.txt` (not YAML). Versioned: `rc_book_v1.txt`, `rc_book_v2.txt`, etc. `prompt_version` stored per extraction for traceability.

### 2.5 Config (Environment Variables)

```
LLM_PROVIDER=anthropic
LLM_MODEL_ANTHROPIC=claude-haiku-4-5-20251001
LLM_MODEL_OPENAI=gpt-4o-mini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LLM_TIMEOUT_SECONDS=30
```

---

## 3. Govt API Client Module

### 3.1 Structure

```
app/govt/
├── __init__.py
├── client.py             # GovtAPIClient — fallback chain + circuit breaker
├── schemas.py            # GovtFields, GovtVerificationResult
└── mappers/
    ├── __init__.py       # GOVT_MAPPER_REGISTRY
    ├── base.py           # BaseGovtMapper ABC
    ├── gridlines.py      # GridlinesMapper
    ├── cashfree.py       # CashfreeMapper
    └── hyperverge.py     # HyperVergeMapper
```

### 3.2 GovtAPIClient Class

- **Startup:** Loads active resellers from `govt_resellers` table ordered by `priority ASC`
- **Fallback chain:** Try primary -> on failure, try next -> continue until success or all exhausted
- **Circuit breaker per reseller:**
  - `consecutive_failures >= 5` -> state = `open` (blocked)
  - After 5 min -> `half_open` (allow 1 test call)
  - Test succeeds -> `closed`, reset failures
  - Test fails -> back to `open`, reset timer
- **Per-call flow:**
  1. Filter out `circuit_state = 'open'` resellers
  2. Build request from `request_template` + document number
  3. Call reseller API (async httpx, timeout from `govt_resellers.timeout_ms`)
  4. On success -> run response through mapper -> store in `*_govt_verifications`
  5. On failure -> log, increment `consecutive_failures`, try next reseller
  6. Update reliability stats
- **Multi-doc support:** Uses `endpoints_by_doc_type` and `response_mappers_by_doc_type`

### 3.3 Reseller Mappers

**BaseGovtMapper:**
```python
class BaseGovtMapper(ABC):
    @abstractmethod
    def normalize(self, raw_response: dict, doc_type: str) -> GovtFields: ...
```

**3 resellers (Gridlines, Cashfree, HyperVerge).** Note: the Phase 1 reference SQL files mention SurePass and Signzy as example names — those were placeholders. The actual resellers being integrated are the 3 listed here.

**RC field mappings:**

| Field | Gridlines | Cashfree | HyperVerge |
|---|---|---|---|
| owner_name | `data.rc_data.owner_data.name` | `owner` | `result.rcInfo.owner_name` |
| chassis_number | `data.rc_data.vehicle_data.chassis_number` | `chassis` | `result.rcInfo.chassis_no` |
| engine_number | `data.rc_data.vehicle_data.engine_number` | `engine` | `result.rcInfo.engine_no` |
| fuel_type | `data.rc_data.vehicle_data.fuel_type` | `type` | `result.rcInfo.fuel_descr` |
| vehicle_class | `data.rc_data.vehicle_data.category` | `class` | `result.rcInfo.vehicle_class_desc` |
| rc_status | `data.rc_data.status` | `rc_status` | `result.rcInfo.status` |
| registration_number | (from request) | `reg_no` | `result.rcInfo.reg_no` |
| insurance_upto | `data.rc_data.insurance_data.expiry_date` | `vehicle_insurance_upto` | `result.rcInfo.vehicle_insurance_details.insurance_upto` |
| fitness_upto | N/A (null) | N/A (null) | `result.rcInfo.fit_upto` |

**HyperVergeMapper** auto-detects response format:
- `result.rcInfo.*` (Advanced/Plus/Detailed Verification endpoints — flat, snake_case)
- `result.data.rcData.*` (Detailed endpoint — nested, camelCase)

All unmapped fields go into `govt_fields` JSONB.

### 3.4 GovtFields Schema

**RC:** owner_name, vehicle_class, fuel_type, chassis_number, engine_number, registration_number, rc_status, fitness_upto, insurance_upto + extra_fields dict

**DL:** holder_name, father_husband_name, dob, dl_number, dl_status, validity_nt, validity_tr, cov_details, issuing_authority + extra_fields dict

**Aadhaar:** holder_name, dob, gender, address, pin_code, aadhaar_status + extra_fields dict

### 3.5 DL & Aadhaar Govt Mapper Field Mappings

DL and Aadhaar reseller mappings will be built when reseller API docs for those document types are provided. The framework supports it — each reseller's `endpoints_by_doc_type` and `response_mappers_by_doc_type` config handles routing. For v1, RC mappers are fully specified; DL and Aadhaar mappers are stub implementations that store raw responses in `govt_fields` JSONB without denormalization until field mappings are confirmed.

### 3.6 Reseller Credential Storage

Reseller API keys are stored as **Railway environment variable names** in `govt_resellers.auth_config` JSONB — e.g., `{"env_var": "GRIDLINES_API_KEY"}`. The application reads the env var name from the DB, then fetches the actual secret from `os.environ`. Raw API keys are never stored in the database.

---

## 4. Verification & Auto-Approval Engine

### 4.1 Structure

```
app/verification/
├── __init__.py
├── engine.py             # AutoApprovalEngine
├── comparator.py         # FieldComparator
└── cross_doc.py          # CrossDocValidator
```

### 4.2 AutoApprovalEngine

Runs after govt API response arrives (async). Takes validation record + LLM extraction + govt verification, returns approval decision.

**RC auto-approval criteria (ALL must pass):**
1. `front_quality_score >= threshold` (default 0.7)
2. `back_quality_score >= threshold` (default 0.7)
3. LLM extraction `status = 'success'`
4. Govt verification `status = 'success'`
5. `govt_match_score >= threshold` (default 0.85)
6. Critical fields match: chassis_number, engine_number, registration_number
7. `govt_rc_status = 'ACTIVE'`
8. `govt_fitness_upto` not expired (if available)
9. `govt_insurance_upto` not expired

**DL auto-approval:** Same pattern + DL status = 'ACTIVE', transport validity not expired, COV covers vehicle class.

**Aadhaar auto-approval:** Same pattern + UIDAI status = 'VALID', not deactivated. Note: Aadhaar govt verification initially uses **demographic verification only** (pass Aadhaar number, get demographics back). OTP-based e-KYC (`otp_ekyc` method) requires user interaction (OTP sent to Aadhaar-linked mobile) and is **out of scope for v1** — the pipeline's fire-and-forget async model cannot support user-interaction steps. The `verification_method` column in `aadhaar_govt_verifications` defaults to `'demographic'`; OTP e-KYC will be added in a future phase with a dedicated interactive flow.

**Outcomes:**
- `auto_approved` — all checks passed
- `auto_rejected` — critical failure (RC not ACTIVE, expired fitness, etc.)
- `manual_review` — borderline scores, partial mismatches

All thresholds configurable via env vars.

### 4.3 FieldComparator

- Takes mapper fields, LLM fields, govt fields for a validation record
- Compares field-by-field: exact match for IDs/numbers, fuzzy match (Levenshtein/token ratio) for names/addresses
- Produces one `*_field_comparisons` row per field per comparison run
- Computes overall `govt_match_score` (weighted average across critical fields)
- Identifies `winner` per field when govt truth available

### 4.4 CrossDocValidator

Runs after all 3 documents individually approved. Updates `driver_onboarding_status`.

**Cross-document checks:**
- DL holder name ~ Aadhaar name (fuzzy, configurable threshold)
- DL DOB = Aadhaar DOB (exact match)
- DL COV covers RC vehicle class
- DL transport validity not expired
- All 3 docs belong to same person (name + DOB consistency)

**Updates onboarding_status:** incomplete -> in_progress -> verified / blocked

---

## 5. API Endpoint & Pipeline Orchestration

### 5.1 New Endpoint: POST /verify/document

Lives in `app/api/verify_routes.py` (new file, registered on existing FastAPI app).

**Pipeline (synchronous, target <10s initially, optimize to <5s later):**

Note: PaddleOCR cold start can take 2-3s, LLM call adds 1-2s, image fetch from S3 adds 0.5-1s. Realistic initial latency is 4-6s, potentially up to 10s on cold starts. Set initial timeout at 10s and optimize down (engine warm-up, connection pooling, prompt shortening) rather than fighting timeouts in week 1.

```
1. Validate input + create/update *_validations record (see 5.1.1 for front/back logic)
2. Fetch image from URL (existing image_utils)
3. Run OCR (PaddleOCR, fallback EasyOCR) -> store raw text
4. asyncio.gather:
   ├── 4a. Quality + Authenticity + Mapper (existing core modules)
   └── 4b. LLM Extraction (new module)
5. Store all results in DB
6. If quality fails -> return status:"rejected" + rejection_reasons
7. If quality passes -> return status:"accepted" + LLM structured_data
8. Fire-and-forget: trigger govt verification as background task
```

### 5.1.1 Front/Back Upload Logic

The endpoint handles both sides of a document using the same pattern as existing `rc_validations`:

**Front upload (side="front"):**
1. Check if driver_id already has a `pending_back` record for this doc type
2. If yes → reject (front already uploaded, waiting for back)
3. If no → create new `*_validations` record with `front_url`, set `overall_status = 'pending_back'`
4. Run OCR + quality + LLM on front only, store in `front_fields`, `front_quality_score`

**Back upload (side="back"):**
1. Look up existing `pending_back` record for this driver_id + doc type
2. If not found → reject (must upload front first)
3. If found → update record: set `back_url`, run OCR + quality + LLM on back
4. Merge front_fields + back_fields → `merged_fields`
5. Set `overall_status = 'pending_verification'` (or `pending_review` if quality issues)
6. Fire-and-forget: trigger govt verification

This logic applies identically to RC, DL, and Aadhaar. The `get_pending_back_for_driver(driver_id)` pattern already exists in `RCValidationRepository` — replicate for DL and Aadhaar repositories.

**Govt verification is async (not in sync response).** Govt APIs are unreliable — response time varies, may timeout. Background task stores result in `*_govt_verifications` when complete. Auto-approval engine runs after govt response arrives.

**Background task mechanism:** Uses FastAPI `BackgroundTasks` for simplicity. If the task is lost (worker restart), a recovery mechanism detects records stuck in `verification_status = 'pending'` for >10 minutes and re-triggers govt verification. This is implemented as a periodic check in the startup event or a lightweight `/admin/retry-stuck` endpoint. No external queue (Celery/Redis) needed at current scale.

### 5.2 Status Check Endpoint

```
GET /verify/document/{validation_id}/status
```

Returns current `verification_status`, `approval_method`, `govt_match_score`. Allows app to poll for govt verification completion.

### 5.3 Endpoint Security

Batch endpoints (`/backfill/*`, `/backtest/*`, `/admin/*`) are protected with an `ADMIN_API_KEY` header check. The key is stored as an environment variable. Regular extraction/verification endpoints remain open (matching existing pattern).

### 5.4 Backfill Endpoint

```
POST /backfill/rc
```

Triggers MySQL -> Postgres migration:
- `rc_book_master` -> `rc_govt_verifications`
- `rc_book_detail` -> `rc_validations`
- Field mappings per implementation plan Section 1.1 and 1.2
- Creates `legacy_import` reseller entry in `govt_resellers`
- Batch processing (1000 rows), idempotent (skips existing), progress logging
- Joins on registration_number to set `govt_verification_id` FK

### 5.5 Backtest Endpoint

```
POST /backtest/rc
```

Runs LLM extraction on historical data and compares against govt truth:
1. Query `rc_validations` where govt verification exists + S3 URLs accessible
2. For each: fetch image -> OCR -> LLM extract -> store in `rc_llm_extractions`
3. Compare LLM vs govt truth -> store in `rc_field_comparisons`
4. Compare mapper vs govt truth -> store in `rc_field_comparisons`
5. Return per-field accuracy report + overall auto-approval rate estimate

Parameters: sample_size (default 500), doc_type, prompt_version.
Resumable — skips already-processed records.

---

## 6. Config & Environment Variables

```env
# LLM
LLM_PROVIDER=anthropic
LLM_MODEL_ANTHROPIC=claude-haiku-4-5-20251001
LLM_MODEL_OPENAI=gpt-4o-mini
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
LLM_TIMEOUT_SECONDS=30

# Govt API (credentials in govt_resellers table, not env vars)
# Reseller API keys stored in govt_resellers.auth_config (encrypted ref)

# Quality thresholds
QUALITY_SCORE_THRESHOLD=0.6
BLUR_THRESHOLD=0.5
BRIGHTNESS_MIN=0.3
BRIGHTNESS_MAX=0.9

# Auto-approval thresholds
AUTO_APPROVAL_QUALITY_THRESHOLD=0.7
AUTO_APPROVAL_MATCH_THRESHOLD=0.85
FUZZY_NAME_MATCH_THRESHOLD=0.85

# Admin
ADMIN_API_KEY=             # protects /backfill, /backtest, /admin endpoints

# Govt reseller keys (referenced by name in govt_resellers.auth_config)
GRIDLINES_API_KEY=
CASHFREE_API_KEY=
HYPERVERGE_API_KEY=

# Database
DATABASE_URL=postgresql://...
```

---

## 7. Testing Strategy

- **Unit tests** for each new module: LLM extractor (mock API calls), govt mappers (sample responses), auto-approval engine (threshold edge cases), field comparator (fuzzy matching), cross-doc validator
- **Integration tests** for the full pipeline: mock OCR + mock LLM + mock govt -> verify end-to-end flow
- **Mapper tests** with real reseller sample responses (Gridlines, Cashfree, HyperVerge) to validate field extraction
- Follow existing test patterns (pytest, pytest-asyncio)

---

## 8. Key Constraints

1. **Existing system untouched** — new endpoint is additive. Current `/extract/*` and `/validate/rc-book` continue working.
2. **Synchronous endpoint, async govt** — `/verify/document` returns in <5s with OCR + LLM results. Govt verification runs as background task.
3. **Raw data always preserved** — every stage stores raw input/output for the prompt improvement loop.
4. **Both LLM providers supported** — toggle via env var, switch without code change.
5. **All components toggleable** — build everything in parallel, enable/disable via config.
6. **Cost tracking** — every LLM call and govt API call logs token counts and cost_inr.
7. **PostgreSQL only** — new tables in Postgres. Existing tables remain as-is.
