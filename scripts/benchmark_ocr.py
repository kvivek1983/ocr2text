#!/usr/bin/env python3
"""
Benchmark OCR engines on real-world images.

Downloads images from S3, runs them through all available engines with
different preprocessing levels, and outputs a comparison report.

Usage:
    python scripts/benchmark_ocr.py                    # Run on default sample images
    python scripts/benchmark_ocr.py --url <image_url>  # Run on a single image
    python scripts/benchmark_ocr.py --file <path>      # Run on a local image file
    python scripts/benchmark_ocr.py --batch <csv_file>  # Run on a CSV of URLs
"""
import argparse
import csv
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.preprocessor import ImagePreprocessor
from app.utils.quality import assess_image_quality
from app.mappers.rc_book import RCBookMapper

# S3 base URL
S3_BASE = "https://oneway-live-new.s3.ap-south-1.amazonaws.com"

# Default sample images (from the provided metadata)
SAMPLE_IMAGES = [
    # (id, front_path, back_path)
    ("sample_gj", "driver/00011500309049988.jpg", None),
    ("195945", "driver/2626341773146038779.jpg", "driver/2107721773146038815.jpg"),
    ("195944", "driver/9651601773145445231.jpg", "driver/4788481773145445292.jpg"),
    ("195943", "driver/7891741773143067910.jpg", "driver/6860911773143067955.jpg"),
    ("195940", "driver/2393931773141276868.jpg", "driver/8646271773141276924.jpg"),
    ("195939", "driver/7857511773141064473.jpg", "driver/7326481773141064537.jpg"),
    ("195938", "driver/4974791773140720823.jpg", "driver/948861773140720872.jpg"),
    ("195937", "driver/9735001773140174540.jpg", "driver/8479051773140177247.jpg"),
    ("195935", "driver/99961773139888926.jpg", "driver/20131773139888985.jpg"),
    ("195934", "driver/5884381773139604509.jpg", "driver/6031701773139604573.jpg"),
    ("195933", "driver/2141441773138848871.jpg", "driver/3075231773138848954.jpg"),
    ("195932", "driver/8946181773138511314.jpg", "driver/3681781773138511374.jpg"),
    ("195931", "driver/6405481773137633115.jpg", "driver/2047601773137633182.jpg"),
    ("195930", "driver/7626581773136726198.jpg", "driver/2458811773136726255.jpg"),
    ("195929", "driver/5497581773135996797.jpg", "driver/6591021773135995870.jpg"),
    ("195928", "driver/278461773135609171.jpg", "driver/2953061773135609235.jpg"),
    ("195927", "driver/2649881773135438089.jpg", "driver/665801773135437148.jpg"),
    ("195926", "driver/2987261773134070595.jpg", "driver/9461801773134070654.jpg"),
    ("195923", "driver/3096791773132585475.jpg", "driver/1346211773132585533.jpg"),
    ("195921", "driver/3803891773131947610.jpg", "driver/7733831773131947671.jpg"),
    ("195919", "driver/2865421773130681905.jpg", "driver/505081773130681948.jpg"),
    ("195918", "driver/2834461773129610192.jpg", "driver/6866921773129612045.jpg"),
    ("195917", "driver/5119331773129587088.jpg", "driver/2551371773129587170.jpg"),
]


# Preprocessing levels
PREPROCESS_LEVELS = {
    "raw": None,  # No preprocessing
    "grayscale_only": ["grayscale"],
    "grayscale_denoise": ["grayscale", "denoise"],
    "full_pipeline": ["grayscale", "denoise", "contrast", "threshold"],
}


class FlexiblePreprocessor:
    """Preprocessor that supports selectable pipeline steps."""

    def __init__(self):
        import cv2
        import numpy as np
        self.cv2 = cv2
        self.np = np

    def process(self, image_bytes: bytes, steps: Optional[List[str]] = None) -> bytes:
        if not steps:
            return image_bytes

        nparr = self.np.frombuffer(image_bytes, self.np.uint8)
        img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)

        for step in steps:
            if step == "grayscale":
                if len(img.shape) == 3:
                    img = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            elif step == "denoise":
                if len(img.shape) == 2:
                    img = self.cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
                else:
                    img = self.cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
            elif step == "contrast":
                if len(img.shape) == 2:
                    clahe = self.cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    img = clahe.apply(img)
                else:
                    lab = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2LAB)
                    clahe = self.cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                    img = self.cv2.cvtColor(lab, self.cv2.COLOR_LAB2BGR)
            elif step == "threshold":
                if len(img.shape) == 3:
                    img = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
                img = self.cv2.adaptiveThreshold(
                    img, 255, self.cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    self.cv2.THRESH_BINARY, 11, 2
                )

        _, buffer = self.cv2.imencode(".png", img)
        return buffer.tobytes()


