#!/usr/bin/env python3
"""
scan_and_track.py — Stratified RC image scanner

Reads one or more CSV files (Front RC URL, Back RC URL),
hits the /extract/rc-book API for each image, detects state from
registration_number, fills coverage buckets (100 per state/format),
and saves results + progress so runs can be resumed.

Usage:
    python3 scripts/scan_and_track.py --csv ~/Downloads/RC_Training_Data_*.csv
    python3 scripts/scan_and_track.py --csv ~/Downloads/RC_Training_Data_170to200.csv --bucket-size 50
    python3 scripts/scan_and_track.py --csv ... --resume   # resume from last checkpoint
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE = "https://ocr2text-production.up.railway.app"
RESULTS_FILE = "scan_results.csv"
PROGRESS_FILE = "scan_progress.json"
DEFAULT_BUCKET_SIZE = 100
REQUEST_TIMEOUT = 30
DELAY_BETWEEN_REQUESTS = 0.3  # seconds — be kind to the API

# State code → human label
STATE_LABELS = {
    "MH": "MH (Maharashtra)",
    "GJ": "GJ (Gujarat)",
    "KA": "KA (Karnataka)",
    "TN": "TN (Tamil Nadu)",
    "UP": "UP (Uttar Pradesh)",
    "HR": "HR (Haryana)",
    "RJ": "RJ (Rajasthan)",
    "PB": "PB (Punjab)",
    "MP": "MP (Madhya Pradesh)",
    "DL": "DL (Delhi)",
    "AP": "AP (Andhra Pradesh)",
    "TS": "TS/TG (Telangana)",
    "TG": "TS/TG (Telangana)",
    "WB": "WB (West Bengal)",
    "UK": "UK (Uttarakhand)",
    "CG": "CG (Chhattisgarh)",
    "OD": "OD (Odisha)",
    "BR": "BR (Bihar)",
    "JH": "JH (Jharkhand)",
    "HP": "HP (Himachal Pradesh)",
    "GA": "GA (Goa)",
    "KL": "KL (Kerala)",
}
OTHER_BUCKET = "OTHER"

FRONT_MANDATORY = {"registration_number", "owner_name", "fuel_type", "registration_date"}
BACK_MANDATORY = {"registration_number", "vehicle_make"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_state(reg_number: str) -> str:
    """Extract 2-letter state code from registration number."""
    if not reg_number:
        return OTHER_BUCKET
    m = re.match(r"^([A-Z]{2})", reg_number.strip().upper())
    if m:
        code = m.group(1)
        return code if code in STATE_LABELS else OTHER_BUCKET
    return OTHER_BUCKET


def bucket_key(state_code: str) -> str:
    """Normalise TG→TS for bucketing."""
    return "TS" if state_code == "TG" else state_code


def extract_side(image_url: str, side: str, row_index: int) -> dict:
    """Call /extract/rc-book and return parsed result."""
    try:
        resp = httpx.post(
            f"{API_BASE}/extract/rc-book",
            json={"image_url": image_url, "side": side, "include_raw_text": False},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"success": False, "fields": [], "image_quality": None, "error": str(e)}


def score_fields(result: dict, mandatory: set) -> tuple[int, list[str]]:
    """Return (count_extracted, missing_mandatory_list)."""
    extracted = {f["label"] for f in result.get("fields", [])}
    missing = sorted(mandatory - extracted)
    return len(mandatory) - len(missing), missing


def load_progress(resume: bool) -> dict:
    if resume and os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed_rows": 0, "buckets": {}, "total_scanned": 0}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def print_bucket_status(buckets: dict, bucket_size: int):
    print("\n── Coverage status ─────────────────────────────────────")
    all_codes = sorted(set(list(STATE_LABELS.keys()) + [OTHER_BUCKET]))
    seen = set()
    for code in all_codes:
        key = bucket_key(code)
        if key in seen:
            continue
        seen.add(key)
        count = buckets.get(key, 0)
        label = STATE_LABELS.get(key, STATE_LABELS.get(code, key))
        bar = "█" * min(count, bucket_size) + "░" * max(0, bucket_size - count)
        status = "✓ FULL" if count >= bucket_size else f"{count}/{bucket_size}"
        print(f"  {label:<28} {bar[:20]} {status}")
    total = sum(buckets.values())
    full = sum(1 for v in buckets.values() if v >= bucket_size)
    print(f"\n  Total accepted: {total} | Full buckets: {full}/{len(buckets) or '?'}")
    print("─" * 57)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stratified RC image scanner")
    parser.add_argument("--csv", nargs="+", required=True, help="CSV file(s) to process")
    parser.add_argument("--bucket-size", type=int, default=DEFAULT_BUCKET_SIZE)
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--api", default=API_BASE, help="API base URL")
    args = parser.parse_args()

    global API_BASE
    API_BASE = args.api.rstrip("/")

    # Load all rows from all CSVs
    all_rows = []
    for csv_path in args.csv:
        path = Path(csv_path).expanduser()
        if not path.exists():
            print(f"Warning: {path} not found, skipping")
            continue
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                front = row.get("Front RC URL", "").strip()
                back = row.get("Back RC URL", "").strip()
                if front and back:
                    all_rows.append((front, back, str(path.name)))
    print(f"Loaded {len(all_rows)} RC pairs from {len(args.csv)} file(s)")

    # Load progress
    progress = load_progress(args.resume)
    start_row = progress["processed_rows"]
    buckets = progress["buckets"]

    if start_row > 0:
        print(f"Resuming from row {start_row}")

    # Open results CSV (append if resuming)
    results_mode = "a" if args.resume and os.path.exists(RESULTS_FILE) else "w"
    results_f = open(RESULTS_FILE, results_mode, newline="")
    writer = csv.writer(results_f)
    if results_mode == "w":
        writer.writerow([
            "row_index", "source_file", "state", "bucket_accepted",
            "front_url", "back_url",
            "reg_number", "owner_name", "fuel_type", "registration_date", "vehicle_make",
            "front_score", "front_missing", "front_quality_score", "front_acceptable",
            "back_score", "back_missing", "back_quality_score", "back_acceptable",
            "both_passing", "front_error", "back_error",
            "scanned_at",
        ])

    print(f"\nBucket size: {args.bucket_size} per state")
    print(f"Scanning rows {start_row + 1} to {len(all_rows)}...\n")

    try:
        for i, (front_url, back_url, source_file) in enumerate(all_rows[start_row:], start=start_row):
            row_num = i + 1

            # ── Front ──
            front_result = extract_side(front_url, "front", i)
            time.sleep(DELAY_BETWEEN_REQUESTS)

            # ── Back ──
            back_result = extract_side(back_url, "back", i)
            time.sleep(DELAY_BETWEEN_REQUESTS)

            # ── Parse fields ──
            front_fields = {f["label"]: f["value"] for f in front_result.get("fields", [])}
            back_fields = {f["label"]: f["value"] for f in back_result.get("fields", [])}
            all_fields = {**back_fields, **front_fields}  # front takes precedence

            reg_number = all_fields.get("registration_number", "")
            state = detect_state(reg_number)
            bkey = bucket_key(state)

            front_score, front_missing = score_fields(front_result, FRONT_MANDATORY)
            back_score, back_missing = score_fields(back_result, BACK_MANDATORY)
            both_passing = front_score == len(FRONT_MANDATORY) and back_score == len(BACK_MANDATORY)

            fiq = front_result.get("image_quality") or {}
            biq = back_result.get("image_quality") or {}

            # ── Bucket logic ──
            bucket_count = buckets.get(bkey, 0)
            accepted = bucket_count < args.bucket_size
            if accepted:
                buckets[bkey] = bucket_count + 1

            # ── Write result ──
            writer.writerow([
                row_num, source_file, state, accepted,
                front_url, back_url,
                reg_number,
                all_fields.get("owner_name", ""),
                all_fields.get("fuel_type", ""),
                all_fields.get("registration_date", ""),
                all_fields.get("vehicle_make", ""),
                front_score, "|".join(front_missing),
                fiq.get("overall_score", ""), fiq.get("is_acceptable", ""),
                back_score, "|".join(back_missing),
                biq.get("overall_score", ""), biq.get("is_acceptable", ""),
                both_passing,
                front_result.get("error", ""),
                back_result.get("error", ""),
                datetime.utcnow().isoformat(),
            ])
            results_f.flush()

            # ── Progress save every 10 rows ──
            progress["processed_rows"] = i + 1
            progress["buckets"] = buckets
            progress["total_scanned"] = progress.get("total_scanned", 0) + 1
            if (i + 1) % 10 == 0:
                save_progress(progress)
                print_bucket_status(buckets, args.bucket_size)
                print(f"  Row {row_num}/{len(all_rows)} | Both passing: {both_passing} | State: {state} ({reg_number})")

            # ── Check if all buckets full ──
            all_full = all(buckets.get(bucket_key(s), 0) >= args.bucket_size for s in STATE_LABELS)
            if all_full:
                print("\n✓ All buckets full — scan complete!")
                break

    except KeyboardInterrupt:
        print("\nInterrupted — progress saved.")

    finally:
        save_progress(progress)
        results_f.close()
        print_bucket_status(buckets, args.bucket_size)
        print(f"\nResults saved to: {RESULTS_FILE}")
        print(f"Progress saved to: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()
