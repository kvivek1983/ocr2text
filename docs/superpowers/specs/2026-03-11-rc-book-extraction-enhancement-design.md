# RC Book Extraction Enhancement Design

## Overview

Enhance the OCR extraction system for Indian RC (Registration Certificate) books with:
1. Expanded field mapping with front/back side support
2. Image quality assessment (pre-OCR + post-OCR)
3. Document authenticity validation (structural + visual)
4. Multi-engine comparison for testing phase
5. Iterative structural pattern discovery per state/format

## API Changes

### Request: `side` parameter

Add optional `side` field to `ExtractionRequest`:

```python
side: Optional[str] = None  # "front", "back", or None (auto-detect)
```

- `"front"` / `"back"` — caller specifies which side of the RC book
- `None` — system auto-detects based on which fields are found in OCR text
- Front/back are separate API calls; client merges results using `registration_number` as the common key (appears on both sides)

**Auto-detection logic:** Score both sides based on how many side-specific field labels appear in OCR text. Whichever side has more matching labels wins. If tied, default to "front". Fields used for scoring:
- Front indicators: "Owner", "Address", "Fuel Type", "Body Type", "Colour", "Seating"
- Back indicators: "Engine No", "Chassis No", "Cubic Capacity", "Wheelbase", "Cylinders", "Unladen Weight"
- `registration_number` appears on both sides and is NOT used for side detection

### Response: new optional fields

```python
class ImageQuality(BaseModel):
    score: float                    # 0.0 - 1.0
    is_acceptable: bool
    feedback: Optional[str] = None
    missing_fields: List[str] = []  # mandatory fields not extracted
    issues: List[str] = []          # "blurry", "too_dark", "low_resolution", "too_bright"

class DocumentAuthenticity(BaseModel):
    is_authentic: bool
    confidence: float               # 0.0 - 1.0
    checks_passed: List[str] = []
    checks_failed: List[str] = []
    message: Optional[str] = None

class ExtractionResponse(BaseModel):
    # ... existing fields unchanged ...
    side: Optional[str] = None          # "front" or "back" (detected or echoed)
    image_quality: Optional[ImageQuality] = None
    authenticity: Optional[DocumentAuthenticity] = None
```

All new fields optional — backward compatible.

## Component 1: Expanded RC Book Mapper

### Common Field (appears on both sides)

| Field | Mandatory | Aliases |
|-------|-----------|---------|
| registration_number | Yes (both sides) | "Regn No", "Registration No", "Vehicle No", "Reg. No.", "Regn. No" |

`registration_number` is always extracted regardless of side. It serves as the **merge key** for the client to join front + back results from two separate API calls.

### Front Side Fields

| Field | Mandatory | Aliases |
|-------|-----------|---------|
| owner_name | Yes | "Owner", "Name", "Registered Owner", "Owner's Name" |
| father_name | No | "S/O", "D/O", "W/O", "S/W/D of", "Son of", "Daughter of", "Wife of" |
| address | No | "Address", "Permanent Address", "Present Address" |
| vehicle_make | Yes | "Maker", "Maker's Name", "Manufacturer", "Make", "Vehicle Make" |
| vehicle_model | No | "Model", "Vehicle Model", "Maker Model" |
| fuel_type | Yes | "Fuel Type", "Fuel Used", "Type of Fuel", "Fuel" |
| vehicle_type | No | "Body Type", "Vehicle Class", "Type of Body", "Veh. Class" |
| color | No | "Colour", "Color", "Vehicle Colour" |
| seating_capacity | No | "Seating Capacity", "Seats", "No. of Seats", "Seating Cap" |
| registration_date | Yes | "Date of Reg", "Regn Date", "Date of Registration", "Reg Date" |
| fitness_expiry | No | "Fitness Upto", "Fit Upto", "Fitness Valid Till" |
| tax_expiry | No | "Tax Upto", "Tax Valid Till", "Tax Paid Upto" |
| rto | No | "RTO", "Registering Authority", "Registration Authority", "Reg. Authority" |

