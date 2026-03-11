# RC Book Extraction Enhancement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance RC book extraction with front/back side support, image quality assessment, document authenticity validation, and multi-engine comparison for testing.

**Architecture:** The extraction pipeline gains three new modules (image_quality, document_validator, comparator generalization) integrated into ExtractionService. The RC book mapper is expanded with front/back field sets and `registration_number` as a common merge key. All changes are backward compatible — new response fields are optional.

**Tech Stack:** Python, FastAPI, Pydantic, OpenCV (cv2), NumPy, pytest

**Spec:** `docs/superpowers/specs/2026-03-11-rc-book-extraction-enhancement-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app/mappers/base.py` | Modify | Add `side` param to abstract `map_fields` |
| `app/mappers/rc_book.py` | Modify | Expand fields, front/back/common split, side-aware mapping |
| `app/mappers/receipt.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/invoice.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/driving_license.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/insurance.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/petrol_receipt.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/odometer.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/mappers/fuel_pump_reading.py` | Modify | Add `side=None` to `map_fields` signature |
| `app/core/image_quality.py` | Create | Blur, brightness, resolution checks + extraction completeness scoring |
| `app/core/document_validator.py` | Create | Structural (text) + visual (OpenCV) authenticity checks |
| `app/api/schemas.py` | Modify | Add ImageQuality, DocumentAuthenticity, side field |
| `app/api/routes.py` | Modify | Pass side through, add `/compare/rc-book` endpoint |
| `app/core/extraction_service.py` | Modify | Integrate side, quality, authenticity into pipeline |
| `app/comparison/comparator.py` | Modify | Generalize to N engines |
| `app/comparison/metrics.py` | Modify | Generalize from 2-engine to N-engine |
| `tests/test_rc_book_mapper.py` | Create | Comprehensive RC book mapper tests (front/back/auto-detect) |
| `tests/test_image_quality.py` | Create | Image quality assessment tests |
| `tests/test_document_validator.py` | Create | Document authenticity tests |
| `tests/test_comparison_n_engine.py` | Create | N-engine comparison tests |
| `tests/conftest.py` | Modify | Add RC book front/back fixtures |
| `tests/test_comparison.py` | Modify | Update to N-engine API |
| `tests/test_api.py` | Modify | Update mock fixture for new response fields |
| `tests/test_extraction_service.py` | Modify | Mock new quality/validator dependencies |
| `tests/test_schemas.py` | Modify | Add tests for new schema models + side validation |

---

## Chunk 1: BaseMapper Interface + RC Book Mapper Expansion

### Task 1: Update BaseMapper interface to accept `side` parameter

**Files:**
- Modify: `app/mappers/base.py`
- Modify: `app/mappers/receipt.py`
- Modify: `app/mappers/invoice.py`
- Modify: `app/mappers/driving_license.py`
- Modify: `app/mappers/insurance.py`
- Modify: `app/mappers/petrol_receipt.py`
- Modify: `app/mappers/odometer.py`
- Modify: `app/mappers/fuel_pump_reading.py`

- [ ] **Step 1: Update BaseMapper abstract method**

In `app/mappers/base.py`, add `side` parameter:

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseMapper(ABC):
    """Abstract base class for document-type-specific field mappers."""

    @abstractmethod
    def map_fields(self, raw_text: str, side: Optional[str] = None) -> List[Dict[str, str]]:
        """Extract type-specific fields from raw OCR text."""
        pass

    @abstractmethod
    def document_type(self) -> str:
        """Return the document type this mapper handles."""
        pass
```

- [ ] **Step 2: Update all existing mapper signatures**

Add `side: Optional[str] = None` to `map_fields` in each mapper. The parameter is accepted but ignored. Example for `receipt.py`:

```python
def map_fields(self, raw_text: str, side: Optional[str] = None) -> List[Dict[str, str]]:
```

Add `from typing import Optional` to imports where missing. Apply to all 7 mappers: receipt, invoice, driving_license, insurance, petrol_receipt, odometer, fuel_pump_reading.

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS (the `side=None` default means no behavioral change)

- [ ] **Step 4: Commit**

```bash
git add app/mappers/
git commit -m "refactor: add optional side parameter to BaseMapper.map_fields"
```

### Task 2: Add RC book front/back test fixtures

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_rc_book_mapper.py`

- [ ] **Step 1: Add front and back RC book fixtures to conftest.py**

Add these fixtures after the existing `sample_raw_text_rc_book` fixture:

```python
@pytest.fixture
def sample_raw_text_rc_front():
    return """FORM 23
REGISTRATION CERTIFICATE
Government of India

Registration No: KA01AB1234
Owner: RAJESH KUMAR
S/O: SURESH KUMAR
Address: 123, MG Road, Bangalore - 560001
Maker's Name: MARUTI SUZUKI
Model: SWIFT DZIRE
Fuel Type: Petrol
Body Type: Sedan
Colour: White
Seating Capacity: 5
Date of Registration: 15/03/2020
Fitness Upto: 14/03/2035
Tax Upto: 14/03/2025
Registering Authority: KA01 - Bangalore"""


@pytest.fixture
def sample_raw_text_rc_back():
    return """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Engine No: K12M1234567
Chassis No: MA3FJEB1S00123456
Mfg Date: 02/2020
Unladen Weight: 875 KG
Cubic Capacity: 1197 CC
Wheelbase: 2430 MM
No of Cyl: 4
Emission Norms: BS VI
Hypothecation: HDFC BANK
Insurance Upto: 14/03/2025
Standing Capacity: 0"""
```

- [ ] **Step 2: Write failing tests for front-side mapping**

Create `tests/test_rc_book_mapper.py`:

```python
import pytest
from app.mappers.rc_book import RCBookMapper


class TestRCBookMapperFront:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_front_extracts_registration_number(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "KA01AB1234" in field_dict["registration_number"]

    def test_front_extracts_owner_name(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" in field_dict
        assert "RAJESH KUMAR" in field_dict["owner_name"]

    def test_front_extracts_vehicle_make(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "vehicle_make" in field_dict
        assert "MARUTI SUZUKI" in field_dict["vehicle_make"]

    def test_front_extracts_fuel_type(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fuel_type" in field_dict
        assert "Petrol" in field_dict["fuel_type"]

    def test_front_extracts_registration_date(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_date" in field_dict

    def test_front_extracts_fitness_expiry(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "fitness_expiry" in field_dict

    def test_front_extracts_tax_expiry(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "tax_expiry" in field_dict

    def test_front_does_not_extract_back_fields(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" not in field_dict
        assert "chassis_number" not in field_dict
        assert "cubic_capacity" not in field_dict

    def test_front_all_mandatory_fields_present(self, sample_raw_text_rc_front):
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side="front")
        field_dict = {f["label"]: f["value"] for f in fields}
        mandatory = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
        for field in mandatory:
            assert field in field_dict, f"Mandatory field '{field}' missing from front extraction"


class TestRCBookMapperBack:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_back_extracts_registration_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
        assert "KA01AB1234" in field_dict["registration_number"]

    def test_back_extracts_engine_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" in field_dict
        assert "K12M1234567" in field_dict["engine_number"]

    def test_back_extracts_chassis_number(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "chassis_number" in field_dict
        assert "MA3FJEB1S00123456" in field_dict["chassis_number"]

    def test_back_extracts_cubic_capacity(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "cubic_capacity" in field_dict

    def test_back_extracts_emission_norms(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "emission_norms" in field_dict

    def test_back_does_not_extract_front_fields(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" not in field_dict
        assert "fuel_type" not in field_dict
        assert "vehicle_make" not in field_dict

    def test_back_all_mandatory_fields_present(self, sample_raw_text_rc_back):
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side="back")
        field_dict = {f["label"]: f["value"] for f in fields}
        mandatory = ["registration_number", "engine_number", "chassis_number"]
        for field in mandatory:
            assert field in field_dict, f"Mandatory field '{field}' missing from back extraction"


class TestRCBookMapperAutoDetect:
    def setup_method(self):
        self.mapper = RCBookMapper()

    def test_auto_detect_front(self, sample_raw_text_rc_front):
        """When side=None, should detect front and return front fields."""
        fields = self.mapper.map_fields(sample_raw_text_rc_front, side=None)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "owner_name" in field_dict
        assert "registration_number" in field_dict

    def test_auto_detect_back(self, sample_raw_text_rc_back):
        """When side=None, should detect back and return back fields."""
        fields = self.mapper.map_fields(sample_raw_text_rc_back, side=None)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "engine_number" in field_dict
        assert "chassis_number" in field_dict

    def test_empty_text_returns_empty(self):
        mapper = RCBookMapper()
        assert mapper.map_fields("", side="front") == []
        assert mapper.map_fields("", side="back") == []
        assert mapper.map_fields("") == []

    def test_backward_compat_no_side(self, sample_raw_text_rc_book):
        """Existing fixture with no side param should still work."""
        mapper = RCBookMapper()
        fields = mapper.map_fields(sample_raw_text_rc_book)
        field_dict = {f["label"]: f["value"] for f in fields}
        assert "registration_number" in field_dict
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `pytest tests/test_rc_book_mapper.py -v`
Expected: FAIL (new fields like `fitness_expiry`, `tax_expiry` don't exist yet; side filtering not implemented)

- [ ] **Step 4: Commit test file**

```bash
git add tests/test_rc_book_mapper.py tests/conftest.py
git commit -m "test: add RC book front/back mapper tests (red)"
```

### Task 3: Implement expanded RC book mapper with front/back support

**Files:**
- Modify: `app/mappers/rc_book.py`

- [ ] **Step 1: Implement the expanded RCBookMapper**

Replace `app/mappers/rc_book.py` with:

```python
import re
from typing import Dict, List, Optional

