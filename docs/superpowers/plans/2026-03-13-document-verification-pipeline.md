# Document Verification Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-document verification pipeline (RC Book, DL, Aadhaar) with LLM extraction, govt API verification, and auto-approval engine.

**Architecture:** FastAPI endpoint `POST /verify/document` runs OCR + quality + LLM synchronously, fires govt verification as async background task. Auto-approval engine runs after govt response. All raw data preserved at every stage.

**Tech Stack:** FastAPI, SQLAlchemy (Postgres), Anthropic SDK, OpenAI SDK, httpx, PaddleOCR, thefuzz (fuzzy matching), pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-13-document-verification-pipeline-design.md`

---

## Chunk 1: Foundation (Config + Models + Repositories)

### Task 1: Config Updates

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test for new config fields**

```python
# tests/test_config.py — append to existing file

def test_llm_config_defaults():
    """New LLM config fields have sensible defaults."""
    from app.config import Settings
    s = Settings(DATABASE_URL="postgresql://x:x@localhost/test")
    assert s.LLM_PROVIDER == "anthropic"
    assert s.LLM_MODEL_ANTHROPIC == "claude-haiku-4-5-20251001"
    assert s.LLM_MODEL_OPENAI == "gpt-4o-mini"
    assert s.LLM_TIMEOUT_SECONDS == 30
    assert s.QUALITY_SCORE_THRESHOLD == 0.6
    assert s.AUTO_APPROVAL_QUALITY_THRESHOLD == 0.7
    assert s.AUTO_APPROVAL_MATCH_THRESHOLD == 0.85
    assert s.FUZZY_NAME_MATCH_THRESHOLD == 0.85
    assert s.ADMIN_API_KEY is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_llm_config_defaults -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'LLM_PROVIDER'`

- [ ] **Step 3: Add new config fields to Settings**

```python
# app/config.py — add these fields to the Settings class

    # LLM
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL_ANTHROPIC: str = "claude-haiku-4-5-20251001"
    LLM_MODEL_OPENAI: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LLM_TIMEOUT_SECONDS: int = 30

    # Quality thresholds
    QUALITY_SCORE_THRESHOLD: float = 0.6
    BLUR_THRESHOLD: float = 0.5
    BRIGHTNESS_MIN: float = 0.3
    BRIGHTNESS_MAX: float = 0.9

    # Auto-approval thresholds
    AUTO_APPROVAL_QUALITY_THRESHOLD: float = 0.7
    AUTO_APPROVAL_MATCH_THRESHOLD: float = 0.85
    FUZZY_NAME_MATCH_THRESHOLD: float = 0.85

    # Admin
    ADMIN_API_KEY: Optional[str] = None

    # Govt reseller keys (referenced by name in govt_resellers.auth_config)
    GRIDLINES_API_KEY: Optional[str] = None
    CASHFREE_API_KEY: Optional[str] = None
    HYPERVERGE_API_KEY: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_llm_config_defaults -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add LLM, govt API, and auto-approval config fields"
```

---

### Task 2: SQLAlchemy Models — Shared + RC Tables

**Files:**
- Modify: `app/storage/models.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing test for new model imports**

```python
# tests/test_new_models.py

import pytest
from app.storage.models import (
    GovtReseller,
    RCLLMExtraction,
    RCGovtVerification,
    RCFieldComparison,
)


def test_govt_reseller_model_exists():
    r = GovtReseller(name="test", provider_code="test_code")
    assert r.name == "test"
    assert r.is_active is True  # default
    assert r.circuit_state == "closed"  # default


def test_rc_llm_extraction_model_exists():
    e = RCLLMExtraction(
        model_provider="anthropic",
        model_name="claude-haiku-4-5-20251001",
        extracted_fields={"registration_number": "MH47BL1775"},
    )
    assert e.model_provider == "anthropic"
    assert e.status == "success"  # default


def test_rc_govt_verification_model_exists():
    v = RCGovtVerification(reseller_id="abc")
    assert v.status == "pending"  # default
    assert v.attempt_number == 1  # default


def test_rc_field_comparison_model_exists():
    c = RCFieldComparison(
        validation_id="abc",
        field_name="owner_name",
        comparison_type="llm_vs_govt",
    )
    assert c.field_name == "owner_name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_new_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'GovtReseller'`

- [ ] **Step 3: Add new columns to RCValidation model**

Add these columns to the existing `RCValidation` class in `app/storage/models.py`:

```python
    # --- New verification pipeline columns ---
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    mapper_raw_output = Column(JSON, nullable=True)
```

- [ ] **Step 4: Add GovtReseller model**

```python
class GovtReseller(Base):
    """Registry of govt data providers with circuit breaker state."""
    __tablename__ = "govt_resellers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    name = Column(String(100), nullable=False)
    provider_code = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=1, nullable=False)

    supported_doc_types = Column(JSON, nullable=True)  # ["rc_book", "driving_license"]
    endpoints_by_doc_type = Column(JSON, nullable=True)  # {"rc_book": "https://..."}
    response_mappers_by_doc_type = Column(JSON, nullable=True)  # {"rc_book": "gridlines"}
    request_template = Column(JSON, nullable=True)
    auth_config = Column(JSON, nullable=True)  # {"env_var": "GRIDLINES_API_KEY"}
    timeout_ms = Column(Integer, default=10000, nullable=False)

    # Circuit breaker
    circuit_state = Column(String(20), default="closed", nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_failure_at = Column(DateTime, nullable=True)

    # Reliability stats
    total_requests = Column(Integer, default=0, nullable=False)
    successful_requests = Column(Integer, default=0, nullable=False)
    avg_response_ms = Column(Integer, nullable=True)
```

- [ ] **Step 5: Add RCLLMExtraction model**

```python
class RCLLMExtraction(Base):
    """LLM extraction output for RC Book."""
    __tablename__ = "rc_llm_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    model_provider = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    prompt_version = Column(String(20), nullable=True)
    llm_raw_response = Column(JSON, nullable=True)
    system_prompt_used = Column(Text, nullable=True)
    extracted_fields = Column(JSON, nullable=False)
    llm_confidence = Column(Float, nullable=True)
    extraction_time_ms = Column(Integer, nullable=True)
    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)
    cost_inr = Column(Numeric(10, 4), nullable=True)  # import Numeric from sqlalchemy
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)

    # Denormalized key fields
    registration_number = Column(String(20), nullable=True)
    owner_name = Column(String(200), nullable=True)
    vehicle_class = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    chassis_number = Column(String(50), nullable=True)
    engine_number = Column(String(50), nullable=True)
    registration_date = Column(DateTime, nullable=True)
    validity_date = Column(DateTime, nullable=True)
    rto_code = Column(String(20), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model_field = Column("model", String(100), nullable=True)
```

- [ ] **Step 6: Add RCGovtVerification model**

```python
class RCGovtVerification(Base):
    """Govt reseller API response for RC verification."""
    __tablename__ = "rc_govt_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=True, index=True)
    reseller_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String(20), default="pending", nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    api_cost_inr = Column(Numeric(10, 4), nullable=True)
    raw_response = Column(JSON, nullable=True)
    govt_fields = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Denormalized critical fields
    govt_registration_number = Column(String(20), nullable=True, index=True)
    govt_owner_name = Column(String(200), nullable=True)
    govt_chassis_number = Column(String(50), nullable=True)
    govt_engine_number = Column(String(50), nullable=True)
    govt_fuel_type = Column(String(50), nullable=True)
    govt_vehicle_class = Column(String(50), nullable=True)
    govt_rc_status = Column(String(20), nullable=True)
    govt_fitness_upto = Column(DateTime, nullable=True)
    govt_insurance_upto = Column(DateTime, nullable=True)
```

