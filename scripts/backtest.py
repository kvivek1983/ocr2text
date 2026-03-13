"""
Backtest script: measure LLM extraction accuracy against govt truth data.

Usage: Run as script or trigger via /backtest/rc endpoint.
Queries records with govt verification, fetches image → OCR → LLM → compare vs govt truth.
"""
from typing import Dict, List, Any
from collections import defaultdict


def compute_accuracy_report(comparisons: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Compute per-field accuracy from a list of comparison results.

    Args:
        comparisons: List of dicts with keys: field_name, is_match, source

    Returns:
        Dict mapping field_name to {accuracy, total, matched} stats.
    """
    field_stats = defaultdict(lambda: {"matched": 0, "total": 0})

    for comp in comparisons:
        field = comp["field_name"]
        field_stats[field]["total"] += 1
        if comp["is_match"]:
            field_stats[field]["matched"] += 1

    report = {}
    for field, stats in field_stats.items():
        report[field] = {
            "accuracy": stats["matched"] / stats["total"] if stats["total"] > 0 else 0.0,
            "total": stats["total"],
            "matched": stats["matched"],
        }

    return report


def compute_overall_accuracy(report: Dict[str, Dict[str, Any]]) -> float:
    """Compute weighted overall accuracy across all fields."""
    total_matched = sum(v["matched"] for v in report.values())
    total_count = sum(v["total"] for v in report.values())
    return total_matched / total_count if total_count > 0 else 0.0