from .base import BaseMapper

# Common field — appears on both sides, used as merge key
COMMON_FIELD_ALIASES: Dict[str, List[str]] = {
    "registration_number": [
        "registration no", "regn no", "reg no", "vehicle no",
        "reg. no", "regn. no",
    ],
}

FRONT_FIELD_ALIASES: Dict[str, List[str]] = {
    "owner_name": ["owner", "name", "registered owner", "owner's name"],
    "father_name": ["s/o", "d/o", "w/o", "s/w/d of", "son of", "daughter of", "wife of"],
    "address": ["address", "permanent address", "present address"],
    "vehicle_make": [
        "maker", "maker's name", "manufacturer", "make", "vehicle make",
    ],
    "vehicle_model": ["model", "vehicle model", "maker model"],
    "fuel_type": ["fuel type", "fuel used", "type of fuel", "fuel"],
    "vehicle_type": ["body type", "vehicle class", "type of body", "veh. class"],
    "color": ["colour", "color", "vehicle colour"],
    "seating_capacity": ["seating capacity", "seats", "no. of seats", "seating cap"],
    "registration_date": [
        "date of registration", "regn date", "date of reg", "reg date",
    ],
    "fitness_expiry": ["fitness upto", "fit upto", "fitness valid till", "valid till"],
    "tax_expiry": ["tax upto", "tax valid till", "tax paid upto"],
    "rto": ["rto", "registering authority", "registration authority", "reg. authority"],
}

BACK_FIELD_ALIASES: Dict[str, List[str]] = {
    "engine_number": ["engine no", "engine number", "eng no", "eng. no"],
    "chassis_number": [
        "chassis no", "chassis number", "ch no", "chasi no", "ch. no",
    ],
    "manufacturing_date": [
        "mfg date", "manufacturing date", "month/year of mfg", "mfg. date",
    ],
    "unladen_weight": ["unladen weight", "ulw", "unladen wt", "ul weight"],
    "cubic_capacity": ["cubic capacity", "cc", "engine cc", "cubic cap"],
    "wheelbase": ["wheelbase", "wheel base"],
    "cylinders": ["no of cyl", "cylinders", "no. of cylinders", "noof cyl"],
    "emission_norms": ["emission norms", "bs", "bharat stage", "emission standard"],
    "hypothecation": ["hypothecation", "financer", "hp", "hypothecated to"],
    "insurance_validity": ["insurance upto", "insurance valid till", "ins. upto"],
    "standing_capacity": ["standing capacity"],
}

# Side detection indicators (fields unique to each side, excluding registration_number)
FRONT_INDICATORS = ["owner", "address", "fuel type", "body type", "colour", "seating"]
BACK_INDICATORS = ["engine no", "chassis no", "cubic capacity", "wheelbase", "cylinders", "unladen weight"]

FRONT_MANDATORY = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
BACK_MANDATORY = ["registration_number", "engine_number", "chassis_number"]


def _detect_side(raw_text: str) -> str:
    """Auto-detect front vs back based on field indicators in OCR text."""
    text_lower = raw_text.lower()
    front_score = sum(1 for ind in FRONT_INDICATORS if ind in text_lower)
    back_score = sum(1 for ind in BACK_INDICATORS if ind in text_lower)
    return "back" if back_score > front_score else "front"


class RCBookMapper(BaseMapper):
    def map_fields(self, raw_text: str, side: Optional[str] = None) -> List[Dict[str, str]]:
        if not raw_text.strip():
            return []

        # Auto-detect side if not provided
        if side is None:
            side = _detect_side(raw_text)

        # Select field set based on side
        if side == "back":
            side_aliases = BACK_FIELD_ALIASES
        else:
            side_aliases = FRONT_FIELD_ALIASES

        # Always include common fields
        all_aliases = {**COMMON_FIELD_ALIASES, **side_aliases}

        fields = []
        lines = raw_text.strip().split("\n")
        used_labels = set()

        for label, aliases in all_aliases.items():
            if label in used_labels:
                continue
            for alias in aliases:
                pattern = re.compile(
                    rf"(?i){re.escape(alias)}\s*[:\-]?\s*(.+)",
                )
                for line in lines:
                    match = pattern.search(line)
                    if match and label not in used_labels:
                        value = match.group(1).strip()
                        # Strip trailing colons and extra whitespace
                        value = value.rstrip(":").strip()
                        if value:
                            fields.append({"label": label, "value": value})
                            used_labels.add(label)
                            break
                if label in used_labels:
                    break

        return fields

    def document_type(self) -> str:
        return "rc_book"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_rc_book_mapper.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS (existing `test_driver_mappers.py::test_rc_book_mapper` should still pass with backward compat)

- [ ] **Step 4: Commit**

```bash
git add app/mappers/rc_book.py
git commit -m "feat: expand RC book mapper with front/back side support"
```

---

## Chunk 2: Image Quality Assessment

### Task 4: Write image quality tests

**Files:**
- Create: `tests/test_image_quality.py`

- [ ] **Step 1: Write failing tests for image quality assessment**

Create `tests/test_image_quality.py`:

