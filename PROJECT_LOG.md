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
tests/          - pytest suite (191+ tests)
```

**Key patterns:**
- Plugin architecture: `BaseOCREngine` abstract class, engines registered at startup
- Mapper registry: `BaseMapper` per document type, alias-based regex field extraction
- Pipeline: image preprocessing -> OCR -> document detection -> field mapping

---

## Active Initiatives

### "RC SmartExtract" — RC Book Extraction Enhancement

**Status:** Live testing & hardening (Phase 2)
**Reference name:** `rc-smartextract` — use this to resume work on RC book extraction improvements.

**Goal:** Production-grade extraction for Indian Registration Certificates (RC books/smart cards) across all states, with front/back support, image quality feedback, document authenticity validation, and multi-engine comparison.

**What this covers:**
1. Front/back side-aware extraction with auto-detection
2. Multi-state format handling (KA, GJ, and accumulating more)
3. Image quality assessment (blur, brightness, resolution, field completeness)
4. Document authenticity validation (structural + visual checks)
5. N-engine comparison (`/compare/rc-book` endpoint)
6. OCR noise tolerance (typo-tolerant aliases, regex fallbacks, multi-line extraction)

**Current state (2026-03-12):**
- Phase 7 complete: 31-RC batch hardening (RC_Training_Data_170to200.csv)
- 199 tests passing
- Deployed to production (multiple commits pushed)

**Formats tested (Phase 3 + Phase 4 + Phase 5):**
- MH (Maharashtra) physical RC smart card — front/back ✓ robust
- GJ (Gujarat) RC smart card — partially working (garbled OCR in some images)
- KA (Karnataka) old paper booklet — back fields extracted; front too garbled
- PB (Punjab) mParivahan virtual RC — 4/4 front ✓
- MP (Madhya Pradesh) RC — partial (reg number only on back)
- mParivahan digital RC (MH) — partial (fuel/date not on front side)
- UP (Uttar Pradesh) paper RC — partial (garbled OCR, "OwName"/"Ownrf" label typos)
- TN (Tamil Nadu) RC smart card — ✓ (qwner name alias)
- HR (Haryana) paper RC — very garbled; reg number only
- WB (West Bengal) RC smart card — ✓ front+back
- HONDA format RC (GJ) — ✓

**Score on 51-RC batch (RC_Training_Data_99to150.csv):**
- ~23/51 RCs: both front+back fully passing
- ~5/51 RCs: data issues (swapped sides, empty/blank images)
- ~8/51 RCs: OCR quality too poor (HR/UP/KA paper, severely garbled images)
- ~15/51 RCs: partial extraction (format limitations, OCR truncation, merged labels+values)

**Known limitations:**
- PaddleOCR merges words without spaces — OCR engine limitation
- OCR sometimes merges adjacent label columns — causes extraction failures
- mParivahan digital RC: fuel_type/registration_date only on "back" URL, not front
- MH back: engine/chassis not in back OCR (they're on front) — BACK_MANDATORY reduced to 2
- Garbled UP/KA/HR paper RCs: OCR output too noisy to extract reliably
- `vehicle_make` missing when "Maker's Name" label absent from OCR output (garbled images)
- UP paper RC fuel_type often absent from OCR output (not extractable)
- OCR 'O'→'0' digit confusion in reg numbers (e.g. "GJO1MT0859") — fails state code validation
- Dates merged with reg numbers on same OCR line — unfixable without risking false positives

---

## Changelog

### 2026-03-12 — RC SmartExtract: 31-RC Batch Hardening (Phase 7)

**What happened:** Iterated through 31 new RC images (RC_Training_Data_170to200.csv) in 6 batches. Each batch: hit production API → analyze raw OCR → fix mapper → push → redeploy → verify.

**Score: 8/31 (26%) both passing** — Front avg: 2.65/4 (66%), Back avg: 1.13/2 (57%)

**Commits:**
- `9e97375` — Fuel garble variants (TETROUCNG/PETRQUCNG/PEROLCNG), "fu." label alias, mokor/haxer/atsker vehicle_make aliases

**New format support:**
- "Fu." as fuel label (very short garbled GJ format label)
- TETROUCNG/TETROLICNG (OCR 'T' for 'P'), PETRQUCNG (OCR 'Q' for 'O'), PEROLCNG (OCR drops 'T') fuel normalizations
- "mokor's name/namo" (OCR 'o' for 'a' in "Makor"), "haxer's hame/name/namo", "haxer." (OCR 'H' for 'M'), "atsker name" (mParivahan garble) vehicle_make aliases
- RJ (Rajasthan) RC format confirmed working
- UK (Uttarakhand) paper RC format — reg number extractable

**Failure analysis:**
- ~6/31: blank or severely garbled images (RC02, RC04, RC07, RC10, RC22 front)
- ~5/31: UP/CG paper RCs — reg numbers garbled beyond repair
- ~8/31: blank/missing back images
- ~4/31: fuel_type absent from raw OCR (label present, no adjacent value)

### 2026-03-12 — RC SmartExtract: 20-RC Batch Hardening (Phase 6)

**What happened:** Iterated through 20 new RC images (RC_Training_Data_150to170.csv) in 4 batches. Each batch: hit production API → analyze raw OCR → fix mapper → push → redeploy → verify.

**Score: 4/20 (20%) both passing** — tougher dataset with more garbled/paper RCs
- Front avg: 2.45/4 (61%), Back avg: 1.20/2 (60%)

**Commits:**
- `867a13b` — Batch 1-2: maxer's namo alias, OCR-normalized reg rejection for vehicle_make (O→0, S→5 substitution catches garbled reg numbers like "GJO1MT40S5")
- `60c10d5` — Batch 3-4: RETROLCNG/RETROLICNG fuel normalization (OCR 'R' for 'P' in PETROL, GJ format), strip trailing punctuation from fuel value before normalization

**New format support:**
- GJ RC with "Maxer's Namo" (OCR 'x' for 'k') label
- RETROLCNG / RETROLICNG / RETROUCNG fuel variants (GJ format)

**Failure analysis:**
- ~5/20: blank or severely garbled images
- ~4/20: UP paper RCs (garbled reg numbers, "P78LN3638" — state code unrecognizable)
- ~4/20: fuel_type absent from raw OCR output (label present but no value)
- ~3/20: OCR multi-char substitutions in reg numbers (TN91ATOT10 — O+T substitutions)

### 2026-03-12 — RC SmartExtract: 51-RC Batch Hardening (Phase 5)

**What happened:** Iterated through 51 new RC images (RC_Training_Data_99to150.csv) in 11 batches of 5. Each batch: hit production API → analyze raw OCR → fix mapper → push → redeploy → verify.

**Commits:**
- `d4d1c1a` — Batch 1-6: fuel typo aliases (ftel/fues/fue), owier owner alias, digit-prefix vehicle_make guard, ownernarne/ownor owner aliases, cardissue/bharat label guards, makor vehicle alias, vohick/vohide label guards, laker/slash-maker vehicle aliases, keg/setial label guards, vhic label guard, TG state code, regd.owner alias, dot-date pattern, PETROLONG fuel, flnancer label guard
- `c6db555` — Batch 7: makers-name alias (no apostrophe), dot-prefix digit guard for vehicle_make

**New format support added:**
- HR (Haryana) paper RC — reg number extractable; other fields too garbled
- WB (West Bengal) RC smart card — front+back working
- GJ RC with "Makers Name;" (no apostrophe) label format
- Dot-separator dates (DD.MM.YYYY)
- TG (Telangana) state code validation
- "regd. owner" / "regd owner" aliases for TG/AP formats

**Score summary:**
- RC1-5: ~3 fully passing
- RC6-10: ~3 passing
- RC11-15: ~3 passing
- RC16-20: ~3 passing
- RC21-25: ~4 passing
- RC26-30: ~3 passing
- RC31-35: ~4 passing (RC34 improved with ownerna alias)
- RC36-40: ~1 fully passing (RC38 ✓; RC39-40 UP/HR garbled)
- RC41-45: ~1 fully passing (RC42 ✓; RC43/45 garbled)
- RC46-50: ~3 fully passing (RC46/48/49 ✓)
- RC51: 0 (garbled GJ RC with merged dates)

**Data quality observations:**
- ~8/51 severely garbled (HR/UP paper RCs, some GJ)
- ~5/51 data issues (blank images, inverted layouts)
- OCR 'O'→'0' confusion causes reg number extraction failures on some GJ RCs

### 2026-03-12 — RC SmartExtract: 40-RC Batch Hardening (Phase 4)

**What happened:** Iterated through 40 new RC images (RC_Training_Data_40to99.csv) in 8 batches of 5. Each batch: hit production API → analyze raw OCR → fix mapper → push → redeploy → verify.

**Commits:**
- `8974067` — Batch 5+6: qwner-name (TN format Q→O), PETRQL fuel, semicolon/colon strip, dateofregn alias, ownernamr label guard, `_STRICT_DATE_PATTERN`, VIN min length 15, `Scp` month alias, multi-word vehicle_make score bonus, word boundary guard `(?!\w)` for owner alias
- `dd5a697` — Batch 7: gross/weight label guards (prevents vehicle_make capturing "Gross Combination Weight"), ownrf owner_name alias (UP paper RC)
- `f7dc039` — Batch 8: owname alias for UP format OCR-merged "OwName" owner label

**New format support added:**
- UP (Uttar Pradesh) paper RC — "OwName", "Ownrf Name" label typos; highly garbled OCR
- TN (Tamil Nadu) RC — "qwner name" (Q→O OCR typo)
- GJ (Gujarat) RC improvements — PETRQL fuel typo

**Score summary:**
- RC1-5: 3/5 fully passing, 1 garbled, 1 partial
- RC6-10: 3/5 passing, 2 swapped/garbled
- RC11-15: 2/5 passing, 2 garbled, 1 swapped
- RC16-20: 3/5 passing, 1 garbled, 1 data issue
- RC21-25: 4/5 fully passing, 1 partial
- RC26-30: 3/5 passing, 1 swapped, 1 garbled
- RC31-35: 4/5 passing (RC31F now 4/4 with ownrf fix), RC35 garbled
- RC36-40: 4/5 passing (RC36-38 all 4/4+2/2 ✓), RC39 garbled, RC40 3/4 front

**Data quality observations:**
- ~5/40 RCs had swapped or inaccessible images
- ~5/40 had severely garbled OCR (UP paper, old KA/GJ formats)
- UP paper RCs consistently extract owner but miss fuel_type (not in OCR output)

### 2026-03-12 — RC SmartExtract: 19-RC Batch Hardening (Phase 3)

**What happened:** Iterated through 19 new RC images (RC_Training_Data_20to40.csv) in 4 batches of 5. Each batch: hit production API → analyze raw OCR → fix mapper → push → redeploy → verify.

**6 commits of mapper fixes:**
- `80c943a` — Batch 1: MH format engine/chassis aliases (`engine / motor number`), Indian state code validation for reg numbers, `_NUMERIC_DECIMAL_FIELDS` validator, emission_norms validator, registration_validity accepts "As per Fitness", lookahead 3→5 lines, chassis ~ stripping
- `55bfd94` — Round 2: BACK_MANDATORY reduced to `[registration_number, vehicle_make]` (engine/chassis are on FRONT for MH/GJ), fallback reg number state code check, OCR typo "Registratln" label indicators
- `7b9fdb5` — Fix vehicle_make getting "Vehide Class" (OCR typo for Vehicle) in reversed-line mode
- `b5b78b6` — Fix vehicle_make greedy "make" alias causing "r's Name"; scoring penalizes short vehicle_make
- `fc5a907` — registration_validity: "As per Fitness" standalone line returns itself as value (MH format)
- `b3cd6c3` — Batch 3: mParivahan digital RC + KA old paper format aliases; DD-Mon-YYYY date format; owner_name label guards

**New format support added:**
- MH (Maharashtra) physical RC — `Engine / Motor Number` (spaces around `/`)
- mParivahan digital RC — `Vehicle Number`, `Maker Name`, `Engine No.`, `Registration Date`
- KA old paper booklet — `MFR`, `Rec.Date`, `Fuel`
- Punjab virtual RC — `Registratlon Date`, `15-Jan-2026` date format
- MP (Madhya Pradesh) — `PETROLICNG` normalization, `Makor's Namo` typo

