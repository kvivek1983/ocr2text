from typing import Dict, List
from app.utils.text_utils import normalize_amount


def calculate_comparison_metrics(
    paddle_fields: List[Dict[str, str]],
    google_fields: List[Dict[str, str]],
) -> Dict:
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