```python
import io
import numpy as np
import cv2
import pytest
from app.core.image_quality import ImageQualityAssessor


def _make_image_bytes(width=800, height=600, brightness=128, add_blur=False):
    """Create a test image with controllable properties."""
    img = np.full((height, width, 3), brightness, dtype=np.uint8)
    # Add some text-like features so it's not completely uniform
    cv2.putText(img, "TEST", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 3)
    if add_blur:
        img = cv2.GaussianBlur(img, (51, 51), 0)
    _, buffer = cv2.imencode(".png", img)
    return buffer.tobytes()


class TestImageProperties:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_normal_image_no_issues(self):
        image_bytes = _make_image_bytes(800, 600, brightness=128)
        result = self.assessor.assess_image_properties(image_bytes)
        assert "blurry" not in result["issues"]
        assert "too_dark" not in result["issues"]
        assert "too_bright" not in result["issues"]
        assert "low_resolution" not in result["issues"]

    def test_blurry_image_detected(self):
        image_bytes = _make_image_bytes(800, 600, brightness=128, add_blur=True)
        result = self.assessor.assess_image_properties(image_bytes)
        assert "blurry" in result["issues"]

    def test_dark_image_detected(self):
        image_bytes = _make_image_bytes(800, 600, brightness=30)
        result = self.assessor.assess_image_properties(image_bytes)
        assert "too_dark" in result["issues"]

    def test_bright_image_detected(self):
        image_bytes = _make_image_bytes(800, 600, brightness=230)
        result = self.assessor.assess_image_properties(image_bytes)
        assert "too_bright" in result["issues"]

    def test_low_resolution_detected(self):
        image_bytes = _make_image_bytes(320, 240, brightness=128)
        result = self.assessor.assess_image_properties(image_bytes)
        assert "low_resolution" in result["issues"]


class TestExtractionCompleteness:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_all_front_mandatory_present(self):
        extracted = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
        result = self.assessor.assess_completeness(extracted, side="front")
        assert result["is_acceptable"] is True
        assert result["missing_fields"] == []

    def test_one_front_mandatory_missing(self):
        extracted = ["registration_number", "owner_name", "vehicle_make", "fuel_type"]
        result = self.assessor.assess_completeness(extracted, side="front")
        assert result["is_acceptable"] is True  # 1 missing = warning, still acceptable
        assert "registration_date" in result["missing_fields"]

    def test_two_front_mandatory_missing(self):
        extracted = ["registration_number", "owner_name", "vehicle_make"]
        result = self.assessor.assess_completeness(extracted, side="front")
        assert result["is_acceptable"] is False
        assert len(result["missing_fields"]) == 2

    def test_all_back_mandatory_present(self):
        extracted = ["registration_number", "engine_number", "chassis_number"]
        result = self.assessor.assess_completeness(extracted, side="back")
        assert result["is_acceptable"] is True

    def test_back_mandatory_missing(self):
        extracted = ["registration_number"]
        result = self.assessor.assess_completeness(extracted, side="back")
        assert result["is_acceptable"] is False


class TestCombinedQuality:
    def setup_method(self):
        self.assessor = ImageQualityAssessor()

    def test_good_image_all_fields(self):
        image_issues = []
        extracted = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
        result = self.assessor.combine(image_issues, extracted, side="front", ocr_confidence=0.9)
        assert result["is_acceptable"] is True
        assert result["score"] > 0.7

    def test_blurry_but_all_fields_still_acceptable(self):
        image_issues = ["blurry"]
        extracted = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
        result = self.assessor.combine(image_issues, extracted, side="front", ocr_confidence=0.7)
        assert result["is_acceptable"] is True  # all fields found, so acceptable despite blur

    def test_blurry_plus_missing_field_not_acceptable(self):
        image_issues = ["blurry"]
        extracted = ["registration_number", "owner_name", "vehicle_make"]
        result = self.assessor.combine(image_issues, extracted, side="front", ocr_confidence=0.4)
        assert result["is_acceptable"] is False

    def test_feedback_message_for_blur(self):
        image_issues = ["blurry"]
        extracted = ["registration_number", "owner_name"]
        result = self.assessor.combine(image_issues, extracted, side="front", ocr_confidence=0.3)
        assert result["feedback"] is not None
        assert "blurry" in result["feedback"].lower() or "blur" in result["feedback"].lower()

    def test_score_formula(self):
        """Score = 0.3 * layer_a_score + 0.7 * layer_b_score"""
        image_issues = []  # layer_a_score = 1.0
        extracted = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
        result = self.assessor.combine(image_issues, extracted, side="front", ocr_confidence=0.9)
        # layer_b = 5/5 = 1.0, score = 0.3 * 1.0 + 0.7 * 1.0 = 1.0
        assert result["score"] == pytest.approx(1.0, abs=0.01)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_image_quality.py -v`