- [ ] **Step 7: Add RCFieldComparison model**

```python
class RCFieldComparison(Base):
    """Field-level diff: mapper vs LLM vs govt for RC."""
    __tablename__ = "rc_field_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    field_name = Column(String(50), nullable=False)
    comparison_type = Column(String(30), nullable=False)  # mapper_vs_govt, llm_vs_govt, mapper_vs_llm

    mapper_value = Column(Text, nullable=True)
    llm_value = Column(Text, nullable=True)
    govt_value = Column(Text, nullable=True)
    is_match = Column(Boolean, nullable=True)
    similarity_score = Column(Float, nullable=True)
    match_method = Column(String(20), nullable=True)  # exact, fuzzy, normalized
    winner = Column(String(20), nullable=True)  # mapper, llm, neither
```

- [ ] **Step 8: Run tests to verify models work**

Run: `pytest tests/test_new_models.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add app/storage/models.py tests/test_new_models.py
git commit -m "feat: add GovtReseller, RCLLMExtraction, RCGovtVerification, RCFieldComparison models + extend RCValidation"
```

---

### Task 3: SQLAlchemy Models — DL + Aadhaar + Cross-Doc Tables

**Files:**
- Modify: `app/storage/models.py`
- Test: `tests/test_new_models.py`

- [ ] **Step 1: Write failing test for DL/Aadhaar models**