Front mandatory (5): registration_number, owner_name, vehicle_make, fuel_type, registration_date

### Back Side Fields

| Field | Mandatory | Aliases |
|-------|-----------|---------|
| engine_number | Yes | "Engine No", "Engine Number", "Eng No", "Eng. No" |
| chassis_number | Yes | "Chassis No", "Chassis Number", "Ch No", "Chasi No", "Ch. No" |
| manufacturing_date | No | "Mfg Date", "Manufacturing Date", "Month/Year of Mfg", "Mfg. Date" |
| unladen_weight | No | "Unladen Weight", "ULW", "Unladen Wt", "UL Weight" |
| cubic_capacity | No | "Cubic Capacity", "CC", "Engine CC", "Cubic Cap" |
| wheelbase | No | "Wheelbase", "Wheel Base" |
| cylinders | No | "No of Cyl", "Cylinders", "No. of Cylinders", "Noof Cyl" |
| emission_norms | No | "Emission Norms", "BS", "Bharat Stage", "Emission Standard" |
| hypothecation | No | "Hypothecation", "Financer", "HP", "Hypothecated To" |
| insurance_validity | No | "Insurance Upto", "Insurance Valid Till", "Ins. Upto" |
| standing_capacity | No | "Standing Capacity" |

Back mandatory (3): registration_number, engine_number, chassis_number

### Alias expansion

Aliases grow iteratively as we test with real images from different states. Each state has 2-3 RC formats with varying label text. Discovered patterns are added in real-time during testing.

### How `side` flows through the system

1. `ExtractionRequest.side` is passed to `ExtractionService.extract()` as a new optional `side` parameter
2. `ExtractionService` passes `side` to `get_mapper()` which returns `RCBookMapper`
3. `RCBookMapper.map_fields(raw_text, side)` uses `side` to select which field set to apply
4. **Only `RCBookMapper` changes.** The `BaseMapper.map_fields` signature adds `side: Optional[str] = None` with a default of `None`. All existing mappers ignore it — no breaking changes. Only mappers that care about sides override the behavior.

```python
class BaseMapper(ABC):
    @abstractmethod
    def map_fields(self, raw_text: str, side: Optional[str] = None) -> List[Dict[str, str]]:
        pass
```

## Component 2: Image Quality Assessment

New module: `app/core/image_quality.py`

### Layer A: Image Properties (pre-OCR)

Evaluated on raw image bytes before preprocessing. Layer A performs its own grayscale conversion internally for blur detection. Brightness is measured on the grayscale image (mean pixel intensity).

- **Blur**: `cv2.Laplacian(gray, cv2.CV_64F).var()` — below 100 = blurry
- **Brightness**: mean pixel intensity of grayscale — below 50 = too dark, above 200 = washed out
- **Resolution**: minimum 640x480 for readable text

**Layer A is advisory only.** It always allows the pipeline to continue to OCR. It reports issues but never short-circuits. Rationale: even a blurry image might yield enough OCR text for some fields, and we always want to return best-effort results.

### Layer B: Extraction Completeness (post-OCR)

Evaluated after OCR and field mapping:

- Count mandatory fields extracted vs expected (based on `side`)
- Front: 5 mandatory, Back: 3 mandatory
- All mandatory present = acceptable
- Missing 1 mandatory = acceptable with warning
- Missing 2+ mandatory = not acceptable

### Combined Score Formula

```
layer_a_score = (1.0 if not blurry else 0.3) * (1.0 if brightness_ok else 0.5) * (1.0 if resolution_ok else 0.4)
layer_b_score = mandatory_fields_found / total_mandatory_expected
score = 0.3 * layer_a_score + 0.7 * layer_b_score
```