**Data quality observations from batch:**
- 3/19 RCs had CSV front/back URLs swapped (RC6, RC8, RC15)
- 1/19 was a tax receipt, not RC book (RC17)
- 2/19 had inaccessible/empty images (RC2, RC7)
- 3/19 had severely garbled OCR (RC1 UP paper, RC14 KA paper, RC19 GJ garbled)

### 2026-03-11 — RC SmartExtract: Live Hardening (Phase 2)

**What happened:** Tested deployed API with real Gujarat RC smart card images. Discovered format differences and PaddleOCR noise issues. Two rounds of fixes.

**Round 1 — Field reclassification (`8be53fb`):**
- Discovered vehicle_make/model/color/seating are on BACK of Indian RC smart cards (not front as modeled)
- Moved these fields from FRONT to BACK aliases
- Added next-line extraction pattern (OCR outputs label on one line, value on next)
- Added Gujarat-specific aliases (engine/motor no, regn. number, etc.)
- Added `_is_label_text()` to prevent false matches
- Added Gujarat format tests with real OCR output

**Round 2 — OCR noise tolerance (`382b77d`):**
- Moved engine_number/chassis_number to COMMON fields (Gujarat has them on FRONT, other states on BACK)
- Added registration number regex fallback (`_fallback_registration_number`)
- Added fuel type fallback for unlabeled PETROL/DIESEL/CNG lines (`_fallback_fuel_type`)
- Added OCR-typo aliases: regr, namo, registralion, cublc, gapacity, etc.
- Enhanced next-line extraction: looks ahead up to 3 lines, skips blanks and descriptors
- Added `_is_label_or_descriptor()`: rejects parenthetical text like "(In case of Individual Owner)"
- Same-line rejection now cascades to next-line extraction
- Added 9 new test cases (real PaddleOCR output, fallbacks, OCR typos)
- 191 total tests passing