```python
# tests/test_new_models.py — append

from app.storage.models import (
    DLValidation, DLLLMExtraction, DLGovtVerification, DLFieldComparison,
    AadhaarValidation, AadhaarLLMExtraction, AadhaarGovtVerification, AadhaarFieldComparison,
    DriverOnboardingStatus,
)


def test_dl_validation_model():
    v = DLValidation(driver_id="123")
    assert v.overall_status == "pending_back"
    assert v.verification_status == "pending"


def test_aadhaar_validation_model():
    v = AadhaarValidation(driver_id="123")
    assert v.overall_status == "pending_back"


def test_driver_onboarding_status_model():
    s = DriverOnboardingStatus(driver_id="123")
    assert s.onboarding_status == "incomplete"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_new_models.py::test_dl_validation_model -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Add DLValidation model**

Same column pattern as `RCValidation` (with extended verification columns), but with `dl_number` instead of `registration_number`. Tablename: `dl_validations`.

```python
class DLValidation(Base):
    __tablename__ = "dl_validations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    driver_id = Column(String(100), nullable=True, index=True)
    front_url = Column(Text, nullable=True)
    back_url = Column(Text, nullable=True)
    overall_status = Column(String(20), nullable=False, default="pending_back", index=True)
    front_quality_score = Column(Float, nullable=True)
    back_quality_score = Column(Float, nullable=True)
    front_issues = Column(JSON, nullable=True)
    back_issues = Column(JSON, nullable=True)
    front_fields = Column(JSON, nullable=True)
    back_fields = Column(JSON, nullable=True)
    merged_fields = Column(JSON, nullable=True)
    dl_number = Column(String(20), nullable=True, index=True)
    requires_review = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
    # Verification pipeline
    ocr_raw_text_front = Column(Text, nullable=True)
    ocr_raw_text_back = Column(Text, nullable=True)
    mapper_raw_output = Column(JSON, nullable=True)
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    approval_method = Column(String(20), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    govt_match_score = Column(Float, nullable=True)
    llm_extraction_id = Column(String(36), nullable=True)
    govt_verification_id = Column(String(36), nullable=True)
```

- [ ] **Step 4: Add AadhaarValidation model**

Same pattern, `aadhaar_number` instead of `dl_number`. Tablename: `aadhaar_validations`.

- [ ] **Step 5: Add DLLLMExtraction, DLGovtVerification, DLFieldComparison**

Same column pattern as RC counterparts. DL-specific denormalized fields on LLM extraction: `dl_number, holder_name, father_husband_name, date_of_birth, blood_group, issue_date, validity_nt, validity_tr, issuing_authority, cov_details (JSON), address`.

- [ ] **Step 6: Add AadhaarLLMExtraction, AadhaarGovtVerification, AadhaarFieldComparison**

Same pattern. Aadhaar-specific denormalized fields: `aadhaar_number, holder_name, date_of_birth, gender, father_name, address, pin_code`. AadhaarGovtVerification adds `verification_method` column (default `'demographic'`).

- [ ] **Step 7: Add DriverOnboardingStatus model**

```python
class DriverOnboardingStatus(Base):
    __tablename__ = "driver_onboarding_status"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    onboarding_status = Column(String(20), nullable=False, default="incomplete")

    rc_validation_id = Column(String(36), nullable=True)
    rc_status = Column(String(20), nullable=True)
    dl_validation_id = Column(String(36), nullable=True)
    dl_status = Column(String(20), nullable=True)
    aadhaar_validation_id = Column(String(36), nullable=True)
    aadhaar_status = Column(String(20), nullable=True)

    cross_doc_checks = Column(JSON, nullable=True)
    cross_doc_passed = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_new_models.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add app/storage/models.py tests/test_new_models.py
git commit -m "feat: add DL, Aadhaar validation/extraction/verification models + DriverOnboardingStatus"
```

---

### Task 4: Repositories

**Files:**
- Modify: `app/storage/repository.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: Write failing test for new repositories**

```python
# tests/test_repositories.py

import pytest
from unittest.mock import MagicMock
from app.storage.repository import (
    DLValidationRepository,
    AadhaarValidationRepository,
    LLMExtractionRepository,
    GovtVerificationRepository,
    FieldComparisonRepository,
    GovtResellerRepository,
    DriverOnboardingRepository,
)


def test_dl_validation_repo_has_get_pending_back():
    repo = DLValidationRepository(session=MagicMock())
    assert hasattr(repo, "get_pending_back_for_driver")
    assert hasattr(repo, "create")
    assert hasattr(repo, "update")


def test_llm_extraction_repo_has_create():
    repo = LLMExtractionRepository(session=MagicMock(), doc_type="rc_book")
    assert hasattr(repo, "create")
    assert hasattr(repo, "get_by_validation_id")


def test_govt_reseller_repo_has_get_active():
    repo = GovtResellerRepository(session=MagicMock())
    assert hasattr(repo, "get_active_ordered")
    assert hasattr(repo, "update_circuit_state")


def test_driver_onboarding_repo_has_upsert():
    repo = DriverOnboardingRepository(session=MagicMock())
    assert hasattr(repo, "upsert")
    assert hasattr(repo, "get_by_driver_id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repositories.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement DLValidationRepository and AadhaarValidationRepository**

Follow the exact same pattern as `RCValidationRepository` — same methods: `create`, `get_by_id`, `get_pending_back_for_driver`, `update`, `get_review_queue`, `count_review_queue`, `mark_reviewed`. Use `DLValidation` and `AadhaarValidation` models respectively.

- [ ] **Step 4: Implement LLMExtractionRepository**

```python
class LLMExtractionRepository:
    """Generic repository for LLM extractions — works across doc types."""

    # Model lookup by doc type
    _MODELS = {
        "rc_book": RCLLMExtraction,
        "driving_license": DLLLMExtraction,
        "aadhaar": AadhaarLLMExtraction,
    }

    def __init__(self, session: Session, doc_type: str):
        self.session = session
        self.model = self._MODELS[doc_type]

    def create(self, **kwargs):
        record = self.model(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_validation_id(self, validation_id: str):
        return (
            self.session.query(self.model)
            .filter(self.model.validation_id == validation_id)
            .order_by(self.model.created_at.desc())
            .first()
        )
```

- [ ] **Step 5: Implement GovtVerificationRepository, FieldComparisonRepository, GovtResellerRepository, DriverOnboardingRepository**

`GovtVerificationRepository` — same pattern as LLMExtractionRepository (model lookup by doc_type). Methods: `create`, `get_by_validation_id`, `get_by_reg_number`.

`FieldComparisonRepository` — model lookup by doc_type. Methods: `bulk_create(comparisons: list)`, `get_by_validation_id`.

`GovtResellerRepository` — single model. Methods: `get_active_ordered(doc_type)` (filter by `is_active=True`, `supported_doc_types` contains doc_type, order by `priority ASC`), `update_stats`, `update_circuit_state`.

`DriverOnboardingRepository` — Methods: `get_by_driver_id`, `upsert(driver_id, **kwargs)` (ON CONFLICT handled via get-or-create pattern with SELECT FOR UPDATE).

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_repositories.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add app/storage/repository.py tests/test_repositories.py
git commit -m "feat: add repositories for DL, Aadhaar, LLM extraction, govt verification, field comparison, onboarding"
```

---

## Chunk 2: LLM Module

### Task 5: LLM Pydantic Schemas

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/schemas.py`
- Test: `tests/test_llm_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_llm_schemas.py

from app.llm.schemas import (
    RCExtractionFields,
    DLExtractionFields,
    AadhaarExtractionFields,
    LLMExtractionResult,
    LLMExtractionMetadata,
    VerifyDocumentRequest,
    VerifyDocumentResponse,
)


def test_rc_extraction_fields_from_dict():
    data = {"registration_number": "MH47BL1775", "owner_name": "SHIVA SAI TRAVELS"}
    fields = RCExtractionFields(**data)
    assert fields.registration_number == "MH47BL1775"
    assert fields.chassis_number is None  # optional


def test_verify_document_request_validation():
    req = VerifyDocumentRequest(
        image_type="rc_book", side="front",
        driver_id="123", image_url="https://example.com/img.jpg",
    )
    assert req.image_type == "rc_book"


def test_verify_document_request_invalid_type():
    import pytest
    with pytest.raises(ValueError):
        VerifyDocumentRequest(
            image_type="passport", side="front",
            driver_id="123", image_url="https://example.com/img.jpg",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_schemas.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Create `app/llm/__init__.py`** (empty file)

- [ ] **Step 4: Implement schemas**

```python
# app/llm/schemas.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator
from datetime import date


class RCExtractionFields(BaseModel):
    registration_number: Optional[str] = None
    owner_name: Optional[str] = None
    father_name: Optional[str] = None
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_number: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    registration_date: Optional[str] = None
    validity_date: Optional[str] = None
    rto_code: Optional[str] = None
    rto_name: Optional[str] = None
    insurance_upto: Optional[str] = None
    fitness_upto: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    seat_capacity: Optional[str] = None
    emission_norms: Optional[str] = None


class DLExtractionFields(BaseModel):
    dl_number: Optional[str] = None
    holder_name: Optional[str] = None
    father_husband_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    blood_group: Optional[str] = None
    issue_date: Optional[str] = None
    validity_nt: Optional[str] = None
    validity_tr: Optional[str] = None
    issuing_authority: Optional[str] = None
    cov_details: Optional[List[Dict[str, str]]] = None
    address: Optional[str] = None


class AadhaarExtractionFields(BaseModel):
    aadhaar_number: Optional[str] = None
    holder_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    father_name: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None


class LLMExtractionMetadata(BaseModel):
    llm_provider: str
    llm_model: str
    extraction_time_ms: int
    prompt_version: str
    ocr_engine: str = "paddleocr"


class LLMExtractionResult(BaseModel):
    extracted_fields: Dict[str, Any]
    metadata: LLMExtractionMetadata
    raw_response: Dict[str, Any]
    system_prompt_used: str
    status: str = "success"  # success | partial | failed
    error_message: Optional[str] = None
    token_input: int = 0
    token_output: int = 0
    cost_inr: float = 0.0


class VerifyDocumentRequest(BaseModel):
    image_type: str  # "rc_book" | "driving_license" | "aadhaar"
    side: str  # "front" | "back"
    driver_id: str
    image_url: str

    @field_validator("image_type")
    @classmethod
    def validate_image_type(cls, v):
        valid = ("rc_book", "driving_license", "aadhaar")
        if v not in valid:
            raise ValueError(f"image_type must be one of {valid}")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v):
        if v not in ("front", "back"):
            raise ValueError("side must be 'front' or 'back'")
        return v


class VerifyDocumentResponse(BaseModel):
    request_id: str
    status: str  # "accepted" | "rejected"
    quality_score: float
    authenticity_passed: bool
    rejection_reasons: List[str] = []
    message: str
    structured_data: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[LLMExtractionMetadata] = None
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_llm_schemas.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/llm/__init__.py app/llm/schemas.py tests/test_llm_schemas.py
git commit -m "feat: add LLM Pydantic schemas for extraction fields and API request/response"
```

---

### Task 6: System Prompts

**Files:**
- Create: `app/llm/prompts/rc_book_v1.txt`
- Create: `app/llm/prompts/driving_license_v1.txt`
- Create: `app/llm/prompts/aadhaar_v1.txt`

- [ ] **Step 1: Create RC Book prompt**

See spec Section 2.4 for the full prompt content. Key: uses `{side}` placeholder, lists all 18 fields with format specs, includes OCR error correction rules (0↔O, 1↔I↔L, etc.), state code mapping, returns JSON only.

- [ ] **Step 2: Create DL prompt**

Same structure. Fields: dl_number, holder_name, father_husband_name, date_of_birth, blood_group, issue_date, validity_nt, validity_tr, issuing_authority, cov_details (as JSON array of {class, issue_date, expiry_date}), address.

- [ ] **Step 3: Create Aadhaar prompt**

Same structure. Fields: aadhaar_number, holder_name, date_of_birth, gender, father_name, address, pin_code.

- [ ] **Step 4: Commit**

```bash
git add app/llm/prompts/
git commit -m "feat: add v1 system prompts for RC book, DL, and Aadhaar extraction"
```

---

### Task 7: LLM Extractor

**Files:**
- Create: `app/llm/extractor.py`
- Test: `tests/test_llm_extractor.py`

- [ ] **Step 1: Write failing test with mocked API calls**

```python
# tests/test_llm_extractor.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.llm.extractor import LLMExtractor


@pytest.mark.asyncio
async def test_extract_rc_book_anthropic():
    """LLM extractor returns structured fields from OCR text."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"registration_number": "MH47BL1775", "owner_name": "SHIVA SAI"}')]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 100

    with patch("app.llm.extractor.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        extractor = LLMExtractor(provider="anthropic")
        result = await extractor.extract(
            ocr_text_front="Registration No: MH47BL1775\nOwner: SHIVA SAI",
            ocr_text_back=None,
            document_type="rc_book",
            side="front",
        )

        assert result.status == "success"
        assert result.extracted_fields["registration_number"] == "MH47BL1775"
        assert result.token_input == 500
        assert result.token_output == 100


@pytest.mark.asyncio
async def test_extract_returns_failed_on_api_error():
    with patch("app.llm.extractor.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        extractor = LLMExtractor(provider="anthropic")
        result = await extractor.extract(
            ocr_text_front="some text",
            ocr_text_back=None,
            document_type="rc_book",
            side="front",
        )

        assert result.status == "failed"
        assert "API down" in result.error_message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_extractor.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement LLMExtractor**

```python
# app/llm/extractor.py
import json
import os
import time
from pathlib import Path
from typing import Optional

import anthropic
from openai import AsyncOpenAI

from app.llm.schemas import LLMExtractionResult, LLMExtractionMetadata
from app.config import settings


# Prompt directory
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Cost per 1M tokens (INR) — configurable
COST_RATES = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},  # $0.25/1M in, $1.25/1M out → ~INR
    "gpt-4o-mini": {"input": 1.20, "output": 6.00},
}

# Doc type to prompt file mapping
DOC_TYPE_PROMPT_MAP = {
    "rc_book": "rc_book",
    "driving_license": "driving_license",
    "aadhaar": "aadhaar",
}


class LLMExtractor:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER

    def _load_prompt(self, document_type: str, version: str = "v1") -> str:
        prompt_name = DOC_TYPE_PROMPT_MAP[document_type]
        prompt_path = PROMPTS_DIR / f"{prompt_name}_{version}.txt"
        return prompt_path.read_text()

    def _build_user_prompt(self, ocr_text_front: Optional[str], ocr_text_back: Optional[str], side: str) -> str:
        parts = []
        if side == "front" and ocr_text_front:
            parts.append(f"OCR text from FRONT side:\n---\n{ocr_text_front}\n---")
        elif side == "back" and ocr_text_back:
            parts.append(f"OCR text from BACK side:\n---\n{ocr_text_back}\n---")
        if not parts:
            parts.append("No OCR text available.")
        return "\n\n".join(parts)

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = COST_RATES.get(model, {"input": 0, "output": 0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    async def extract(
        self,
        ocr_text_front: Optional[str],
        ocr_text_back: Optional[str],
        document_type: str,
        side: str,
        prompt_version: str = "v1",
    ) -> LLMExtractionResult:
        start = time.time()
        system_prompt = self._load_prompt(document_type, prompt_version)
        system_prompt = system_prompt.replace("{side}", side)
        user_prompt = self._build_user_prompt(ocr_text_front, ocr_text_back, side)

        model = (
            settings.LLM_MODEL_ANTHROPIC if self.provider == "anthropic"
            else settings.LLM_MODEL_OPENAI
        )

        # Retry policy: 1 retry with 2s delay on timeout or 5xx. No retry on 4xx or parse failures.
        last_error = None
        for attempt in range(2):  # max 2 attempts (1 original + 1 retry)
            try:
                if self.provider == "anthropic":
                    extracted, token_in, token_out, raw = await self._call_anthropic(
                        system_prompt, user_prompt, model
                    )
                else:
                    extracted, token_in, token_out, raw = await self._call_openai(
                        system_prompt, user_prompt, model
                    )

                elapsed_ms = int((time.time() - start) * 1000)
                cost = self._calculate_cost(model, token_in, token_out)

                return LLMExtractionResult(
                    extracted_fields=extracted,
                    metadata=LLMExtractionMetadata(
                        llm_provider=self.provider,
                        llm_model=model,
                        extraction_time_ms=elapsed_ms,
                        prompt_version=prompt_version,
                    ),
                    raw_response=raw,
                    system_prompt_used=system_prompt,
                    status="success",
                    token_input=token_in,
                    token_output=token_out,
                    cost_inr=cost,
                )
            except json.JSONDecodeError as e:
                last_error = e
                break  # No retry on parse failures
            except Exception as e:
                last_error = e
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2)  # 2s delay before retry
                continue

        elapsed_ms = int((time.time() - start) * 1000)
        return LLMExtractionResult(
            extracted_fields={},
            metadata=LLMExtractionMetadata(
                llm_provider=self.provider,
                llm_model=model,
                extraction_time_ms=elapsed_ms,
                prompt_version=prompt_version,
            ),
            raw_response={},
            system_prompt_used=system_prompt,
            status="failed",
            error_message=str(last_error),
        )

    async def _call_anthropic(self, system_prompt, user_prompt, model):
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        text = response.content[0].text
        extracted = json.loads(text)
        return extracted, response.usage.input_tokens, response.usage.output_tokens, {"text": text}

    async def _call_openai(self, system_prompt, user_prompt, model):
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,  # timeout on client, not per-call
        )
        response = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        extracted = json.loads(text)
        token_in = response.usage.prompt_tokens
        token_out = response.usage.completion_tokens
        return extracted, token_in, token_out, {"text": text}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_llm_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm/extractor.py tests/test_llm_extractor.py
git commit -m "feat: implement LLMExtractor with Anthropic + OpenAI provider support"
```

---

## Chunk 3: Govt API Module

### Task 8: Govt Schemas + Base Mapper

**Files:**
- Create: `app/govt/__init__.py`
- Create: `app/govt/schemas.py`
- Create: `app/govt/mappers/__init__.py`
- Create: `app/govt/mappers/base.py`
- Test: `tests/test_govt_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_govt_schemas.py

from app.govt.schemas import RCGovtFields, DLGovtFields, AadhaarGovtFields, GovtVerificationResult


def test_rc_govt_fields():
    f = RCGovtFields(owner_name="SHIVA SAI", rc_status="ACTIVE")
    assert f.owner_name == "SHIVA SAI"
    assert f.chassis_number is None


def test_govt_verification_result():
    r = GovtVerificationResult(
        status="success",
        reseller_code="gridlines",
        normalized_fields={"owner_name": "TEST"},
        raw_response={"data": {}},
    )
    assert r.status == "success"
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement schemas**

```python
# app/govt/schemas.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class RCGovtFields(BaseModel):
    owner_name: Optional[str] = None
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_number: Optional[str] = None
    registration_number: Optional[str] = None
    rc_status: Optional[str] = None
    fitness_upto: Optional[str] = None
    insurance_upto: Optional[str] = None
    extra_fields: Dict[str, Any] = {}


class DLGovtFields(BaseModel):
    holder_name: Optional[str] = None
    father_husband_name: Optional[str] = None
    dob: Optional[str] = None
    dl_number: Optional[str] = None
    dl_status: Optional[str] = None
    validity_nt: Optional[str] = None
    validity_tr: Optional[str] = None
    cov_details: Optional[list] = None
    issuing_authority: Optional[str] = None
    extra_fields: Dict[str, Any] = {}


class AadhaarGovtFields(BaseModel):
    holder_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None
    aadhaar_status: Optional[str] = None
    extra_fields: Dict[str, Any] = {}


class GovtVerificationResult(BaseModel):
    status: str  # success | failed | not_found
    reseller_code: str
    normalized_fields: Dict[str, Any]
    raw_response: Dict[str, Any]
    response_time_ms: int = 0
    api_cost_inr: float = 0.0
    error_message: Optional[str] = None
```

- [ ] **Step 4: Create BaseGovtMapper**

```python
# app/govt/mappers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseGovtMapper(ABC):
    @abstractmethod
    def normalize(self, raw_response: dict, doc_type: str) -> Dict[str, Any]:
        """Normalize raw reseller response into standard fields dict."""
        ...
```

- [ ] **Step 5: Run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add app/govt/ tests/test_govt_schemas.py
git commit -m "feat: add govt API schemas, base mapper, and GovtVerificationResult"
```

---

### Task 9: Reseller Mappers (Gridlines, Cashfree, HyperVerge)

**Files:**
- Create: `app/govt/mappers/gridlines.py`
- Create: `app/govt/mappers/cashfree.py`
- Create: `app/govt/mappers/hyperverge.py`
- Test: `tests/test_govt_mappers.py`

- [ ] **Step 1: Write tests with sample responses**

```python
# tests/test_govt_mappers.py

from app.govt.mappers.gridlines import GridlinesMapper
from app.govt.mappers.cashfree import CashfreeMapper
from app.govt.mappers.hyperverge import HyperVergeMapper


def test_gridlines_rc_normalize():
    raw = {
        "data": {
            "rc_data": {
                "owner_data": {"name": "SHIVA SAI TRAVELS"},
                "vehicle_data": {
                    "chassis_number": "MBHCZFB3SPG458278",
                    "engine_number": "K12NP7316940",
                    "fuel_type": "PETROL/CNG",
                    "category": "LMV",
                },
                "status": "ACTIVE",
                "insurance_data": {"expiry_date": "2025-08-04"},
            }
        }
    }
    mapper = GridlinesMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert fields["owner_name"] == "SHIVA SAI TRAVELS"
    assert fields["chassis_number"] == "MBHCZFB3SPG458278"
    assert fields["rc_status"] == "ACTIVE"
    assert fields["fitness_upto"] is None  # Gridlines doesn't have fitness


def test_cashfree_rc_normalize():
    raw = {
        "owner": "SHIVA SAI TRAVELS",
        "chassis": "MBHCZFB3SPG458278",
        "engine": "K12NP7316940",
        "type": "PETROL/CNG",
        "class": "LMV",
        "rc_status": "ACTIVE",
        "reg_no": "MH47BL1775",
        "vehicle_insurance_upto": "2025-08-04",
    }
    mapper = CashfreeMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert fields["owner_name"] == "SHIVA SAI TRAVELS"
    assert fields["registration_number"] == "MH47BL1775"


def test_hyperverge_rc_normalize_flat_format():
    raw = {
        "result": {
            "rcInfo": {
                "owner_name": "SHIVA SAI TRAVELS",
                "chassis_no": "MBHCZFB3SPG458278",
                "engine_no": "K12NP7316940",
                "fuel_descr": "PETROL/CNG",
                "vehicle_class_desc": "LMV",
                "status": "ACTIVE",
                "reg_no": "MH47BL1775",
                "fit_upto": "2028-01-06",
                "vehicle_insurance_details": {"insurance_upto": "2025-08-04"},
            }
        }
    }
    mapper = HyperVergeMapper()
    fields = mapper.normalize(raw, "rc_book")
    assert fields["owner_name"] == "SHIVA SAI TRAVELS"
    assert fields["fitness_upto"] == "2028-01-06"  # Only HyperVerge has this
    assert fields["registration_number"] == "MH47BL1775"
```

- [ ] **Step 2: Run tests — FAIL**

- [ ] **Step 3: Implement GridlinesMapper**

Extracts from `data.rc_data.*` path structure per field mapping table in spec Section 3.3.

- [ ] **Step 4: Implement CashfreeMapper**

Flat top-level keys: `owner`, `chassis`, `engine`, `type`, `class`, `rc_status`, `reg_no`, `vehicle_insurance_upto`.

- [ ] **Step 5: Implement HyperVergeMapper**

Auto-detect: if `result.rcInfo` exists → flat format. If `result.data.rcData` exists → nested format. Extract accordingly.

- [ ] **Step 6: Create mapper registry in `app/govt/mappers/__init__.py`**

```python
from app.govt.mappers.gridlines import GridlinesMapper
from app.govt.mappers.cashfree import CashfreeMapper
from app.govt.mappers.hyperverge import HyperVergeMapper

GOVT_MAPPER_REGISTRY = {
    "gridlines": GridlinesMapper(),
    "cashfree": CashfreeMapper(),
    "hyperverge": HyperVergeMapper(),
}
```

- [ ] **Step 7: Run tests — PASS**

- [ ] **Step 8: Commit**

```bash
git add app/govt/mappers/ tests/test_govt_mappers.py
git commit -m "feat: implement Gridlines, Cashfree, HyperVerge RC mappers with auto-format detection"
```

---

### Task 10: Govt API Client

**Files:**
- Create: `app/govt/client.py`
- Test: `tests/test_govt_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_govt_client.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.govt.client import GovtAPIClient


@pytest.mark.asyncio
async def test_client_calls_primary_reseller():
    mock_session = MagicMock()
    # Mock reseller from DB
    reseller = MagicMock()
    reseller.provider_code = "gridlines"
    reseller.endpoints_by_doc_type = {"rc_book": "https://api.gridlines.io/rc"}
    reseller.response_mappers_by_doc_type = {"rc_book": "gridlines"}
    reseller.auth_config = {"env_var": "GRIDLINES_API_KEY"}
    reseller.timeout_ms = 10000
    reseller.circuit_state = "closed"
    reseller.id = "r1"

    with patch("app.govt.client.httpx.AsyncClient") as mock_httpx:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"rc_data": {"owner_data": {"name": "TEST"}, "vehicle_data": {}, "status": "ACTIVE"}}
        }
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_httpx.return_value)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value.post = AsyncMock(return_value=mock_resp)

        client = GovtAPIClient(session=mock_session)
        client._resellers = [reseller]  # bypass DB load

        result = await client.verify("MH47BL1775", "rc_book")
        assert result.status == "success"
        assert result.normalized_fields["owner_name"] == "TEST"