**`is_acceptable` rules:**
- If 2+ mandatory fields missing → `is_acceptable = False` (regardless of Layer A)
- If Layer A detects blur AND 1+ mandatory field missing → `is_acceptable = False`
- Otherwise → `is_acceptable = True`

Layer A alone never makes `is_acceptable = False` — a blurry image with all fields extracted is acceptable (with issues noted). But blur + missing fields together is not acceptable, since the blur likely caused the missed fields.

### Feedback Messages

Specific, actionable messages based on detected issues:

- `["blurry"]` -> "Image appears blurry. Hold the camera steady and ensure the document is in focus"
- `["too_dark"]` -> "Image is too dark. Please retake in better lighting"
- `["too_bright"]` -> "Image is overexposed. Avoid direct light on the document"
- `["low_resolution"]` -> "Image resolution is too low. Move the camera closer to the document"
- `missing_fields` -> "Could not read: {field_names}. Please ensure the full document is visible"
- blur + missing -> "Image is blurry and some fields could not be read. Please retake with steady hands in good lighting"

## Component 3: Document Authenticity Validation

New module: `app/core/document_validator.py`

### Structural Checks (text-based) — CRITICAL

These are pass/fail checks. If any critical check fails, `is_authentic = False`.

- **structure**: Expected header markers in OCR text: "Form 23", "Registration Certificate", state transport department names. At least 1 must be present.
- **registration_format**: Registration number matches Indian pattern: `[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{4}` (e.g., KA-01-AB-1234, MH12DE5678). If registration_number is extracted, it must match.
- **field_structure**: At least 3 mandatory field *labels* must appear in the OCR text (confirms RC layout, not random text with matching keywords).

### Visual Checks (OpenCV) — CONFIDENCE-ONLY

These do not set `is_authentic = False` on their own. They adjust the `confidence` score.

- **aspect_ratio**: Smart card RC = ~1.586:1 (85.6mm x 54mm). Detected document region should match within 20% tolerance. Adds 0.2 to confidence if passed.
- **color_bands**: Indian RC smart cards have characteristic blue/green header bands. Check for expected color ranges in HSV space in top 20% of image. Adds 0.15 to confidence if found.
- **card_edges**: Canny edge detection to verify card-shaped rectangular boundary exists. Distinguishes card from text on plain paper. Adds 0.15 to confidence if found.

**Note on paper-format RCs:** Older Indian RCs are paper booklets, not smart cards. Visual checks will naturally fail for these — that is expected. Since visual checks are confidence-only (not critical), paper-format RCs will still pass with `is_authentic = True` at lower confidence. This is a known limitation. The structural checks (text-based) work for both formats.

### Confidence Calculation

```
base_confidence = 0.5 if all critical checks pass, else 0.0
confidence = base_confidence + aspect_ratio_bonus + color_bands_bonus + card_edges_bonus
# Capped at 1.0
```

### Result

```python
critical_checks = ["structure", "registration_format", "field_structure"]
visual_checks = ["aspect_ratio", "color_bands", "card_edges"]
is_authentic = all critical checks passed
```

## Component 4: Multi-Engine Comparison (Testing Phase)

Generalize `EngineComparator` to support N engines (currently hardcoded for 2).

During testing, each RC image runs through all available engines (paddle, easyocr, tesseract).

### Comparison output structure

```python
{
    "engines": {
        "paddle": {"confidence": 0.85, "fields": [...], "raw_text": "...", "processing_time_ms": 1200},
        "easyocr": {"confidence": 0.78, "fields": [...], "raw_text": "...", "processing_time_ms": 2100},
        "tesseract": {"confidence": 0.62, "fields": [...], "raw_text": "...", "processing_time_ms": 400}
    },
    "field_agreement": {
        "registration_number": {"values": {"paddle": "KA01AB1234", "easyocr": "KA01AB1234", "tesseract": "KA01A81234"}, "agreement": "partial"},
        "owner_name": {"values": {"paddle": "JOHN DOE", "easyocr": "JOHN DOE", "tesseract": "JOHN DOE"}, "agreement": "full"}
    },
    "summary": {
        "mandatory_fields_found": {"paddle": 5, "easyocr": 4, "tesseract": 3},
        "full_agreement_fields": 8,
        "partial_agreement_fields": 2,
        "disagreement_fields": 1
    },
    "recommendation": "paddle"
}
```