**Test images used:**
- Front: `https://oneway-live-new.s3.ap-south-1.amazonaws.com/driver/2141441773138848871.jpg`
- Back: `https://oneway-live-new.s3.ap-south-1.amazonaws.com/driver/3075231773138848954.jpg`

### 2026-03-11 — RC SmartExtract: Implementation (Phase 1)

**Goal:** Build RC book extraction with front/back support, image quality, document authenticity, and multi-engine comparison.

**Design decisions:**
- Front/back are separate API calls; client merges using `registration_number` (common to both sides)
- `side` parameter added to `ExtractionRequest` — "front", "back", or null (auto-detect)
- Image quality: Layer A (pre-OCR: blur, brightness, resolution) + Layer B (post-OCR: mandatory field completeness)
- Document authenticity: structural checks (critical, pass/fail) + visual checks (confidence-only, OpenCV)
- Multi-engine comparison via `/compare/rc-book` endpoint for testing phase
- All new response fields optional — backward compatible

**Front mandatory fields (4):** registration_number, owner_name, fuel_type, registration_date
**Back mandatory fields (4):** registration_number, vehicle_make, engine_number, chassis_number

**Commits:**
- `5fcaff5` — Design spec
- `35e605e` — Implementation plan
- `dc6d12b` — Task 1: BaseMapper `side` parameter + all 7 mappers
- `0599840` — Task 2: RC mapper tests (TDD red)
- `927874b` — Task 3: RC mapper front/back implementation (green)
- `2d77997` — Tasks 4+6: Image quality + doc auth tests (red)
- `0825c7d` — Tasks 5+7: Quality + auth implementations (green)
- `c2170fb` — Tasks 8+11: Integration + N-engine tests (red)
- `8619310` — Tasks 9+10: Schemas + pipeline integration (green)
- `0f3dba6` — Task 12: N-engine comparator
- `5bc1d3a` — Task 13: `/compare/rc-book` endpoint
- `a27e8ab` — Fix: alias ordering bug
- `8be53fb` — Phase 2: Gujarat RC format reclassification
- `382b77d` — Phase 2: OCR noise tolerance + fallbacks

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
- **Remotes:** `github` (kvivek1983/ocr2text) + `bitbucket` (ez_onewaycab/orc2text)