@pytest.mark.asyncio
async def test_client_skips_open_circuit():
    mock_session = MagicMock()
    reseller = MagicMock()
    reseller.circuit_state = "open"
    reseller.provider_code = "gridlines"

    client = GovtAPIClient(session=mock_session)
    client._resellers = [reseller]

    result = await client.verify("MH47BL1775", "rc_book")
    assert result.status == "failed"
    assert "all resellers" in result.error_message.lower()
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement GovtAPIClient**

```python
# app/govt/client.py
import os
import time
from typing import List, Optional

import httpx

from app.govt.mappers import GOVT_MAPPER_REGISTRY
from app.govt.schemas import GovtVerificationResult


class GovtAPIClient:
    def __init__(self, session):
        self.session = session
        self._resellers = None

    def _load_resellers(self, doc_type: str):
        from app.storage.repository import GovtResellerRepository
        repo = GovtResellerRepository(self.session)
        self._resellers = repo.get_active_ordered(doc_type)

    async def verify(self, document_number: str, doc_type: str) -> GovtVerificationResult:
        if self._resellers is None:
            self._load_resellers(doc_type)

        from datetime import datetime, timedelta

        for reseller in self._resellers:
            # Circuit breaker: skip open circuits (allow half_open for test call)
            if reseller.circuit_state == "open":
                if reseller.last_failure_at and \
                   datetime.utcnow() - reseller.last_failure_at > timedelta(minutes=5):
                    reseller.circuit_state = "half_open"  # allow 1 test call
                else:
                    continue

            try:
                result = await self._call_reseller(reseller, document_number, doc_type)
                if result.status == "success":
                    # Reset circuit on success
                    reseller.consecutive_failures = 0
                    reseller.circuit_state = "closed"
                    reseller.successful_requests = (reseller.successful_requests or 0) + 1
                    reseller.total_requests = (reseller.total_requests or 0) + 1
                    self.session.commit()
                    return result
            except Exception:
                # Increment failures, update circuit breaker
                reseller.consecutive_failures = (reseller.consecutive_failures or 0) + 1
                reseller.total_requests = (reseller.total_requests or 0) + 1
                reseller.last_failure_at = datetime.utcnow()
                if reseller.consecutive_failures >= 5:
                    reseller.circuit_state = "open"
                self.session.commit()
                continue

        return GovtVerificationResult(
            status="failed",
            reseller_code="none",
            normalized_fields={},
            raw_response={},
            error_message="All resellers exhausted or circuit open",
        )

    async def _call_reseller(self, reseller, document_number, doc_type):
        endpoint = reseller.endpoints_by_doc_type.get(doc_type)
        mapper_name = reseller.response_mappers_by_doc_type.get(doc_type)
        auth_env = reseller.auth_config.get("env_var", "")
        api_key = os.environ.get(auth_env, "")
        timeout = reseller.timeout_ms / 1000

        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                endpoint,
                json={"id_number": document_number},
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                timeout=timeout,
            )
        elapsed_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            raise Exception(f"API returned {resp.status_code}")

        raw = resp.json()
        mapper = GOVT_MAPPER_REGISTRY[mapper_name]
        normalized = mapper.normalize(raw, doc_type)

        return GovtVerificationResult(
            status="success",
            reseller_code=reseller.provider_code,
            normalized_fields=normalized,
            raw_response=raw,
            response_time_ms=elapsed_ms,
        )
```

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add app/govt/client.py tests/test_govt_client.py
git commit -m "feat: implement GovtAPIClient with fallback chain and circuit breaker"
```

---

## Chunk 4: Verification Engine

### Task 11: Field Comparator

**Files:**
- Create: `app/verification/__init__.py`
- Create: `app/verification/comparator.py`
- Test: `tests/test_field_comparator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_field_comparator.py