Expected: FAIL (module doesn't exist yet)

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_image_quality.py
git commit -m "test: add image quality assessment tests (red)"
```

### Task 5: Implement image quality assessment

**Files:**
- Create: `app/core/image_quality.py`

- [ ] **Step 1: Implement ImageQualityAssessor**

Create `app/core/image_quality.py`:

```python
from typing import Dict, List, Optional

import cv2
import numpy as np

FRONT_MANDATORY = ["registration_number", "owner_name", "vehicle_make", "fuel_type", "registration_date"]
BACK_MANDATORY = ["registration_number", "engine_number", "chassis_number"]

BLUR_THRESHOLD = 100.0
BRIGHTNESS_MIN = 50
BRIGHTNESS_MAX = 200
MIN_WIDTH = 640
MIN_HEIGHT = 480

FEEDBACK_MESSAGES = {
    "blurry": "Image appears blurry. Hold the camera steady and ensure the document is in focus",
    "too_dark": "Image is too dark. Please retake in better lighting",
    "too_bright": "Image is overexposed. Avoid direct light on the document",
    "low_resolution": "Image resolution is too low. Move the camera closer to the document",
}


class ImageQualityAssessor:
    """Two-layer image quality assessment: image properties + extraction completeness."""

    def assess_image_properties(self, image_bytes: bytes) -> Dict:
        """Layer A: Check blur, brightness, resolution on raw image bytes."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        issues = []
        h, w = img.shape[:2]

        # Resolution check
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            issues.append("low_resolution")

        # Convert to grayscale for blur and brightness checks
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Blur check: Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < BLUR_THRESHOLD:
            issues.append("blurry")

        # Brightness check: mean pixel intensity of grayscale
        mean_brightness = np.mean(gray)
        if mean_brightness < BRIGHTNESS_MIN:
            issues.append("too_dark")
        elif mean_brightness > BRIGHTNESS_MAX:
            issues.append("too_bright")

        return {"issues": issues, "blur_score": float(laplacian_var), "brightness": float(mean_brightness)}

    def assess_completeness(self, extracted_labels: List[str], side: str) -> Dict:
        """Layer B: Check if mandatory fields were extracted."""
        mandatory = FRONT_MANDATORY if side == "front" else BACK_MANDATORY
        missing = [f for f in mandatory if f not in extracted_labels]
        is_acceptable = len(missing) <= 1
        return {"is_acceptable": is_acceptable, "missing_fields": missing}

    def combine(
        self,
        image_issues: List[str],
        extracted_labels: List[str],
        side: str,
        ocr_confidence: float,
    ) -> Dict:
        """Combine Layer A + Layer B into final quality assessment."""
        mandatory = FRONT_MANDATORY if side == "front" else BACK_MANDATORY
        missing = [f for f in mandatory if f not in extracted_labels]

        # Layer A score
        blur_penalty = 0.3 if "blurry" in image_issues else 1.0
        brightness_penalty = 0.5 if ("too_dark" in image_issues or "too_bright" in image_issues) else 1.0
        resolution_penalty = 0.4 if "low_resolution" in image_issues else 1.0
        layer_a_score = blur_penalty * brightness_penalty * resolution_penalty

        # Layer B score
        layer_b_score = len([f for f in mandatory if f in extracted_labels]) / len(mandatory) if mandatory else 1.0

        score = 0.3 * layer_a_score + 0.7 * layer_b_score

        # Acceptability rules
        is_acceptable = True
        if len(missing) >= 2:
            is_acceptable = False
        elif "blurry" in image_issues and len(missing) >= 1:
            is_acceptable = False

        # Generate feedback
        feedback = self._generate_feedback(image_issues, missing)

        return {
            "score": round(score, 2),
            "is_acceptable": is_acceptable,
            "feedback": feedback,
            "missing_fields": missing,
            "issues": image_issues,
        }

    def _generate_feedback(self, image_issues: List[str], missing_fields: List[str]) -> Optional[str]:
        """Generate actionable feedback message."""
        if not image_issues and not missing_fields:
            return None

        parts = []
        if "blurry" in image_issues and missing_fields:
            return "Image is blurry and some fields could not be read. Please retake with steady hands in good lighting"

        for issue in image_issues:
            if issue in FEEDBACK_MESSAGES:
                parts.append(FEEDBACK_MESSAGES[issue])

        if missing_fields:
            field_names = ", ".join(f.replace("_", " ").title() for f in missing_fields)
            parts.append(f"Could not read: {field_names}. Please ensure the full document is visible")

        return ". ".join(parts) if parts else None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_image_quality.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add app/core/image_quality.py
git commit -m "feat: add image quality assessment module"
```

---

## Chunk 3: Document Authenticity Validation

### Task 6: Write document authenticity tests

**Files:**
- Create: `tests/test_document_validator.py`

- [ ] **Step 1: Write failing tests for document validator**

Create `tests/test_document_validator.py`:

```python
import io
import numpy as np
import cv2
import pytest
from app.core.document_validator import DocumentValidator


def _make_card_image(width=856, height=540, add_color_band=True):
    """Create a test image resembling a smart card RC."""
    img = np.full((height, width, 3), 240, dtype=np.uint8)
    if add_color_band:
        # Blue header band in top 20%
        img[:int(height * 0.2), :] = [180, 100, 50]  # BGR blue-ish
    cv2.putText(img, "RC", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 3)
    _, buffer = cv2.imencode(".png", img)
    return buffer.tobytes()


def _make_paper_image(width=600, height=800):
    """Create a test image resembling plain paper (wrong aspect ratio, no color bands)."""
    img = np.full((height, width, 3), 250, dtype=np.uint8)
    cv2.putText(img, "TEXT", (100, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 2)
    _, buffer = cv2.imencode(".png", img)
    return buffer.tobytes()


class TestStructuralChecks:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_valid_rc_text_passes_structure(self):
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: TEST"
        result = self.validator.check_structural(text, side="front")
        assert "structure" in result["checks_passed"]

    def test_missing_headers_fails_structure(self):
        text = "Random text\nSome values\nNothing useful"
        result = self.validator.check_structural(text, side="front")
        assert "structure" in result["checks_failed"]

    def test_valid_registration_format(self):
        text = "Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol"
        result = self.validator.check_structural(text, side="front")
        assert "registration_format" in result["checks_passed"]

    def test_invalid_registration_format(self):
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: INVALID123\nOwner: TEST\nFuel Type: Petrol"
        result = self.validator.check_structural(text, side="front")
        assert "registration_format" in result["checks_failed"]

    def test_field_structure_check(self):
        text = "FORM 23\nRegistration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol\nMake: MARUTI"
        result = self.validator.check_structural(text, side="front")
        assert "field_structure" in result["checks_passed"]

    def test_too_few_field_labels_fails(self):
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: KA01AB1234"
        result = self.validator.check_structural(text, side="front")
        assert "field_structure" in result["checks_failed"]


class TestVisualChecks:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_card_aspect_ratio_passes(self):
        image_bytes = _make_card_image(856, 540)
        result = self.validator.check_visual(image_bytes)
        assert "aspect_ratio" in result["checks_passed"]

    def test_wrong_aspect_ratio_fails(self):
        image_bytes = _make_paper_image(600, 800)
        result = self.validator.check_visual(image_bytes)
        assert "aspect_ratio" in result["checks_failed"]


class TestCombinedAuthenticity:
    def setup_method(self):
        self.validator = DocumentValidator()

    def test_all_structural_pass_is_authentic(self):
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol\nMake: MARUTI"
        image_bytes = _make_card_image()
        result = self.validator.validate(text, image_bytes, side="front")
        assert result["is_authentic"] is True

    def test_structural_fail_not_authentic(self):
        text = "Random printed text on paper"
        image_bytes = _make_paper_image()
        result = self.validator.validate(text, image_bytes, side="front")
        assert result["is_authentic"] is False

    def test_paper_rc_passes_structure_lower_confidence(self):
        """Paper-format RC: structural checks pass, visual checks fail, still authentic but lower confidence."""
        text = "FORM 23\nREGISTRATION CERTIFICATE\nRegistration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol\nMake: MARUTI"
        image_bytes = _make_paper_image()
        result = self.validator.validate(text, image_bytes, side="front")
        assert result["is_authentic"] is True
        assert result["confidence"] < 0.8  # Lower confidence due to failed visual checks
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_document_validator.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_document_validator.py
git commit -m "test: add document authenticity validation tests (red)"
```

### Task 7: Implement document authenticity validator

**Files:**
- Create: `app/core/document_validator.py`

- [ ] **Step 1: Implement DocumentValidator**

Create `app/core/document_validator.py`:

```python
import re
from typing import Dict, List, Optional

import cv2
import numpy as np

# Expected header markers in RC book text
RC_HEADER_MARKERS = [
    "form 23", "registration certificate", "government of india",
    "transport department", "registering authority",
]

# Indian registration number pattern: XX-00-XX-0000 with optional separators
RC_REG_NUMBER_PATTERN = re.compile(
    r"[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{4}"
)

# Field labels that indicate RC book structure
FRONT_FIELD_LABELS = ["owner", "fuel type", "make", "body type", "colour", "seating", "registration"]
BACK_FIELD_LABELS = ["engine no", "chassis no", "cubic capacity", "wheelbase", "unladen"]

# Smart card aspect ratio: 85.6mm / 54mm = 1.585
CARD_ASPECT_RATIO = 1.585
ASPECT_RATIO_TOLERANCE = 0.20

# Confidence bonuses for visual checks
ASPECT_RATIO_BONUS = 0.20
COLOR_BANDS_BONUS = 0.15
CARD_EDGES_BONUS = 0.15


class DocumentValidator:
    """Validate RC book document authenticity via structural and visual checks."""

    def check_structural(self, raw_text: str, side: str) -> Dict:
        """Critical checks based on OCR text content."""
        text_lower = raw_text.lower()
        checks_passed = []
        checks_failed = []

        # Check 1: Header markers
        header_found = any(marker in text_lower for marker in RC_HEADER_MARKERS)
        if header_found:
            checks_passed.append("structure")
        else:
            checks_failed.append("structure")

        # Check 2: Registration number format
        reg_match = RC_REG_NUMBER_PATTERN.search(raw_text.upper())
        if reg_match:
            checks_passed.append("registration_format")
        else:
            checks_failed.append("registration_format")

        # Check 3: Field structure — at least 3 expected field labels present
        field_labels = FRONT_FIELD_LABELS if side == "front" else BACK_FIELD_LABELS
        label_count = sum(1 for label in field_labels if label in text_lower)
        if label_count >= 3:
            checks_passed.append("field_structure")
        else:
            checks_failed.append("field_structure")

        return {"checks_passed": checks_passed, "checks_failed": checks_failed}

    def check_visual(self, image_bytes: bytes) -> Dict:
        """Confidence-only checks based on image properties."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        checks_passed = []
        checks_failed = []

        # Check: Aspect ratio
        aspect = w / h if h > 0 else 0
        if abs(aspect - CARD_ASPECT_RATIO) / CARD_ASPECT_RATIO <= ASPECT_RATIO_TOLERANCE:
            checks_passed.append("aspect_ratio")
        else:
            checks_failed.append("aspect_ratio")

        # Check: Color bands in top 20% of image
        top_region = img[:int(h * 0.2), :]
        hsv = cv2.cvtColor(top_region, cv2.COLOR_BGR2HSV)
        # Blue/green range in HSV
        lower_blue = np.array([90, 40, 40])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        color_ratio = np.count_nonzero(mask) / mask.size if mask.size > 0 else 0
        if color_ratio > 0.15:
            checks_passed.append("color_bands")
        else:
            checks_failed.append("color_bands")

        # Check: Card edges via Canny
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        card_edge_found = False
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                area = cv2.contourArea(approx)
                if area > (w * h * 0.3):  # Contour covers >30% of image
                    card_edge_found = True
                    break
        if card_edge_found:
            checks_passed.append("card_edges")
        else:
            checks_failed.append("card_edges")

        return {"checks_passed": checks_passed, "checks_failed": checks_failed}

    def validate(self, raw_text: str, image_bytes: bytes, side: str) -> Dict:
        """Run all checks and return combined authenticity result."""
        structural = self.check_structural(raw_text, side)
        visual = self.check_visual(image_bytes)

        all_passed = structural["checks_passed"] + visual["checks_passed"]
        all_failed = structural["checks_failed"] + visual["checks_failed"]

        # is_authentic: all critical (structural) checks must pass
        critical_checks = ["structure", "registration_format", "field_structure"]
        critical_failed = [c for c in structural["checks_failed"] if c in critical_checks]
        is_authentic = len(critical_failed) == 0

        # Confidence calculation
        confidence = 0.5 if is_authentic else 0.0
        if "aspect_ratio" in visual["checks_passed"]:
            confidence += ASPECT_RATIO_BONUS
        if "color_bands" in visual["checks_passed"]:
            confidence += COLOR_BANDS_BONUS
        if "card_edges" in visual["checks_passed"]:
            confidence += CARD_EDGES_BONUS
        confidence = min(confidence, 1.0)

        message = None
        if not is_authentic:
            message = "Document does not appear to be a valid RC book"

        return {
            "is_authentic": is_authentic,
            "confidence": round(confidence, 2),
            "checks_passed": all_passed,
            "checks_failed": all_failed,
            "message": message,
        }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_document_validator.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add app/core/document_validator.py
git commit -m "feat: add document authenticity validator"
```

---

## Chunk 4: Schema + Pipeline Integration

### Task 8: Write integration tests for pipeline changes (TDD)

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_extraction_service.py`
- Modify: `tests/test_schemas.py`

- [ ] **Step 1: Update test_api.py mock fixture to include new fields**

In `tests/test_api.py`, update the `mock_extraction_result` fixture:

```python
@pytest.fixture
def mock_extraction_result():
    return {
        "success": True,
        "document_type": "receipt",
        "confidence": 0.92,
        "fields": [{"label": "vendor", "value": "Big Bazaar"}],
        "raw_text": "raw text",
        "processing_time_ms": 100,
        "side": None,
        "image_quality": None,
        "authenticity": None,
    }
```

- [ ] **Step 2: Update test_extraction_service.py to mock new dependencies**

The new `ExtractionService.__init__` creates `ImageQualityAssessor` and `DocumentValidator` which use `cv2.imdecode`. Tests that pass `b"fake"` as image bytes will crash. Add mocks:

```python
# tests/test_extraction_service.py
from unittest.mock import MagicMock, patch
from app.core.extraction_service import ExtractionService


def _make_service(mock_router):
    """Create ExtractionService with mocked quality and validator."""
    with patch("app.core.extraction_service.ImageQualityAssessor") as mock_qa, \
         patch("app.core.extraction_service.DocumentValidator") as mock_dv:
        mock_qa_instance = MagicMock()
        mock_qa_instance.assess_image_properties.return_value = {"issues": [], "blur_score": 200.0, "brightness": 128.0}
        mock_qa_instance.combine.return_value = {
            "score": 1.0, "is_acceptable": True, "feedback": None, "missing_fields": [], "issues": [],
        }
        mock_qa.return_value = mock_qa_instance

        mock_dv_instance = MagicMock()
        mock_dv_instance.validate.return_value = {
            "is_authentic": True, "confidence": 0.85, "checks_passed": ["structure"], "checks_failed": [], "message": None,
        }
        mock_dv.return_value = mock_dv_instance

        service = ExtractionService(router=mock_router, enable_preprocessing=False)
        return service


def test_extraction_service_single_engine():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Vendor: Big Bazaar\nTotal: 1234\nDate: 15/01/2024\nBill No: B-123\nSubtotal: 1100\nGST: 134",
        "confidence": 0.92,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = _make_service(mock_router)

    result = service.extract(image_bytes=b"fake", engine="paddle")

    assert result["success"] is True
    assert result["document_type"] is not None
    assert result["confidence"] == 0.92
    assert isinstance(result["fields"], list)
    assert result["raw_text"] is not None


def test_extraction_service_with_document_type_hint():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Some text",
        "confidence": 0.85,
        "blocks": [],
        "processing_time_ms": 50,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = _make_service(mock_router)

    result = service.extract(
        image_bytes=b"fake",
        engine="paddle",
        document_type="receipt",
    )

    assert result["success"] is True
    assert result["document_type"] == "receipt"


def test_extraction_service_returns_side_for_rc_book():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol",
        "confidence": 0.85,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = _make_service(mock_router)

    result = service.extract(
        image_bytes=b"fake",
        engine="paddle",
        document_type="rc_book",
        side="front",
    )

    assert result["side"] == "front"
    assert result["image_quality"] is not None
    assert result["authenticity"] is not None


def test_extraction_service_non_rc_book_no_quality():
    mock_engine = MagicMock()
    mock_engine.extract.return_value = {
        "raw_text": "Vendor: Big Bazaar\nTotal: 1234",
        "confidence": 0.90,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_engine.get_name.return_value = "paddle"

    mock_router = MagicMock()
    mock_router.get_engine.return_value = mock_engine

    service = _make_service(mock_router)

    result = service.extract(image_bytes=b"fake", engine="paddle", document_type="receipt")

    assert result["image_quality"] is None
    assert result["authenticity"] is None
```

- [ ] **Step 3: Add schema validation tests**

Add to `tests/test_schemas.py`:

```python
from app.api.schemas import ExtractionRequest, ImageQuality, DocumentAuthenticity
import pytest


def test_side_validation_accepts_front():
    req = ExtractionRequest(image="base64data", side="front")
    assert req.side == "front"


def test_side_validation_accepts_back():
    req = ExtractionRequest(image="base64data", side="back")
    assert req.side == "back"


def test_side_validation_accepts_none():
    req = ExtractionRequest(image="base64data")
    assert req.side is None


def test_side_validation_rejects_invalid():
    with pytest.raises(ValueError):
        ExtractionRequest(image="base64data", side="left")


def test_image_quality_model():
    q = ImageQuality(score=0.8, is_acceptable=True, feedback=None, missing_fields=[], issues=[])
    assert q.score == 0.8
    assert q.is_acceptable is True


def test_document_authenticity_model():
    a = DocumentAuthenticity(is_authentic=True, confidence=0.85, checks_passed=["structure"], checks_failed=[], message=None)
    assert a.is_authentic is True
    assert a.confidence == 0.85
```

- [ ] **Step 4: Run tests to confirm they fail (new service tests + schema tests)**

Run: `pytest tests/test_extraction_service.py tests/test_api.py tests/test_schemas.py -v`
Expected: Some tests FAIL (service doesn't accept `side` yet, schemas don't have new models yet)

- [ ] **Step 5: Commit test updates**

```bash
git add tests/test_api.py tests/test_extraction_service.py tests/test_schemas.py
git commit -m "test: update existing tests for pipeline integration (red)"
```

### Task 9: Update API schemas

**Files:**
- Modify: `app/api/schemas.py`

- [ ] **Step 1: Add new schema models**

Update `app/api/schemas.py`:

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, model_validator


class ExtractionRequest(BaseModel):
    image: Optional[str] = None
    image_url: Optional[str] = None
    document_type: Optional[str] = None
    engine: str = "auto"
    include_raw_text: bool = True
    side: Optional[str] = None  # "front", "back", or None (auto-detect)

    @model_validator(mode="after")
    def check_image_source(self):
        if not self.image and not self.image_url:
            raise ValueError("Either 'image' (base64) or 'image_url' must be provided")
        return self

    @model_validator(mode="after")
    def check_side_value(self):
        if self.side is not None and self.side not in ("front", "back"):
            raise ValueError("'side' must be 'front', 'back', or null")
        return self


class FieldResult(BaseModel):
    label: str
    value: str


class ImageQuality(BaseModel):
    score: float
    is_acceptable: bool
    feedback: Optional[str] = None
    missing_fields: List[str] = []
    issues: List[str] = []


class DocumentAuthenticity(BaseModel):
    is_authentic: bool
    confidence: float
    checks_passed: List[str] = []
    checks_failed: List[str] = []
    message: Optional[str] = None


class ExtractionResponse(BaseModel):
    success: bool
    document_type: Optional[str] = None
    confidence: float = 0.0
    fields: List[FieldResult] = []
    raw_text: Optional[str] = None
    processing_time_ms: int = 0
    side: Optional[str] = None
    image_quality: Optional[ImageQuality] = None
    authenticity: Optional[DocumentAuthenticity] = None


class ComparisonResponse(BaseModel):
    success: bool
    document_type: Optional[str] = None
    results: Dict[str, Any] = {}
    comparison: Dict[str, Any] = {}
    recommendation: Optional[str] = None
    comparison_id: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str
    confidence: float = 0.0
```

- [ ] **Step 2: Run existing tests**

Run: `pytest tests/test_schemas.py tests/test_api.py -v`
Expected: All PASS (new fields have defaults, backward compatible)

- [ ] **Step 3: Commit**

```bash
git add app/api/schemas.py
git commit -m "feat: add ImageQuality, DocumentAuthenticity, side to schemas"
```

### Task 10: Integrate quality + authenticity into ExtractionService

**Files:**
- Modify: `app/core/extraction_service.py`
- Modify: `app/api/routes.py`

- [ ] **Step 1: Update ExtractionService to include quality and authenticity**

Replace `app/core/extraction_service.py`:

```python
# app/core/extraction_service.py
from typing import Any, Dict, List, Optional

from app.core.document_detector import DocumentDetector
from app.core.field_extractor import FieldExtractor
from app.core.image_quality import ImageQualityAssessor
from app.core.document_validator import DocumentValidator
from app.core.preprocessor import ImagePreprocessor
from app.core.router import EngineRouter
from app.mappers import get_mapper


class ExtractionService:
    """Orchestrates the full extraction pipeline."""

    def __init__(
        self,
        router: EngineRouter,
        enable_preprocessing: bool = True,
    ):
        self.router = router
        self.preprocessor = ImagePreprocessor(enabled=enable_preprocessing)
        self.detector = DocumentDetector()
        self.field_extractor = FieldExtractor()
        self.quality_assessor = ImageQualityAssessor()
        self.document_validator = DocumentValidator()

    def extract(
        self,
        image_bytes: bytes,
        engine: str = "paddle",
        document_type: Optional[str] = None,
        include_raw_text: bool = True,
        side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full extraction pipeline."""
        # 1. Layer A: Image quality properties (advisory, on raw image)
        image_props = self.quality_assessor.assess_image_properties(image_bytes)

        # 2. Preprocess
        processed = self.preprocessor.process(image_bytes)

        # 3. OCR
        ocr_engine = self.router.get_engine(engine)
        ocr_result = ocr_engine.extract(processed)

        raw_text = ocr_result["raw_text"]
        confidence = ocr_result["confidence"]
        processing_time_ms = ocr_result["processing_time_ms"]

        # 4. Detect document type (if not provided)
        if not document_type:
            document_type, _det_conf = self.detector.detect(raw_text)

        # 5. Auto-detect side before mapping (for rc_book)
        detected_side = side
        if document_type == "rc_book" and side is None:
            from app.mappers.rc_book import _detect_side
            detected_side = _detect_side(raw_text)

        # 6. Map fields using type-specific mapper
        fields: List[Dict[str, str]] = []
        try:
            mapper = get_mapper(document_type)
            fields = mapper.map_fields(raw_text, side=detected_side)
        except ValueError:
            fields = self.field_extractor.extract(raw_text)

        # 7. Layer B: Extraction completeness + combined quality
        image_quality = None
        if document_type == "rc_book" and detected_side:
            extracted_labels = [f["label"] for f in fields]
            image_quality = self.quality_assessor.combine(
                image_issues=image_props["issues"],
                extracted_labels=extracted_labels,
                side=detected_side,
                ocr_confidence=confidence,
            )

        # 8. Document authenticity
        authenticity = None
        if document_type == "rc_book" and detected_side:
            authenticity = self.document_validator.validate(
                raw_text=raw_text,
                image_bytes=image_bytes,
                side=detected_side,
            )

        return {
            "success": True,
            "document_type": document_type,
            "confidence": confidence,
            "fields": fields,
            "raw_text": raw_text if include_raw_text else None,
            "processing_time_ms": processing_time_ms,
            "side": detected_side,
            "image_quality": image_quality,
            "authenticity": authenticity,
        }
```

- [ ] **Step 2: Update routes to pass `side` and return new fields**

Replace `app/api/routes.py`:

```python
# app/api/routes.py
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    DocumentAuthenticity,
    ExtractionRequest,
    ExtractionResponse,
    FieldResult,
    ImageQuality,
)
from app.config import settings
from app.core.extraction_service import ExtractionService
from app.core.router import EngineRouter
from app.utils.image_utils import decode_base64_image, fetch_image_url

router = APIRouter()

# Initialize engine router (engines registered at startup in main.py)
engine_router = EngineRouter()
extraction_service = ExtractionService(
    router=engine_router,
    enable_preprocessing=settings.ENABLE_PREPROCESSING,
)


def _get_image_bytes(request: ExtractionRequest) -> bytes:
    if request.image:
        return decode_base64_image(request.image)
    elif request.image_url:
        return fetch_image_url(request.image_url)
    raise HTTPException(status_code=400, detail="No image provided")


def _build_response(result: dict) -> ExtractionResponse:
    """Build ExtractionResponse from service result dict."""
    image_quality = None
    if result.get("image_quality"):
        image_quality = ImageQuality(**result["image_quality"])

    authenticity = None
    if result.get("authenticity"):
        authenticity = DocumentAuthenticity(**result["authenticity"])

    return ExtractionResponse(
        success=result["success"],
        document_type=result["document_type"],
        confidence=result["confidence"],
        fields=[FieldResult(**f) for f in result["fields"]],
        raw_text=result["raw_text"],
        processing_time_ms=result["processing_time_ms"],
        side=result.get("side"),
        image_quality=image_quality,
        authenticity=authenticity,
    )


@router.get("/health")
def health():
    return {"status": "healthy", "engines": engine_router.list_engines()}


@router.get("/engines")
def list_engines():
    return {"engines": engine_router.list_engines()}


@router.post("/extract", response_model=ExtractionResponse)
def extract(request: ExtractionRequest):
    image_bytes = _get_image_bytes(request)
    engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

    result = extraction_service.extract(
        image_bytes=image_bytes,
        engine=engine,
        document_type=request.document_type,
        include_raw_text=request.include_raw_text,
        side=request.side,
    )

    return _build_response(result)


def _make_type_endpoint(doc_type: str):
    def endpoint(request: ExtractionRequest):
        image_bytes = _get_image_bytes(request)
        engine = request.engine if request.engine != "auto" else settings.DEFAULT_ENGINE

        result = extraction_service.extract(
            image_bytes=image_bytes,
            engine=engine,
            document_type=doc_type,
            include_raw_text=request.include_raw_text,
            side=request.side,
        )

        return _build_response(result)

    return endpoint


# Expense Tracking
router.post("/extract/receipt", response_model=ExtractionResponse)(
    _make_type_endpoint("receipt")
)
router.post("/extract/invoice", response_model=ExtractionResponse)(
    _make_type_endpoint("invoice")
)

# Driver Onboarding
router.post("/extract/driving-license", response_model=ExtractionResponse)(
    _make_type_endpoint("driving_license")
)
router.post("/extract/rc-book", response_model=ExtractionResponse)(
    _make_type_endpoint("rc_book")
)
router.post("/extract/insurance", response_model=ExtractionResponse)(
    _make_type_endpoint("insurance")
)

# Fuel Tracking
router.post("/extract/petrol-receipt", response_model=ExtractionResponse)(
    _make_type_endpoint("petrol_receipt")
)
router.post("/extract/odometer", response_model=ExtractionResponse)(
    _make_type_endpoint("odometer")
)
router.post("/extract/fuel-pump-reading", response_model=ExtractionResponse)(
    _make_type_endpoint("fuel_pump_reading")
)
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/extraction_service.py app/api/routes.py
git commit -m "feat: integrate image quality and authenticity into extraction pipeline"
```

---

## Chunk 5: Multi-Engine Comparison + Compare Endpoint

### Task 11: Write N-engine comparison tests

**Files:**
- Create: `tests/test_comparison_n_engine.py`

- [ ] **Step 1: Write failing tests for N-engine comparison**

Create `tests/test_comparison_n_engine.py`:

```python
from unittest.mock import MagicMock
from app.comparison.comparator import EngineComparator
from app.comparison.metrics import calculate_comparison_metrics


class TestNEngineComparator:
    def test_compare_three_engines(self):
        engines = {}
        for name in ["paddle", "easyocr", "tesseract"]:
            engine = MagicMock()
            engine.get_name.return_value = name
            engine.extract.return_value = {
                "raw_text": f"Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol",
                "confidence": 0.85 if name == "paddle" else 0.70,
                "blocks": [],
                "processing_time_ms": 100,
            }
            engines[name] = engine

        comparator = EngineComparator(engines=engines)
        result = comparator.compare(b"fake_image", document_type="rc_book", side="front")

        assert "engines" in result
        assert len(result["engines"]) == 3
        assert "paddle" in result["engines"]
        assert "easyocr" in result["engines"]
        assert "tesseract" in result["engines"]
        assert "field_agreement" in result
        assert "summary" in result
        assert "recommendation" in result

    def test_recommendation_picks_most_mandatory_fields(self):
        engines = {}
        # Paddle finds more fields
        paddle = MagicMock()
        paddle.get_name.return_value = "paddle"
        paddle.extract.return_value = {
            "raw_text": "Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol\nMake: MARUTI\nDate of Registration: 01/01/2020",
            "confidence": 0.85,
            "blocks": [],
            "processing_time_ms": 100,
        }
        engines["paddle"] = paddle

        # Tesseract finds fewer
        tesseract = MagicMock()
        tesseract.get_name.return_value = "tesseract"
        tesseract.extract.return_value = {
            "raw_text": "Registration No: KA01AB1234\nOwner: TEST",
            "confidence": 0.60,
            "blocks": [],
            "processing_time_ms": 50,
        }
        engines["tesseract"] = tesseract

        comparator = EngineComparator(engines=engines)
        result = comparator.compare(b"fake_image", document_type="rc_book", side="front")
        assert result["recommendation"] == "paddle"


class TestNEngineMetrics:
    def test_full_agreement(self):
        engine_fields = {
            "paddle": [{"label": "registration_number", "value": "KA01AB1234"}],
            "easyocr": [{"label": "registration_number", "value": "KA01AB1234"}],
            "tesseract": [{"label": "registration_number", "value": "KA01AB1234"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["field_agreement"]["registration_number"]["agreement"] == "full"

    def test_partial_agreement(self):
        engine_fields = {
            "paddle": [{"label": "registration_number", "value": "KA01AB1234"}],
            "easyocr": [{"label": "registration_number", "value": "KA01AB1234"}],
            "tesseract": [{"label": "registration_number", "value": "KA01A81234"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["field_agreement"]["registration_number"]["agreement"] == "partial"

    def test_disagreement(self):
        engine_fields = {
            "paddle": [{"label": "owner_name", "value": "RAJESH"}],
            "easyocr": [{"label": "owner_name", "value": "RAKESH"}],
            "tesseract": [{"label": "owner_name", "value": "RAMESH"}],
        }
        result = calculate_comparison_metrics(engine_fields)
        assert result["field_agreement"]["owner_name"]["agreement"] == "disagreement"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_comparison_n_engine.py -v`
Expected: FAIL (EngineComparator constructor changed, metrics function changed)

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_comparison_n_engine.py
git commit -m "test: add N-engine comparison tests (red)"
```

### Task 12: Implement N-engine comparator and metrics + update old tests

**Files:**
- Modify: `app/comparison/comparator.py`
- Modify: `app/comparison/metrics.py`

- [ ] **Step 1: Rewrite metrics for N-engine comparison**

Replace `app/comparison/metrics.py`:

```python
from typing import Dict, List
from collections import Counter


def calculate_comparison_metrics(
    engine_fields: Dict[str, List[Dict[str, str]]],
) -> Dict:
    """Calculate comparison metrics across N engines.

    Args:
        engine_fields: Dict mapping engine name to list of {"label": ..., "value": ...}
    """
    engine_names = list(engine_fields.keys())

    # Build per-engine field dicts
    engine_dicts = {}
    for name, fields in engine_fields.items():
        engine_dicts[name] = {f["label"]: f["value"] for f in fields}

    # Collect all labels across all engines
    all_labels = set()
    for d in engine_dicts.values():
        all_labels.update(d.keys())

    field_agreement = {}
    full_count = 0
    partial_count = 0
    disagreement_count = 0

    for label in sorted(all_labels):
        values = {}
        for name in engine_names:
            val = engine_dicts[name].get(label)
            if val is not None:
                values[name] = val

        if len(values) <= 1:
            # Only one engine has this field — no agreement to measure
            agreement = "single"
        else:
            # Check agreement
            val_list = list(values.values())
            val_counts = Counter(val_list)
            most_common_count = val_counts.most_common(1)[0][1]

            if most_common_count == len(val_list):
                agreement = "full"
                full_count += 1
            elif most_common_count >= 2:
                agreement = "partial"
                partial_count += 1
            else:
                agreement = "disagreement"
                disagreement_count += 1

        field_agreement[label] = {"values": values, "agreement": agreement}

    summary = {
        "mandatory_fields_found": {
            name: len(engine_dicts[name]) for name in engine_names
        },
        "full_agreement_fields": full_count,
        "partial_agreement_fields": partial_count,
        "disagreement_fields": disagreement_count,
    }

    return {"field_agreement": field_agreement, "summary": summary}
```

- [ ] **Step 2: Rewrite comparator for N engines**

Replace `app/comparison/comparator.py`:

```python
from typing import Any, Dict, Optional
from app.engines.base import BaseOCREngine
from app.comparison.metrics import calculate_comparison_metrics
from app.mappers import get_mapper
from app.core.field_extractor import FieldExtractor
from app.mappers.rc_book import FRONT_MANDATORY, BACK_MANDATORY


class EngineComparator:
    def __init__(self, engines: Dict[str, BaseOCREngine]):
        self.engines = engines
        self.field_extractor = FieldExtractor()

    def compare(
        self,
        image: bytes,
        document_type: str = "rc_book",
        side: Optional[str] = None,
    ) -> Dict[str, Any]:
        engine_results = {}
        engine_fields = {}

        for name, engine in self.engines.items():
            result = engine.extract(image)
            raw_text = result["raw_text"]

            # Map fields
            try:
                mapper = get_mapper(document_type)
                fields = mapper.map_fields(raw_text, side=side)
            except ValueError:
                fields = self.field_extractor.extract(raw_text)

            engine_results[name] = {
                "confidence": result["confidence"],
                "fields": fields,
                "raw_text": raw_text,
                "processing_time_ms": result["processing_time_ms"],
            }
            engine_fields[name] = fields

        metrics = calculate_comparison_metrics(engine_fields)

        # Recommendation: most mandatory fields, then confidence, then speed
        mandatory = FRONT_MANDATORY if side != "back" else BACK_MANDATORY
        recommendation = self._recommend(engine_results, mandatory)

        return {
            "engines": engine_results,
            "field_agreement": metrics["field_agreement"],
            "summary": metrics["summary"],
            "recommendation": recommendation,
        }

    def _recommend(self, engine_results: Dict, mandatory: list) -> str:
        """Pick best engine: most mandatory fields > highest confidence > fastest."""
        scored = []
        for name, result in engine_results.items():
            field_dict = {f["label"]: f["value"] for f in result["fields"]}
            mandatory_count = sum(1 for m in mandatory if m in field_dict)
            scored.append((
                mandatory_count,
                result["confidence"],
                -result["processing_time_ms"],  # negative so higher = faster
                name,
            ))
        scored.sort(reverse=True)
        return scored[0][3] if scored else ""
```

- [ ] **Step 3: Update existing comparison tests for new API**

Replace `tests/test_comparison.py` to work with the new N-engine API:

```python
# tests/test_comparison.py
from app.comparison.metrics import calculate_comparison_metrics
from app.comparison.comparator import EngineComparator
from unittest.mock import MagicMock


def test_calculate_metrics_exact_match():
    engine_fields = {
        "paddle": [
            {"label": "vendor", "value": "Big Bazaar"},
            {"label": "total", "value": "1234"},
        ],
        "google": [
            {"label": "vendor", "value": "Big Bazaar"},
            {"label": "total", "value": "1234"},
        ],
    }
    metrics = calculate_comparison_metrics(engine_fields)
    assert metrics["summary"]["full_agreement_fields"] == 2
    assert metrics["summary"]["disagreement_fields"] == 0


def test_calculate_metrics_partial_match():
    engine_fields = {
        "paddle": [{"label": "total", "value": "1234"}],
        "easyocr": [{"label": "total", "value": "1234"}],
        "google": [{"label": "total", "value": "\u20b91,234.00"}],
    }
    metrics = calculate_comparison_metrics(engine_fields)
    assert metrics["summary"]["partial_agreement_fields"] >= 1 or metrics["summary"]["disagreement_fields"] >= 1


def test_calculate_metrics_one_engine_only():
    engine_fields = {
        "paddle": [{"label": "vendor", "value": "Big Bazaar"}],
        "google": [
            {"label": "vendor", "value": "Big Bazaar"},
            {"label": "date", "value": "15/01/2024"},
        ],
    }
    metrics = calculate_comparison_metrics(engine_fields)
    assert metrics["field_agreement"]["date"]["agreement"] == "single"


def test_comparator_runs_all_engines():
    mock_paddle = MagicMock()
    mock_paddle.extract.return_value = {
        "raw_text": "Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol",
        "confidence": 0.90,
        "blocks": [],
        "processing_time_ms": 100,
    }
    mock_paddle.get_name.return_value = "paddle"

    mock_google = MagicMock()
    mock_google.extract.return_value = {
        "raw_text": "Registration No: KA01AB1234\nOwner: TEST\nFuel Type: Petrol",
        "confidence": 0.95,
        "blocks": [],
        "processing_time_ms": 200,
    }
    mock_google.get_name.return_value = "google"

    comparator = EngineComparator(engines={"paddle": mock_paddle, "google": mock_google})
    result = comparator.compare(b"fake_image", document_type="rc_book", side="front")

    assert "engines" in result
    assert "paddle" in result["engines"]
    assert "google" in result["engines"]
    assert result["engines"]["paddle"]["confidence"] == 0.90
    assert result["engines"]["google"]["confidence"] == 0.95
```

- [ ] **Step 4: Run all comparison tests**

Run: `pytest tests/test_comparison.py tests/test_comparison_n_engine.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/comparison/comparator.py app/comparison/metrics.py tests/test_comparison.py
git commit -m "feat: generalize engine comparison to N engines"
```

### Task 13: Add `/compare/rc-book` endpoint

**Files:**
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add comparison endpoint to routes**

Add at the end of `app/api/routes.py`:

```python
@router.post("/compare/rc-book")
def compare_rc_book(request: ExtractionRequest):
    """Compare all engines on an RC book image. For testing phase."""
    image_bytes = _get_image_bytes(request)

    # Preprocess
    from app.core.preprocessor import ImagePreprocessor
    preprocessor = ImagePreprocessor(enabled=settings.ENABLE_PREPROCESSING)
    processed = preprocessor.process(image_bytes)

    # Gather all registered engines
    from app.comparison.comparator import EngineComparator
    engine_names = engine_router.list_engines()
    engines = {name: engine_router.get_engine(name) for name in engine_names}

    comparator = EngineComparator(engines=engines)
    result = comparator.compare(
        image=processed,
        document_type="rc_book",
        side=request.side,
    )

    return {"success": True, **result}
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add /compare/rc-book endpoint for multi-engine testing"
```

---

## Chunk 6: Final Integration Tests + Deploy & Live Testing

### Task 14: Final full test suite verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Fix any remaining failures**

If any test fails, fix it. Common causes:
- Missing `side=None` default in a mapper's `map_fields`
- Mock fixtures missing new response keys

- [ ] **Step 3: Commit any fixes**

```bash
git add .
git commit -m "fix: resolve remaining test failures"
```

### Task 15: Deploy and live test with deployed API

**Files:** None (manual testing)

- [ ] **Step 1: Push to main to trigger deployment**

```bash
git push origin main
```

Wait for CI/CD pipeline to complete.

- [ ] **Step 2: Verify health endpoint**

```bash
curl -s https://ocr2text-production.up.railway.app/health | python3 -m json.tool
```

Expected: `{"status": "healthy", "engines": ["paddle", "easyocr", "tesseract"]}`

- [ ] **Step 3: Test RC book front extraction with image URL**

Test the `/extract/rc-book` endpoint with an RC book image URL:

```bash
curl -s -X POST https://ocr2text-production.up.railway.app/extract/rc-book \
  -H "Content-Type: application/json" \
  -d '{"image_url": "<RC_BOOK_IMAGE_URL>", "side": "front"}' | python3 -m json.tool
```

Review: `fields[]`, `side`, `image_quality`, `authenticity` in response.

- [ ] **Step 4: Test multi-engine comparison**

```bash
curl -s -X POST https://ocr2text-production.up.railway.app/compare/rc-book \
  -H "Content-Type: application/json" \
  -d '{"image_url": "<RC_BOOK_IMAGE_URL>", "side": "front"}' | python3 -m json.tool
```

Review: per-engine fields, agreement matrix, recommendation.

- [ ] **Step 5: Iterate on mapper aliases based on real OCR output**

Compare raw_text from each engine with mapped fields. Add missing aliases to `app/mappers/rc_book.py` for any fields that appear in raw_text but weren't mapped.
