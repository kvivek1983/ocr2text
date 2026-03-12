#!/usr/bin/env python3
"""
analyze_results.py — Summarize scan_and_track results

Usage:
    python3 scripts/analyze_results.py
    python3 scripts/analyze_results.py --file scan_results.csv
"""

import argparse
import csv
from collections import Counter, defaultdict

DEFAULT_FILE = "scan_results.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args()

    rows = []
    with open(args.file) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No results found.")
        return

    total = len(rows)
    accepted = [r for r in rows if r["bucket_accepted"] == "True"]
    both_passing = [r for r in rows if r["both_passing"] == "True"]
    front_errors = [r for r in rows if r["front_error"]]
    back_errors = [r for r in rows if r["back_error"]]

    print(f"\n{'═' * 55}")
    print(f"  RC Scan Summary — {total} pairs processed")
    print(f"{'═' * 55}")
    print(f"  Accepted into buckets : {len(accepted)}")
    print(f"  Both sides passing    : {len(both_passing)} ({100*len(both_passing)//total}%)")
    print(f"  Front errors          : {len(front_errors)}")
    print(f"  Back errors           : {len(back_errors)}")

    # Pass rate by state
    print(f"\n── Pass rate by state ──────────────────────────────")
    state_total = Counter(r["state"] for r in rows)
    state_pass = Counter(r["state"] for r in rows if r["both_passing"] == "True")
    for state, total_count in sorted(state_total.items(), key=lambda x: -x[1]):
        passing = state_pass.get(state, 0)
        pct = 100 * passing // total_count if total_count else 0
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"  {state:<6} {bar} {passing}/{total_count} ({pct}%)")

    # Most common missing fields
    print(f"\n── Most common missing fields ──────────────────────")
    front_missing_counter = Counter()
    back_missing_counter = Counter()
    for r in rows:
        for f in r["front_missing"].split("|"):
            if f:
                front_missing_counter[f] += 1
        for f in r["back_missing"].split("|"):
            if f:
                back_missing_counter[f] += 1

    print("  Front:")
    for field, count in front_missing_counter.most_common(5):
        print(f"    {field:<30} {count} ({100*count//total}%)")
    print("  Back:")
    for field, count in back_missing_counter.most_common(5):
        print(f"    {field:<30} {count} ({100*count//total}%)")

    # Bucket fill status
    print(f"\n── Bucket fill status ──────────────────────────────")
    bucket_counts = Counter(r["state"] for r in accepted)
    for state, count in sorted(bucket_counts.items()):
        print(f"  {state:<8} {count}")

    print(f"\n{'═' * 55}\n")


if __name__ == "__main__":
    main()