from app.verification.comparator import FieldComparator


def test_exact_match_chassis():
    comp = FieldComparator()
    result = comp.compare_field(
        field_name="chassis_number",
        mapper_value="MBHCZFB3SPG458278",
        llm_value="MBHCZFB3SPG458278",
        govt_value="MBHCZFB3SPG458278",
    )
    assert result["is_match"] is True
    assert result["similarity_score"] == 1.0


def test_fuzzy_match_owner_name():
    comp = FieldComparator()
    result = comp.compare_field(
        field_name="owner_name",
        mapper_value="SHIVA SAI TRAVEL",
        llm_value="SHIVA SAI TRAVELS",
        govt_value="SHIVA SAI TRAVELS",
    )
    assert result["is_match"] is True  # fuzzy match above 0.85
    assert result["similarity_score"] > 0.85


def test_compute_match_score():
    comp = FieldComparator()
    comparisons = [
        {"field_name": "chassis_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "engine_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "owner_name", "is_match": True, "similarity_score": 0.9},
        {"field_name": "registration_number", "is_match": True, "similarity_score": 1.0},
        {"field_name": "fuel_type", "is_match": False, "similarity_score": 0.5},
    ]
    score = comp.compute_match_score(comparisons)
    assert 0.85 < score < 1.0
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement FieldComparator**