**Agreement definitions:**
- `"full"` — all engines produced the same value
- `"partial"` — majority agree (2 of 3)
- `"disagreement"` — all different

**Recommendation logic:** Engine that extracted the most mandatory fields wins. Ties broken by confidence score, then by processing time (faster wins).

### How comparison is used

The comparison is for the **testing phase only** — called manually from Claude Code sessions via curl. It is not integrated into the main `/extract` endpoint. We add a new endpoint:

```
POST /compare/rc-book
```

Accepts same request body as `/extract/rc-book` (image + side). Runs all registered engines and returns the comparison structure above.

## Pipeline Flow

```
Request (image + side + document_type)
  |
  +-> Layer A: Image property checks (blur, brightness, resolution) [advisory only]
  |
  +-> Preprocessor (existing: grayscale, denoise, contrast, threshold)
  |
  +-> OCR Engine
  |
  +-> Document type detection (existing, if type not provided)
  |
  +-> Side auto-detection (if side not provided, score front vs back indicators)
  |
  +-> RC Book Mapper (common fields + side-specific fields)
  |
  +-> Layer B: Extraction completeness check (mandatory fields vs side)
  |
  +-> Document authenticity validation (structural on OCR text + visual on raw image)
  |
  +-> Response (fields + side + image_quality + authenticity)
```

## Cross-Side Analysis (Client Responsibility)

When the client has results from both front and back calls:

1. **Merge key**: `registration_number` appears on both sides. Client matches front + back using this field.
2. **Cross-validation**: If `registration_number` differs between front and back responses, the images may not be from the same RC book — client should flag this.
3. **Combined view**: Client merges `fields[]` from both responses into a complete RC record. No duplicate fields expected (except registration_number which should match).

If during testing we discover additional fields common to both sides, we add them to the common set and they become additional cross-validation points.

## Testing Strategy

1. User shares RC book image URLs during Claude Code sessions
2. Call deployed API at ocr2text-production.up.railway.app
3. Use `/compare/rc-book` to run all 3 engines per image
4. Review raw_text and mapped fields per engine
5. Iterate on aliases and structural patterns per state/format discovered
6. Determine best default engine for Indian RC books
7. Unit tests for new components (quality, authenticity, expanded mapper)

## File Changes Summary

| File | Change |
|------|--------|
| `app/api/schemas.py` | Add ImageQuality, DocumentAuthenticity, side field to request + response |
| `app/api/routes.py` | Pass side to extraction service, add `/compare/rc-book` endpoint |
| `app/mappers/base.py` | Add `side: Optional[str] = None` to `map_fields` signature |
| `app/mappers/rc_book.py` | Expand fields, split front/back/common, add aliases |
| `app/mappers/receipt.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/invoice.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/driving_license.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/insurance.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/petrol_receipt.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/odometer.py` | Add `side=None` to `map_fields` (ignored) |
| `app/mappers/fuel_pump_reading.py` | Add `side=None` to `map_fields` (ignored) |
| `app/core/image_quality.py` | New — blur, brightness, resolution + completeness scoring |
| `app/core/document_validator.py` | New — structural + visual authenticity checks |
| `app/core/extraction_service.py` | Integrate side, quality, authenticity into pipeline |
| `app/comparison/comparator.py` | Generalize to N engines |
| `app/comparison/metrics.py` | Generalize from 2-engine to N-engine with agreement matrix |
| Tests | New tests for all new/changed components |