def download_image(url: str) -> Optional[bytes]:
    """Download image from URL with retry."""
    for attempt in range(3):
        try:
            resp = httpx.get(url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  [FAIL] Could not download {url}: {e}")
                return None
    return None


def load_engines() -> Dict[str, Any]:
    """Load all available OCR engines."""
    engines = {}

    # Tesseract
    try:
        from app.engines.tesseract_engine import TesseractEngine
        engines["tesseract"] = TesseractEngine()
        print("  [OK] Tesseract loaded")
    except Exception as e:
        print(f"  [SKIP] Tesseract: {e}")

    # PaddleOCR
    try:
        from app.engines.paddle_engine import PaddleEngine
        engines["paddle"] = PaddleEngine()
        print("  [OK] PaddleOCR loaded")
    except Exception as e:
        print(f"  [SKIP] PaddleOCR: {e}")

    # EasyOCR
    try:
        from app.engines.easyocr_engine import EasyOCREngine
        engines["easyocr"] = EasyOCREngine()
        print("  [OK] EasyOCR loaded")
    except Exception as e:
        print(f"  [SKIP] EasyOCR: {e}")

    # Google Vision (requires credentials)
    try:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            from app.engines.google_engine import GoogleVisionEngine
            engines["google"] = GoogleVisionEngine()
            print("  [OK] Google Vision loaded")
        else:
            print("  [SKIP] Google Vision: no credentials")
    except Exception as e:
        print(f"  [SKIP] Google Vision: {e}")

    return engines


def detect_document_type(raw_text: str) -> Tuple[str, float]:
    """Simple document type detection from OCR text."""
    text_lower = raw_text.lower()

    # RC Book indicators
    rc_keywords = [
        "certificate of registration", "vehicle registration",
        "reg. no", "regn. number", "registration no",
        "chassis no", "engine no", "vehicle class",
        "owner name", "fuel used", "fuel type",
        "form 23a", "maker's name", "body type",
    ]
    rc_score = sum(1 for kw in rc_keywords if kw in text_lower)

    # Driving license indicators
    dl_keywords = [
        "driving licence", "driving license", "dl no",
        "blood group", "date of birth", "badge",
    ]
    dl_score = sum(1 for kw in dl_keywords if kw in text_lower)

    # Insurance indicators
    ins_keywords = [
        "insurance", "policy no", "premium", "insured",
        "third party", "comprehensive",
    ]
    ins_score = sum(1 for kw in ins_keywords if kw in text_lower)

    scores = {
        "rc_book": rc_score,
        "driving_license": dl_score,
        "insurance": ins_score,
        "unknown": 0,
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        return "unknown", 0.0

    return best_type, min(best_score / 5.0, 1.0)


def count_rc_fields(raw_text: str) -> Dict[str, Any]:
    """Run the RC mapper and count extracted fields."""
    mapper = RCBookMapper()
    fields = mapper.map_fields(raw_text)
    return {
        "field_count": len(fields),
        "fields": {f["label"]: f["value"] for f in fields},
    }


def benchmark_single_image(
    image_bytes: bytes,
    engines: Dict[str, Any],
    preprocessor: FlexiblePreprocessor,
    image_id: str = "",
    preprocess_levels: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Run all engine + preprocessing combos on a single image."""
    results = []
    levels = preprocess_levels or PREPROCESS_LEVELS

    # Assess raw image quality first
    quality = assess_image_quality(image_bytes)

    for preprocess_name, steps in levels.items():
        processed = preprocessor.process(image_bytes, steps)

        for engine_name, engine in engines.items():
            try:
                start = time.time()
                ocr_result = engine.extract(processed)
                elapsed = int((time.time() - start) * 1000)

                raw_text = ocr_result["raw_text"]
                confidence = ocr_result["confidence"]

                # Detect doc type
                doc_type, doc_confidence = detect_document_type(raw_text)

                # Count RC fields if applicable
                rc_fields = count_rc_fields(raw_text) if doc_type == "rc_book" else {}

                results.append({
                    "image_id": image_id,
                    "engine": engine_name,
                    "preprocessing": preprocess_name,
                    "image_quality_score": quality["score"],
                    "image_quality_issues": quality["issues"],
                    "ocr_confidence": round(confidence, 3),
                    "processing_time_ms": elapsed,
                    "raw_text_length": len(raw_text),
                    "raw_text_lines": len(raw_text.strip().split("\n")) if raw_text.strip() else 0,
                    "detected_doc_type": doc_type,
                    "doc_type_confidence": round(doc_confidence, 2),
                    "rc_field_count": rc_fields.get("field_count", 0),
                    "rc_fields": rc_fields.get("fields", {}),
                    "raw_text": raw_text[:2000],  # Truncate for report
                })

                status = "RC" if doc_type == "rc_book" else doc_type.upper()
                print(
                    f"    {engine_name:10s} + {preprocess_name:20s} | "
                    f"conf={confidence:.2f} | type={status:5s} | "
                    f"fields={rc_fields.get('field_count', '-'):>2} | "
                    f"{elapsed:>5d}ms"
                )

            except Exception as e:
                results.append({
                    "image_id": image_id,
                    "engine": engine_name,
                    "preprocessing": preprocess_name,
                    "error": str(e),
                })
                print(f"    {engine_name:10s} + {preprocess_name:20s} | ERROR: {e}")

    return results


def generate_report(all_results: List[Dict[str, Any]], output_path: str):
    """Generate a summary report from benchmark results."""
    # Save raw JSON
    json_path = output_path.replace(".txt", ".json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nRaw results saved to: {json_path}")

    # Generate summary
    with open(output_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("OCR BENCHMARK REPORT\n")
        f.write("=" * 80 + "\n\n")

        # Group by image
        images = {}
        for r in all_results:
            img_id = r.get("image_id", "unknown")
            images.setdefault(img_id, []).append(r)

        for img_id, results in images.items():
            f.write(f"\n{'─' * 60}\n")
            f.write(f"Image: {img_id}\n")
            f.write(f"{'─' * 60}\n")

            # Quality info from first result
            first = results[0]
            f.write(f"Image Quality Score: {first.get('image_quality_score', 'N/A')}\n")
            issues = first.get('image_quality_issues', [])
            if issues:
                f.write(f"Quality Issues: {'; '.join(issues)}\n")
            f.write("\n")

            f.write(f"{'Engine':<12} {'Preprocess':<22} {'Conf':>6} {'Type':<12} "
                    f"{'Fields':>6} {'Time':>7}\n")
            f.write("-" * 70 + "\n")

            for r in results:
                if "error" in r:
                    f.write(f"{r['engine']:<12} {r['preprocessing']:<22} ERROR: {r['error']}\n")
                    continue
                f.write(
                    f"{r['engine']:<12} {r['preprocessing']:<22} "
                    f"{r['ocr_confidence']:>5.2f} "
                    f"{r['detected_doc_type']:<12} "
                    f"{r['rc_field_count']:>6} "
                    f"{r['processing_time_ms']:>6}ms\n"
                )

            # Best combo for this image
            valid = [r for r in results if "error" not in r and r.get("rc_field_count", 0) > 0]
            if valid:
                best = max(valid, key=lambda r: (r["rc_field_count"], r["ocr_confidence"]))
                f.write(f"\n  BEST: {best['engine']} + {best['preprocessing']} "
                        f"({best['rc_field_count']} fields, {best['ocr_confidence']:.2f} conf)\n")
                if best.get("rc_fields"):
                    f.write("  Extracted fields:\n")
                    for label, value in best["rc_fields"].items():
                        f.write(f"    {label}: {value}\n")

        # Overall engine ranking
        f.write(f"\n\n{'=' * 80}\n")
        f.write("OVERALL ENGINE RANKING\n")
        f.write(f"{'=' * 80}\n\n")

        engine_stats: Dict[str, Dict] = {}
        for r in all_results:
            if "error" in r:
                continue
            key = f"{r['engine']} + {r['preprocessing']}"
            stats = engine_stats.setdefault(key, {
                "total_confidence": 0, "total_fields": 0,
                "total_time": 0, "count": 0, "rc_count": 0,
            })
            stats["total_confidence"] += r.get("ocr_confidence", 0)
            stats["total_fields"] += r.get("rc_field_count", 0)
            stats["total_time"] += r.get("processing_time_ms", 0)
            stats["count"] += 1
            if r.get("detected_doc_type") == "rc_book":
                stats["rc_count"] += 1

        ranked = sorted(
            engine_stats.items(),
            key=lambda x: (x[1]["total_fields"], x[1]["total_confidence"]),
            reverse=True,
        )

        f.write(f"{'Combo':<35} {'Avg Conf':>9} {'Avg Fields':>11} "
                f"{'RC Docs':>8} {'Avg Time':>9}\n")
        f.write("-" * 75 + "\n")
        for combo, stats in ranked:
            n = stats["count"]
            f.write(
                f"{combo:<35} "
                f"{stats['total_confidence']/n:>8.3f} "
                f"{stats['total_fields']/n:>10.1f} "
                f"{stats['rc_count']:>8} "
                f"{stats['total_time']//n:>8}ms\n"
            )

    print(f"Summary report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark OCR engines on real images")
    parser.add_argument("--url", help="Single image URL to test")
    parser.add_argument("--file", help="Local image file to test")
    parser.add_argument("--batch", help="CSV file with image URLs")
    parser.add_argument("--samples", type=int, default=0,
                        help="Number of sample images to test (0=all)")
    parser.add_argument("--engines", nargs="+",
                        help="Engines to test (default: all available)")
    parser.add_argument("--preprocess", nargs="+", choices=PREPROCESS_LEVELS.keys(),
                        help="Preprocessing levels (default: all)")
    parser.add_argument("--output", default="scripts/benchmark_report.txt",
                        help="Output report path")
    args = parser.parse_args()

    print("=" * 60)
    print("OCR Benchmark Tool")
    print("=" * 60)

    # Load engines
    print("\nLoading engines...")
    all_engines = load_engines()
    if args.engines:
        all_engines = {k: v for k, v in all_engines.items() if k in args.engines}
    if not all_engines:
        print("ERROR: No engines available!")
        sys.exit(1)

    preprocessor = FlexiblePreprocessor()

    # Filter preprocessing levels
    active_levels = dict(PREPROCESS_LEVELS)
    if args.preprocess:
        active_levels = {k: v for k, v in PREPROCESS_LEVELS.items() if k in args.preprocess}

    all_results = []

    if args.url:
        # Single URL mode
        print(f"\nDownloading: {args.url}")
        image_bytes = download_image(args.url)
        if image_bytes:
            results = benchmark_single_image(image_bytes, all_engines, preprocessor, "custom_url", active_levels)
            all_results.extend(results)

    elif args.file:
        # Local file mode
        print(f"\nLoading: {args.file}")
        with open(args.file, "rb") as f:
            image_bytes = f.read()
        results = benchmark_single_image(image_bytes, all_engines, preprocessor, args.file, active_levels)
        all_results.extend(results)

    elif args.batch:
        # CSV batch mode
        print(f"\nLoading batch from: {args.batch}")
        with open(args.batch) as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if len(row) >= 2:
                    img_id = row[0].strip().strip('"')
                    for path in row[1:]:
                        path = path.strip().strip('"')
                        if path:
                            url = f"{S3_BASE}/{path}"
                            print(f"\n  [{img_id}] {path}")
                            img_bytes = download_image(url)
                            if img_bytes:
                                results = benchmark_single_image(
                                    img_bytes, all_engines, preprocessor,
                                    f"{img_id}_{Path(path).stem}",
                                    active_levels,
                                )
                                all_results.extend(results)

    else:
        # Default: run on sample images
        samples = SAMPLE_IMAGES
        if args.samples > 0:
            samples = samples[:args.samples]

        print(f"\nRunning on {len(samples)} sample image sets...")
        for img_id, front_path, back_path in samples:
            for side, path in [("front", front_path), ("back", back_path)]:
                if not path:
                    continue
                url = f"{S3_BASE}/{path}"
                print(f"\n  [{img_id} {side}] {path}")
                img_bytes = download_image(url)
                if img_bytes:
                    results = benchmark_single_image(
                        img_bytes, all_engines, preprocessor,
                        f"{img_id}_{side}",
                        active_levels,
                    )
                    all_results.extend(results)

    if all_results:
        generate_report(all_results, args.output)
    else:
        print("\nNo results to report.")


if __name__ == "__main__":
    main()