Uses exact match for IDs/numbers (chassis, engine, registration), fuzzy match (thefuzz token_sort_ratio) for names/addresses. `compute_match_score` = weighted average (critical fields weighted 2x). Returns list of comparison dicts for bulk insert into `*_field_comparisons`.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add app/verification/ tests/test_field_comparator.py
git commit -m "feat: implement FieldComparator with exact + fuzzy matching and weighted scoring"
```

---

### Task 12: Auto-Approval Engine

**Files:**
- Create: `app/verification/engine.py`
- Test: `tests/test_approval_engine.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_approval_engine.py

from app.verification.engine import AutoApprovalEngine


def test_auto_approve_valid_rc():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.92,
        govt_rc_status="ACTIVE",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=True,
    )
    assert decision.method == "auto_approved"


def test_auto_reject_inactive_rc():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.92,
        govt_rc_status="SUSPENDED",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=True,
    )
    assert decision.method == "auto_rejected"
    assert "not ACTIVE" in decision.reason


def test_manual_review_low_match():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_rc(
        front_quality=0.85,
        back_quality=0.80,
        llm_status="success",
        govt_status="success",
        govt_match_score=0.70,
        govt_rc_status="ACTIVE",
        govt_fitness_upto="2028-01-06",
        govt_insurance_upto="2026-08-04",
        critical_fields_match=False,
    )
    assert decision.method == "manual_review"


def test_auto_reject_expired_dl():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_dl(
        front_quality=0.85, back_quality=0.80,
        llm_status="success", govt_status="success",
        govt_match_score=0.92, govt_dl_status="ACTIVE",
        govt_validity_tr="2020-01-01",  # expired
        cov_covers_vehicle=True,
        critical_fields_match=True,
    )
    assert decision.method == "auto_rejected"
    assert "expired" in decision.reason.lower()


def test_auto_approve_valid_aadhaar():
    engine = AutoApprovalEngine()
    decision = engine.evaluate_aadhaar(
        front_quality=0.85, back_quality=0.80,
        llm_status="success", govt_status="success",
        govt_match_score=0.90, govt_aadhaar_status="VALID",
        critical_fields_match=True,
    )
    assert decision.method == "auto_approved"
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement AutoApprovalEngine**

Returns `ApprovalDecision(method, reason)`. Checks thresholds from `settings`. Criteria per spec Section 4.2. Separate methods: `evaluate_rc`, `evaluate_dl`, `evaluate_aadhaar`.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add app/verification/engine.py tests/test_approval_engine.py
git commit -m "feat: implement AutoApprovalEngine with RC/DL/Aadhaar criteria"
```

---

### Task 13: Cross-Document Validator

**Files:**
- Create: `app/verification/cross_doc.py`
- Test: `tests/test_cross_doc.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cross_doc.py

from app.verification.cross_doc import CrossDocValidator


def test_name_match_across_docs():
    validator = CrossDocValidator()
    result = validator.validate(
        dl_name="RAJESH KUMAR",
        aadhaar_name="RAJESH KUMAR",
        dl_dob="1990-05-15",
        aadhaar_dob="1990-05-15",
        dl_cov=["LMV"],
        rc_vehicle_class="LMV",
    )
    assert result["passed"] is True
    assert result["name_match"] is True
    assert result["dob_match"] is True
    assert result["cov_match"] is True
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement CrossDocValidator**

