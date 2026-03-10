"""Spatial text block mapper for multi-column document layouts.

Uses OCR bounding box coordinates to correctly pair labels with their
values, even when multiple label-value pairs share the same row
(e.g., Maharashtra RC books with 3-column layouts).
"""
import re
from typing import Dict, List, Optional, Tuple


# Type alias for an OCR block: {"text": str, "confidence": float, "bbox": [x1,y1,x2,y2]}
Block = Dict


def group_blocks_into_rows(
    blocks: List[Block],
    y_tolerance: float = 0.5,
) -> List[List[Block]]:
    """Group text blocks into rows based on Y-coordinate proximity.

    Args:
        blocks: OCR blocks with bbox [x1, y1, x2, y2].
        y_tolerance: Fraction of block height used as merge threshold.
            Two blocks are in the same row if their vertical midpoints
            are within y_tolerance * avg_height of each other.

    Returns:
        List of rows, each row being a list of blocks sorted left-to-right.
    """
    if not blocks:
        return []

    # Calculate vertical midpoint for each block
    items = []
    for b in blocks:
        bbox = b["bbox"]
        y_mid = (bbox[1] + bbox[3]) / 2.0
        height = bbox[3] - bbox[1]
        items.append({"block": b, "y_mid": y_mid, "height": max(height, 1)})

    # Filter out noise blocks (very low confidence or very large height
    # relative to others, like logo/emblem detections)
    heights = sorted(it["height"] for it in items)
    median_height = heights[len(heights) // 2]
    filtered = [
        it for it in items
        if it["height"] < median_height * 3 and it["block"].get("confidence", 1) > 0.1
    ]
    if not filtered:
        filtered = items

    # Sort by Y midpoint
    filtered.sort(key=lambda x: x["y_mid"])

    threshold = median_height * y_tolerance

    # Merge into rows using rolling average of Y midpoints
    rows: List[List[Block]] = []
    current_row_items = [filtered[0]]
    current_y_sum = filtered[0]["y_mid"]

    for it in filtered[1:]:
        row_y_avg = current_y_sum / len(current_row_items)
        if abs(it["y_mid"] - row_y_avg) <= threshold:
            current_row_items.append(it)
            current_y_sum += it["y_mid"]
        else:
            row_blocks = [ri["block"] for ri in current_row_items]
            row_blocks.sort(key=lambda b: b["bbox"][0])
            rows.append(row_blocks)
            current_row_items = [it]
            current_y_sum = it["y_mid"]

    if current_row_items:
        row_blocks = [ri["block"] for ri in current_row_items]
        row_blocks.sort(key=lambda b: b["bbox"][0])
        rows.append(row_blocks)

    return rows


def row_to_text(row: List[Block]) -> str:
    """Join blocks in a row into a single text string."""
    return " ".join(b["text"] for b in row)


def find_label_in_row(
    row_text: str,
    aliases: List[str],
) -> Optional[Tuple[str, int, int]]:
    """Check if a row contains a known label alias.

    Prefers longer (more specific) alias matches over shorter ones.

    Returns:
        (matched_alias, start_pos, end_pos) or None.
    """
    best: Optional[Tuple[str, int, int]] = None
    best_len = 0

    for alias in aliases:
        pattern = re.compile(
            rf"(?i)\b{re.escape(alias)}\.?\b",
        )
        match = pattern.search(row_text)
        if match and len(alias) > best_len:
            best = (alias, match.start(), match.end())
            best_len = len(alias)

    return best


def get_column_range(row: List[Block], alias_text: str) -> Tuple[float, float]:
    """Get the X-coordinate range of a label within a row.

    Finds the contiguous sequence of blocks that form the label text
    and returns their combined x1, x2 bounding range.
    """
    alias_words = [
        w for w in alias_text.lower().replace(".", "").replace("/", " ").split()
        if w  # Filter empty strings from double spaces
    ]
    if not alias_words:
        return row[0]["bbox"][0], row[-1]["bbox"][2]

    # Normalize block texts for matching (strip punctuation)
    block_words = [b["text"].lower().rstrip(".:,").lstrip("/") for b in row]

    # Sliding window: find the contiguous block sequence matching alias words
    best_match_start = None
    best_match_len = 0
    best_block_count = 0

    for start_idx in range(len(row)):
        matched = 0
        bi = start_idx
        for aw in alias_words:
            if bi >= len(row):
                break
            bw = block_words[bi]
            # Skip separator blocks like "/" that aren't real words
            if bw in ("", "/", "-", "|"):
                bi += 1
                if bi >= len(row):
                    break
                bw = block_words[bi]
            # Flexible matching
            if bw == aw or bw.startswith(aw) or aw.startswith(bw):
                matched += 1
                bi += 1
            else:
                break

        if matched > best_match_len:
            best_match_len = matched
            best_match_start = start_idx
            best_block_count = bi - start_idx

    if best_match_start is not None and best_match_len > 0:
        label_blocks = row[best_match_start:best_match_start + best_block_count]
        x1 = min(b["bbox"][0] for b in label_blocks)
        x2 = max(b["bbox"][2] for b in label_blocks)
        return x1, x2

    # Fallback: use the full row
    return row[0]["bbox"][0], row[-1]["bbox"][2]


def extract_value_from_row(
    value_row: List[Block],
    target_x1: float,
    target_x2: float,
    x_tolerance: float = 50.0,
) -> Optional[str]:
    """Extract value blocks from a row that align with a label's X range.

    Starts from blocks aligned with the label column, then includes
    contiguous blocks to the right (to capture multi-word values like
    "PATIL TOURS AND TRAVELS" under the "Owner Name" label).

    Args:
        value_row: Row of blocks to search for values.
        target_x1: Left edge of label column.
        target_x2: Right edge of label column.
        x_tolerance: Pixels of tolerance for column alignment.

    Returns:
        Extracted value text, or None if no blocks align.
    """
    # Find the first block that aligns with the label column
    start_idx = None
    for i, b in enumerate(value_row):
        bx1 = b["bbox"][0]
        if abs(bx1 - target_x1) < x_tolerance:
            start_idx = i
            break

    if start_idx is None:
        return None

    # Collect contiguous blocks from the starting point
    # Stop if there's a large gap (indicates a different column)
    matching_blocks = [value_row[start_idx]]
    max_gap = x_tolerance * 3  # Allow reasonable gaps between words

    for i in range(start_idx + 1, len(value_row)):
        prev_x2 = matching_blocks[-1]["bbox"][2]
        curr_x1 = value_row[i]["bbox"][0]
        if curr_x1 - prev_x2 < max_gap:
            matching_blocks.append(value_row[i])
        else:
            break

    return " ".join(b["text"] for b in matching_blocks)


def _get_same_line_value(
    row: List[Block],
    alias_text: str,
    label_x2: float,
    x_tolerance: float,
    field_aliases: Dict[str, List[str]],
    current_field: str,
) -> Optional[str]:
    """Extract same-line value blocks that are spatially close to the label.

    Only returns text from blocks immediately to the right of the label,
    excluding blocks that are part of other labels or spatially distant.
    """
    # Find blocks to the right of the label, within a reasonable gap
    max_gap = x_tolerance * 4  # Allow up to 4x tolerance gap on same line
    value_blocks = []

    for b in row:
        bx1 = b["bbox"][0]
        if bx1 > label_x2 and (bx1 - label_x2) < max_gap:
            value_blocks.append(b)
        elif value_blocks and bx1 > value_blocks[-1]["bbox"][2] + max_gap:
            # Gap too large between consecutive value blocks — stop
            break

    if not value_blocks:
        return None

    value_text = " ".join(b["text"] for b in value_blocks).strip()
    value_text = value_text.lstrip(":.-").strip()

    if not value_text or len(value_text) <= 1:
        return None

    # Check if this value text is actually another field's label
    for other_name, other_aliases in field_aliases.items():
        if other_name == current_field:
            continue
        if find_label_in_row(value_text, other_aliases):
            return None

    return value_text


def spatial_extract_fields(
    blocks: List[Block],
    field_aliases: Dict[str, List[str]],
    y_tolerance: float = 0.5,
    x_tolerance: float = 50.0,
) -> List[Dict[str, str]]:
    """Extract fields from OCR blocks using spatial positioning.

    Strategy:
    1. Group blocks into rows by Y coordinate.
    2. For each row, check if it contains known labels.
    3. If labels found, look for values in the NEXT row at the same X position.
    4. Also check for same-line values (label followed by value on same row).

    Args:
        blocks: OCR blocks with text, confidence, and bbox.
        field_aliases: Mapping of field_name -> list of label aliases.
        y_tolerance: Row grouping tolerance (fraction of avg height).
        x_tolerance: Column alignment tolerance (pixels).

    Returns:
        List of {"label": field_name, "value": extracted_value}.
    """
    if not blocks:
        return []

    rows = group_blocks_into_rows(blocks, y_tolerance)
    fields: List[Dict[str, str]] = []
    used_labels: set = set()

    # Pre-compute how many field labels each row contains
    row_label_counts: List[int] = []
    for row in rows:
        row_text = row_to_text(row)
        count = 0
        for _fn, aliases in field_aliases.items():
            if find_label_in_row(row_text, aliases):
                count += 1
        row_label_counts.append(count)

    # Pre-compute best row for each field (row with longest alias match)
    best_row_for_field: Dict[str, int] = {}
    for field_name, aliases in field_aliases.items():
        best_alias_len = 0
        best_row_idx = -1
        for row_idx, row in enumerate(rows):
            row_text = row_to_text(row)
            match = find_label_in_row(row_text, aliases)
            if match and len(match[0]) > best_alias_len:
                best_alias_len = len(match[0])
                best_row_idx = row_idx
        if best_row_idx >= 0:
            best_row_for_field[field_name] = best_row_idx

    for row_idx, row in enumerate(rows):
        row_text = row_to_text(row)
        is_header_row = row_label_counts[row_idx] >= 2

        for field_name, aliases in field_aliases.items():
            if field_name in used_labels:
                continue

            # Skip if a better (longer alias) match exists on a different row
            if field_name in best_row_for_field:
                if best_row_for_field[field_name] != row_idx:
                    continue

            match = find_label_in_row(row_text, aliases)
            if not match:
                continue

            alias_text, start_pos, end_pos = match
            col_x1, col_x2 = get_column_range(row, alias_text)

            if is_header_row:
                # Multi-label row: values are in the NEXT row, column-aligned
                if row_idx + 1 < len(rows):
                    value = extract_value_from_row(
                        rows[row_idx + 1], col_x1, col_x2, x_tolerance
                    )
                    if value and value.strip():
                        fields.append({"label": field_name, "value": value.strip()})
                        used_labels.add(field_name)
            else:
                # Single-label row: try same-line value first, then next row
                same_line_value = _get_same_line_value(
                    row, alias_text, col_x2, x_tolerance,
                    field_aliases, field_name,
                )

                if same_line_value:
                    fields.append({"label": field_name, "value": same_line_value})
                    used_labels.add(field_name)
                elif row_idx + 1 < len(rows):
                    value = extract_value_from_row(
                        rows[row_idx + 1], col_x1, col_x2, x_tolerance
                    )
                    if value and value.strip():
                        fields.append({"label": field_name, "value": value.strip()})
                        used_labels.add(field_name)

    return fields