---

## Discussion Notes

### RC Book Format Observations
- Indian RC books come as smart cards (credit card sized) or older paper booklets
- Each state has 2-3 RC formats with different label text
- Smart card aspect ratio: ~1.586:1 (85.6mm x 54mm)
- Smart cards have characteristic blue/green header bands
- `registration_number` appears on both front and back — natural merge key
- Older paper RCs will pass structural authenticity but fail visual checks (by design)
- **Gujarat RC front** has chassis/engine numbers (other states have them on back)
- **PaddleOCR** merges words without spaces on some images — engine limitation

### Per-State RC Format Strategy
- **Current approach:** Single mapper with broad alias lists handles all state variations
- **Why it works:** Field labels across states are variations of the same terms (different abbreviations/ordering)
- **When to add state-specific logic:** If two states use the same label for different fields, or layouts are radically incompatible
- **Accumulation strategy:** Test with images from each state, add aliases as discovered
- **States tested:** GJ (Gujarat), KA (Karnataka — fixture data)
- **States pending:** MH, TN, DL, AP, UP, RJ, MP, etc.

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
| POST | `/compare/rc-book` | Multi-engine RC book comparison |

---

## Testing

- **Framework:** pytest + pytest-asyncio + pytest-cov
- **Current count:** 191 tests passing
- **Run:** `python3 -m pytest tests/ -v --tb=short`
- **Live testing:** `curl -X POST https://ocr2text-production.up.railway.app/extract/rc-book -H "Content-Type: application/json" -d '{"image_url": "<URL>", "side": "front"}'`