Fuzzy name match (threshold from settings), exact DOB match, COV vs vehicle class check. Returns dict with per-check results + overall `passed` boolean.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add app/verification/cross_doc.py tests/test_cross_doc.py
git commit -m "feat: implement CrossDocValidator for DL-Aadhaar-RC consistency checks"
```

---

## Chunk 5: API Endpoints

### Task 14: Verify Document Endpoint

**Files:**
- Create: `app/api/verify_routes.py`
- Modify: `app/main.py` (register new router)
- Test: `tests/test_verify_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_verify_api.py

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def test_verify_document_front_upload():
    """POST /verify/document with side=front creates record and returns accepted."""
    from app.main import app
    client = TestClient(app)

    with patch("app.api.verify_routes.fetch_image_url") as mock_fetch, \
         patch("app.api.verify_routes.extraction_service") as mock_svc, \
         patch("app.api.verify_routes.LLMExtractor") as mock_llm_cls, \
         patch("app.api.verify_routes._get_session_factory"):

        mock_fetch.return_value = b"fake_image_bytes"
        mock_svc.extract.return_value = {
            "success": True,
            "fields": [{"label": "registration_number", "value": "MH47BL1775"}],
            "raw_text": "Registration No: MH47BL1775",
            "image_quality": {"overall_score": 0.85, "is_acceptable": True, "feedback": []},
            "document_authenticity": {"is_authentic": True, "confidence": 0.9},
            "processing_time_ms": 500,
            "document_type": "rc_book",
            "confidence": 0.9,
        }

        mock_llm = AsyncMock()
        mock_llm.extract.return_value = MagicMock(
            status="success",
            extracted_fields={"registration_number": "MH47BL1775", "owner_name": "TEST"},
            metadata=MagicMock(
                llm_provider="anthropic", llm_model="claude-haiku-4-5-20251001",
                extraction_time_ms=1200, prompt_version="v1", ocr_engine="paddleocr",
            ),
            raw_response={"text": "{}"},
            system_prompt_used="test prompt",
            token_input=500, token_output=100, cost_inr=0.01,
        )
        mock_llm_cls.return_value = mock_llm

        resp = client.post("/verify/document", json={
            "image_type": "rc_book",
            "side": "front",
            "driver_id": "196274",
            "image_url": "https://example.com/img.jpg",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("accepted", "rejected")
        assert "request_id" in data
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement verify_routes.py**

```python
# app/api/verify_routes.py
import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.routes import get_db, extraction_service, _get_session_factory
from app.llm.extractor import LLMExtractor
from app.llm.schemas import VerifyDocumentRequest, VerifyDocumentResponse, LLMExtractionMetadata
from app.utils.image_utils import fetch_image_url
from app.config import settings

verify_router = APIRouter()

# Doc type to model/repo mapping
DOC_TYPE_CONFIG = {
    "rc_book": {"doc_key": "registration_number"},
    "driving_license": {"doc_key": "dl_number"},
    "aadhaar": {"doc_key": "aadhaar_number"},
}


@verify_router.post("/verify/document", response_model=VerifyDocumentResponse)
async def verify_document(
    request: VerifyDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Fetch image
    image_bytes = fetch_image_url(request.image_url)

    # 2. Run OCR
    ocr_result = extraction_service.extract(
        image_bytes=image_bytes,
        engine="paddle",
        document_type=request.image_type,
        include_raw_text=True,
        side=request.side,
    )
    raw_text = ocr_result.get("raw_text", "")

    # 3. Parallel: quality check (already in ocr_result) + LLM extraction
    llm_extractor = LLMExtractor()
    llm_result = await llm_extractor.extract(
        ocr_text_front=raw_text if request.side == "front" else None,
        ocr_text_back=raw_text if request.side == "back" else None,
        document_type=request.image_type,
        side=request.side,
    )

    # 4. Evaluate quality
    iq = ocr_result.get("image_quality", {})
    quality_score = iq.get("overall_score", 0.0)
    is_acceptable = iq.get("is_acceptable", False)
    da = ocr_result.get("document_authenticity", {})
    authenticity_passed = da.get("is_authentic", False) if da else False

    rejection_reasons = list(iq.get("feedback", []))
    if not authenticity_passed and da:
        rejection_reasons.append("Document authenticity check failed")

    # 5. Store in DB — front/back logic (mirrors existing validate_rc_book pattern)
    from app.storage.repository import RCValidationRepository, DLValidationRepository, AadhaarValidationRepository
    from app.storage.repository import LLMExtractionRepository

    REPO_MAP = {
        "rc_book": RCValidationRepository,
        "driving_license": DLValidationRepository,
        "aadhaar": AadhaarValidationRepository,
    }
    repo = REPO_MAP[request.image_type](db)
    fields = {f["label"]: f["value"] for f in ocr_result.get("fields", [])}
    validation_id = ""

    if request.side == "front":
        record = repo.create(
            driver_id=request.driver_id,
            front_url=request.image_url,
            overall_status="pending_back",
            front_quality_score=quality_score,
            front_issues=rejection_reasons,
            front_fields=fields,
            ocr_raw_text_front=raw_text,
        )
        validation_id = record.id
    else:  # back
        record = repo.get_pending_back_for_driver(request.driver_id)
        if not record:
            record = repo.create(
                driver_id=request.driver_id,
                back_url=request.image_url,
                overall_status="needs_review",
                back_quality_score=quality_score,
                back_issues=rejection_reasons,
                back_fields=fields,
                ocr_raw_text_back=raw_text,
                requires_review=True,
            )
        else:
            merged = {**(record.front_fields or {}), **fields}
            record = repo.update(
                record,
                back_url=request.image_url,
                overall_status="pending_verification",
                back_quality_score=quality_score,
                back_issues=rejection_reasons,
                back_fields=fields,
                merged_fields=merged,
                ocr_raw_text_back=raw_text,
            )
            # Fire govt verification as background task
            background_tasks.add_task(
                _run_govt_verification, record.id, request.image_type, db
            )
        validation_id = record.id

    # Store LLM extraction record
    if llm_result.status in ("success", "partial"):
        llm_repo = LLMExtractionRepository(db, request.image_type)
        llm_repo.create(
            validation_id=validation_id,
            model_provider=llm_result.metadata.llm_provider,
            model_name=llm_result.metadata.llm_model,
            prompt_version=llm_result.metadata.prompt_version,
            llm_raw_response=llm_result.raw_response,
            system_prompt_used=llm_result.system_prompt_used,
            extracted_fields=llm_result.extracted_fields,
            extraction_time_ms=llm_result.metadata.extraction_time_ms,
            token_input=llm_result.token_input,
            token_output=llm_result.token_output,
            cost_inr=llm_result.cost_inr,
            status=llm_result.status,
        )

    # 6. Build response
    if is_acceptable and (authenticity_passed or not da):
        status = "accepted"
        message = "Document accepted"
        structured_data = llm_result.extracted_fields if llm_result.status == "success" else None
    else:
        status = "rejected"
        message = "Please re-upload a clearer photo of the document"
        structured_data = None

    return VerifyDocumentResponse(
        request_id=validation_id,
        status=status,
        quality_score=quality_score,
        authenticity_passed=authenticity_passed,
        rejection_reasons=rejection_reasons,
        message=message,
        structured_data=structured_data,
        extraction_metadata=LLMExtractionMetadata(
            llm_provider=llm_result.metadata.llm_provider,
            llm_model=llm_result.metadata.llm_model,
            extraction_time_ms=llm_result.metadata.extraction_time_ms,
            prompt_version=llm_result.metadata.prompt_version,
            ocr_engine="paddleocr",
        ) if llm_result.status == "success" else None,
    )
```

- [ ] **Step 4: Add background task helper function**

```python
async def _run_govt_verification(validation_id: str, doc_type: str, db: Session):
    """Background task: call govt API and run auto-approval after response."""
    from app.govt.client import GovtAPIClient
    from app.verification.engine import AutoApprovalEngine
    # ... fetch validation record, get reg number, call govt client, store result,
    # run auto-approval engine, update validation record status
```

- [ ] **Step 5: Register router in main.py**

Add to `app/main.py`:
```python
from app.api.verify_routes import verify_router
app.include_router(verify_router)
```

- [ ] **Step 5: Run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add app/api/verify_routes.py app/main.py tests/test_verify_api.py
git commit -m "feat: implement POST /verify/document endpoint with OCR + LLM pipeline"
```

---

### Task 15: Status + Admin Endpoints

**Files:**
- Modify: `app/api/verify_routes.py`
- Test: `tests/test_verify_api.py`

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_verify_api.py

def test_status_endpoint_returns_verification_status():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/verify/document/some-id/status")
    # Will 404 since no record, but endpoint should exist
    assert resp.status_code in (200, 404)


def test_admin_endpoint_requires_api_key():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/admin/retry-stuck")
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Add status endpoint**

```python
@verify_router.get("/verify/document/{validation_id}/status")
def get_verification_status(validation_id: str, db: Session = Depends(get_db)):
    # Look up across all validation tables by ID
    # Return verification_status, approval_method, govt_match_score
    ...
```

- [ ] **Step 4: Add admin middleware for ADMIN_API_KEY**

```python
from fastapi import Header, HTTPException

def require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@verify_router.post("/admin/retry-stuck")
def retry_stuck(db: Session = Depends(get_db), _=Depends(require_admin)):
    # Find records with verification_status='pending' older than 10 min
    # Re-trigger govt verification for each
    ...
```

- [ ] **Step 5: Run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add app/api/verify_routes.py tests/test_verify_api.py
git commit -m "feat: add /verify/document/{id}/status and /admin/retry-stuck endpoints"
```

---

## Chunk 6: Backfill + Backtest

### Task 16: Backfill Script + Endpoint

**Files:**
- Create: `scripts/backfill_mysql_pg.py`
- Modify: `app/api/verify_routes.py` (add `/backfill/rc` endpoint)
- Test: `tests/test_backfill.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_backfill.py

def test_backfill_transforms_rc_master_row():
    from scripts.backfill_mysql_pg import transform_rc_master_row
    mysql_row = {
        "rc_number": "MH47BL1775",
        "owner_name": "SHIVA SAI TRAVELS",
        "vehicle_chasi_number": "MBHCZFB3SPG458278",
        "vehicle_engine_number": "K12NP7316940",
        "fuel_type": "PETROL/CNG",
        "vehicle_category": "LPV",
        "rc_status": "ACTIVE",
        "fit_up_to": "2028-01-06",
        "insurance_upto": "2025-08-04",
        "body_type": "Sedan",
        "color": "White",
    }
    result = transform_rc_master_row(mysql_row)
    assert result["govt_registration_number"] == "MH47BL1775"
    assert result["govt_owner_name"] == "SHIVA SAI TRAVELS"
    assert result["govt_vehicle_class"] == "LPV"
    assert "body_type" in result["govt_fields"]  # non-critical → JSONB
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement transform functions**

`transform_rc_master_row` — maps MySQL columns to Postgres per spec Section 1.1. 10 critical fields as columns, everything else into `govt_fields` dict. Full row into `raw_response`.

`transform_rc_detail_row` — maps per spec Section 1.2. Concat reg number parts, prepend S3 base URL, map `is_approve` to `overall_status`/`approval_method`.

- [ ] **Step 4: Implement backfill endpoint**

```python
@verify_router.post("/backfill/rc")
async def backfill_rc(db: Session = Depends(get_db), _=Depends(require_admin)):
    # Batch process: read from MySQL, transform, insert into Postgres
    # Idempotent: skip existing records
    # Return count processed
    ...
```

- [ ] **Step 5: Run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_mysql_pg.py app/api/verify_routes.py tests/test_backfill.py
git commit -m "feat: add MySQL→Postgres backfill script and /backfill/rc endpoint"
```

---

### Task 17: Backtest Script + Endpoint

**Files:**
- Create: `scripts/backtest.py`
- Modify: `app/api/verify_routes.py` (add `/backtest/rc` endpoint)
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_backtest.py

def test_backtest_computes_accuracy_report():
    from scripts.backtest import compute_accuracy_report
    comparisons = [
        {"field_name": "registration_number", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "registration_number", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "owner_name", "is_match": True, "source": "llm_vs_govt"},
        {"field_name": "owner_name", "is_match": False, "source": "llm_vs_govt"},
        {"field_name": "chassis_number", "is_match": True, "source": "llm_vs_govt"},
    ]
    report = compute_accuracy_report(comparisons)
    assert report["registration_number"]["accuracy"] == 1.0
    assert report["owner_name"]["accuracy"] == 0.5
```

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement backtest logic**

Per spec Section 5.5: query records with govt verification + valid S3 URLs, fetch image → OCR → LLM → compare vs govt truth → store comparisons → return accuracy report.

- [ ] **Step 4: Implement backtest endpoint**

```python
@verify_router.post("/backtest/rc")
async def backtest_rc(
    sample_size: int = 500,
    prompt_version: str = "v1",
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    # Run backtest, return accuracy metrics
    ...
```

- [ ] **Step 5: Run tests — PASS**

- [ ] **Step 6: Commit**

```bash
git add scripts/backtest.py app/api/verify_routes.py tests/test_backtest.py
git commit -m "feat: add backtest script and /backtest/rc endpoint for LLM accuracy measurement"
```

---

## Chunk 7: Integration + Final Verification

### Task 18: Integration Test

**Files:**
- Create: `tests/test_verification_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_verification_integration.py

"""
End-to-end test: mock OCR + mock LLM + mock govt → verify full pipeline flow.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def test_full_rc_pipeline_front_then_back():
    """Upload front, then back. Verify both stored, LLM called, response correct."""
    from app.main import app
    client = TestClient(app)
    # ... (mock OCR, LLM, DB — test front creates record, back updates it)


def test_quality_rejection_skips_llm():
    """If quality fails, still call LLM but return rejected status."""
    ...


def test_invalid_doc_type_returns_422():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/verify/document", json={
        "image_type": "passport",
        "side": "front",
        "driver_id": "123",
        "image_url": "https://example.com/img.jpg",
    })
    assert resp.status_code == 422
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_verification_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 4: Commit**

```bash
git add tests/test_verification_integration.py
git commit -m "test: add integration tests for document verification pipeline"
```

---

### Task 19: Final Cleanup + Requirements

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml`)

- [ ] **Step 1: Add new dependencies**

```
anthropic>=0.39.0
openai>=1.50.0
httpx>=0.27.0
thefuzz>=0.22.1
python-Levenshtein>=0.25.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add anthropic, openai, httpx, thefuzz dependencies"
```

---

## Summary

| Task | Component | New Files | Tests |
|------|-----------|-----------|-------|
| 1 | Config | — (modify config.py) | test_config.py |
| 2 | Models — Shared + RC | — (modify models.py) | test_new_models.py |
| 3 | Models — DL + Aadhaar + Cross-doc | — (modify models.py) | test_new_models.py |
| 4 | Repositories | — (modify repository.py) | test_repositories.py |
| 5 | LLM Schemas | app/llm/schemas.py | test_llm_schemas.py |
| 6 | System Prompts | app/llm/prompts/*.txt | — |
| 7 | LLM Extractor | app/llm/extractor.py | test_llm_extractor.py |
| 8 | Govt Schemas + Base | app/govt/schemas.py, base.py | test_govt_schemas.py |
| 9 | Reseller Mappers | gridlines/cashfree/hyperverge.py | test_govt_mappers.py |
| 10 | Govt Client | app/govt/client.py | test_govt_client.py |
| 11 | Field Comparator | app/verification/comparator.py | test_field_comparator.py |
| 12 | Auto-Approval Engine | app/verification/engine.py | test_approval_engine.py |
| 13 | Cross-Doc Validator | app/verification/cross_doc.py | test_cross_doc.py |
| 14 | Verify Endpoint | app/api/verify_routes.py | test_verify_api.py |
| 15 | Status + Admin | — (modify verify_routes.py) | test_verify_api.py |
| 16 | Backfill | scripts/backfill_mysql_pg.py | test_backfill.py |
| 17 | Backtest | scripts/backtest.py | test_backtest.py |
| 18 | Integration Tests | — | test_verification_integration.py |
| 19 | Dependencies | requirements.txt | — |
