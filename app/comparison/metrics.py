from typing import Dict, List, Union, Optional
from app.utils.text_utils import normalize_amount


def calculate_comparison_metrics(
    engine_fields_or_first: Union[Dict[str, List[Dict[str, str]]], List[Dict[str, str]]],
    second_fields: Optional[List[Dict[str, str]]] = None,
) -> Dict:
    """Calculate comparison metrics across N engines.

    New API:
        calculate_comparison_metrics({"engine_a": [...], "engine_b": [...]})

    Legacy API (backward compatible):
        calculate_comparison_metrics(paddle_fields, google_fields)
    """
    # Handle legacy 2-argument call
    if second_fields is not None or isinstance(engine_fields_or_first, list):
        return _legacy_metrics(engine_fields_or_first, second_fields or [])

    # New N-engine API: engine_fields_or_first is Dict[str, List[Dict]]
    engine_fields = engine_fields_or_first
    return _n_engine_metrics(engine_fields)


def _n_engine_metrics(engine_fields: Dict[str, List[Dict[str, str]]]) -> Dict:
    """Calculate metrics for N engines."""
    engine_names = list(engine_fields.keys())

    # Build per-engine dicts: engine_name -> {label: value}
    engine_dicts = {}
    for name, fields in engine_fields.items():
        engine_dicts[name] = {f["label"]: f["value"] for f in fields}

    # Collect the union of all labels across all engines
    all_labels = set()
    for d in engine_dicts.values():
        all_labels.update(d.keys())

    total_fields = len(all_labels)
    field_agreement = {}
    full_agreement_count = 0
    partial_agreement_count = 0

    for label in sorted(all_labels):
        # Collect values from each engine for this label
        values = {}
        for name in engine_names:
            val = engine_dicts[name].get(label)
            if val is not None:
                values[name] = val

        # Determine agreement status
        if len(values) == 0:
            status = "disagreement"
        elif len(values) == 1:
            # Only one engine has this field
            if len(engine_names) == 1:
                status = "full"
                full_agreement_count += 1
            else:
                status = "disagreement"
        else:
            unique_values = set(values.values())
            if len(unique_values) == 1:
                # All engines that have this field agree exactly
                status = "full"
                full_agreement_count += 1
            elif _has_majority_agreement(list(values.values())):
                # Majority of engines agree (or partial text match)
                status = "partial"
                partial_agreement_count += 1
            elif _has_partial_match(list(values.values())):
                status = "partial"
                partial_agreement_count += 1
            else:
                status = "disagreement"

        field_agreement[label] = {
            "status": status,
            "values": values,
        }

    agreement_rate = (full_agreement_count + 0.5 * partial_agreement_count) / total_fields if total_fields > 0 else 1.0

    # Build engine_results
    engine_results = {}
    for name, fields in engine_fields.items():
        engine_results[name] = fields

    return {
        "agreement_rate": agreement_rate,
        "total_fields": total_fields,
        "field_agreement": field_agreement,
        "engine_results": engine_results,
    }


def _has_majority_agreement(values: List[str]) -> bool:
    """Check if a majority of values agree (more than half share the same value)."""
    if len(values) <= 1:
        return False
    from collections import Counter
    counts = Counter(values)
    most_common_count = counts.most_common(1)[0][1]
    # Majority means more than one engine agrees and it's the dominant group
    return most_common_count > 1 and most_common_count < len(values)


def _has_partial_match(values: List[str]) -> bool:
    """Check if any pair of values has a partial match."""
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if _is_partial_match(values[i], values[j]):
                return True
    return False


def _legacy_metrics(
    paddle_fields: List[Dict[str, str]],
    google_fields: List[Dict[str, str]],
) -> Dict:
    """Original 2-engine metrics (backward compatible)."""
    paddle_dict = {f["label"]: f["value"] for f in paddle_fields}
    google_dict = {f["label"]: f["value"] for f in google_fields}
    all_labels = set(paddle_dict.keys()) | set(google_dict.keys())

    exact_match = 0
    partial_match = 0
    mismatch = 0
    paddle_only = 0
    google_only = 0
    field_comparison = {}

    for label in all_labels:
        p_val = paddle_dict.get(label)
        g_val = google_dict.get(label)

        if p_val and g_val:
            if p_val == g_val:
                exact_match += 1
                field_comparison[label] = {"paddle": p_val, "google": g_val, "status": "match"}
            elif _is_partial_match(p_val, g_val):
                partial_match += 1
                field_comparison[label] = {"paddle": p_val, "google": g_val, "status": "partial"}
            else:
                mismatch += 1
                field_comparison[label] = {"paddle": p_val, "google": g_val, "status": "mismatch"}
        elif p_val and not g_val:
            paddle_only += 1
            field_comparison[label] = {"paddle": p_val, "google": None, "status": "paddle_only"}
        else:
            google_only += 1
            field_comparison[label] = {"paddle": None, "google": g_val, "status": "google_only"}

    total = len(all_labels)
    score = (exact_match + 0.5 * partial_match) / total if total > 0 else 0.0

    return {
        "total_fields": total,
        "exact_match": exact_match,
        "partial_match": partial_match,
        "mismatch": mismatch,
        "paddle_only": paddle_only,
        "google_only": google_only,
        "score": round(score, 2),
        "field_comparison": field_comparison,
    }


def _is_partial_match(val1: str, val2: str) -> bool:
    n1 = normalize_amount(val1)
    n2 = normalize_amount(val2)
    if n1 and n2 and n1 == n2:
        return True
    return val1.lower().strip() in val2.lower().strip() or val2.lower().strip() in val1.lower().strip()
