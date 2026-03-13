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

# All Indian state/UT codes → human label
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
    "TS": "TS (Telangana)",
    "TG": "TG (Telangana old)",
    "WB": "WB (West Bengal)",
    "UK": "UK (Uttarakhand)",
    "CG": "CG (Chhattisgarh)",
    "OD": "OD (Odisha)",
    "OR": "OR (Odisha old)",
    "BR": "BR (Bihar)",
    "JH": "JH (Jharkhand)",
    "HP": "HP (Himachal Pradesh)",
    "GA": "GA (Goa)",
    "KL": "KL (Kerala)",
    "AS": "AS (Assam)",
    "NL": "NL (Nagaland)",
    "MN": "MN (Manipur)",
    "ML": "ML (Meghalaya)",
    "TR": "TR (Tripura)",
    "MZ": "MZ (Mizoram)",
    "SK": "SK (Sikkim)",
    "AR": "AR (Arunachal Pradesh)",
    "JK": "JK (Jammu & Kashmir)",
    "LA": "LA (Ladakh)",
    "CH": "CH (Chandigarh)",
    "PY": "PY (Puducherry)",
    "AN": "AN (Andaman & Nicobar)",
    "DN": "DN (Dadra & Nagar Haveli)",
    "DD": "DD (Daman & Diu)",
    "LD": "LD (Lakshadweep)",
    "BH": "BH (Bharat series)",
}
UNREADABLE_BUCKET = "UNREADABLE"

FRONT_MANDATORY = {"registration_number", "owner_name", "fuel_type", "registration_date"}
BACK_MANDATORY = {"registration_number", "vehicle_make"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_state(reg_number: str) -> str:
    """Extract 2-letter state code from registration number."""
    if not reg_number:
        return UNREADABLE_BUCKET
    m = re.match(r"^([A-Z]{2})", reg_number.strip().upper())
    if m:
        code = m.group(1)
        return code if code in STATE_LABELS else UNREADABLE_BUCKET
    return UNREADABLE_BUCKET


def bucket_key(state_code: str) -> str:
    return state_code


_api_base = API_BASE


def extract_side(image_url: str, side: str, row_index: int) -> dict:
    """Call /extract/rc-book and return parsed result."""
    try:
        resp = httpx.post(
            f"{_api_base}/extract/rc-book",
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
    named = sorted((k, v) for k, v in buckets.items() if k != UNREADABLE_BUCKET)
    unreadable = buckets.get(UNREADABLE_BUCKET, 0)
    for key, count in named:
        label = STATE_LABELS.get(key, key)
        filled = min(count * 20 // max(bucket_size, 1), 20)
        bar = "█" * filled + "░" * (20 - filled)
        status = "✓ FULL" if count >= bucket_size else f"{count}/{bucket_size}"
        print(f"  {label:<32} {bar} {status}")
    if unreadable:
        filled = min(unreadable * 20 // max(bucket_size, 1), 20)
        bar = "█" * filled + "░" * (20 - filled)
        status = "✓ FULL" if unreadable >= bucket_size else f"{unreadable}/{bucket_size}"
        print(f"  {'UNREADABLE (no reg detected)':<32} {bar} {status}")
    total = sum(buckets.values())
    full = sum(1 for v in buckets.values() if v >= bucket_size)
    print(f"\n  Total accepted: {total} | Full buckets: {full}/{len(buckets)}")
    print("─" * 57)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stratified RC image scanner")
    parser.add_argument("--csv", nargs="+", required=True, help="CSV file(s) to process")
    parser.add_argument("--bucket-size", type=int, default=DEFAULT_BUCKET_SIZE)
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--api", default=API_BASE, help="API base URL")
    args = parser.parse_args()

    global _api_base
    _api_base = args.api.rstrip("/")

    # Load all rows from all CSVs
    all_rows = []
    for csv_path in args.csv:
        path = Path(csv_path).expanduser()
        if not path.exists():
            print(f"Warning: {path} not found, skipping")
            continue
        with open(path) as f:
            reader = csv.reader(f)
            headers = [h.strip().lower() for h in next(reader)]

            # Format A: "Front RC URL", "Back RC URL" (training data)
            # Format B: driver_id, "front", front_url, "back", back_url (rc_book_urls)
            if "front rc url" in headers or "back rc url" in headers:
                # Format A
                front_idx = next((i for i, h in enumerate(headers) if "front" in h and "url" in h), None)
                back_idx = next((i for i, h in enumerate(headers) if "back" in h and "url" in h), None)
                driver_idx = None
            else:
                # Format B: driver_id, _, front_url, _, back_url
                driver_idx = 0
                front_idx = 2
                back_idx = 4

            for row in reader:
                if len(row) <= max(filter(None, [front_idx, back_idx])):
                    continue
                front = row[front_idx].strip() if front_idx is not None else ""
                back = row[back_idx].strip() if back_idx is not None else ""
                driver_id = row[driver_idx].strip() if driver_idx is not None else ""
                if front and back:
                    all_rows.append((front, back, str(path.name), driver_id))
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
            "row_index", "source_file", "driver_id", "state", "bucket_accepted",
            "front_url", "back_url",
            "reg_number", "owner_name", "fuel_type", "registration_date", "address",
            "vehicle_make", "chassis_number", "engine_number",
            "front_score", "front_missing", "front_quality_score", "front_acceptable",
            "back_score", "back_missing", "back_quality_score", "back_acceptable",
            "both_passing", "front_error", "back_error",
            "scanned_at",
        ])

    print(f"\nBucket size: {args.bucket_size} per state")
    print(f"Scanning rows {start_row + 1} to {len(all_rows)}...\n")

    try:
        for i, (front_url, back_url, source_file, driver_id) in enumerate(all_rows[start_row:], start=start_row):
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
                row_num, source_file, driver_id, state, accepted,
                front_url, back_url,
                reg_number,
                all_fields.get("owner_name", ""),
                all_fields.get("fuel_type", ""),
                all_fields.get("registration_date", ""),
                all_fields.get("address", ""),
                all_fields.get("vehicle_make", ""),
                all_fields.get("chassis_number", ""),
                all_fields.get("engine_number", ""),
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

            # ── Progress save + live update ──
            progress["processed_rows"] = i + 1
            progress["buckets"] = buckets
            progress["total_scanned"] = progress.get("total_scanned", 0) + 1

            if (i + 1) % 10 == 0:
                save_progress(progress)
                total_accepted = sum(buckets.values())
                full_count = sum(1 for v in buckets.values() if v >= args.bucket_size)
                passing_so_far = progress.get("passing_count", 0)
                top_buckets = " | ".join(
                    f"{k}:{v}" for k, v in sorted(buckets.items(), key=lambda x: -x[1])[:6]
                    if k != UNREADABLE_BUCKET
                )
                print(
                    f"  [{row_num}/{len(all_rows)}] "
                    f"accepted={total_accepted} full={full_count} "
                    f"pass={passing_so_far} | {top_buckets}"
                )

            if (i + 1) % 100 == 0:
                print_bucket_status(buckets, args.bucket_size)

            if both_passing:
                progress["passing_count"] = progress.get("passing_count", 0) + 1

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
