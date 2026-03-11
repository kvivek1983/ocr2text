import re
import cv2
import numpy as np
from typing import Dict, Optional


# Indian vehicle registration format: 2 letters + 2 digits + 1-3 letters + 1-4 digits
# Examples: KA01AB1234, MH02CD5678, DL3CAF1234
REGISTRATION_PATTERN = re.compile(
    r'[A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4}',
    re.IGNORECASE
)

# RC header markers
RC_HEADER_MARKERS = [
    "registration certificate",
    "form 23",
    "form no. 23",
    "certificate of registration",
]

# Minimum field-like lines (lines with colon or key-value pattern)
FRONT_MIN_FIELDS = 4
BACK_MIN_FIELDS = 3

# Card aspect ratio range (width/height)
CARD_ASPECT_MIN = 1.3
CARD_ASPECT_MAX = 1.9


class DocumentValidator:
    """Validates document authenticity using structural and visual checks."""

    def check_structural(self, text: str, side: str = "front") -> Dict:
        """Structural text-based authenticity checks (critical, pass/fail)."""
        text_lower = text.lower()

        # 1. Header check
        has_header = any(marker in text_lower for marker in RC_HEADER_MARKERS)

        # 2. Registration format check
        has_valid_reg_format = bool(REGISTRATION_PATTERN.search(text))

        # 3. Field count check - count lines that look like key:value pairs
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        field_lines = [l for l in lines if ':' in l or re.search(r'\w+\s*[-:]\s*\S', l)]
        min_fields = FRONT_MIN_FIELDS if side == "front" else BACK_MIN_FIELDS
        has_sufficient_fields = len(field_lines) >= min_fields

        # Overall: header is critical, others are supporting
        is_authentic = has_header and (has_valid_reg_format or has_sufficient_fields)

        return {
            "has_header": has_header,
            "has_valid_reg_format": has_valid_reg_format,
            "has_sufficient_fields": has_sufficient_fields,
            "field_count": len(field_lines),
            "is_authentic": is_authentic,
        }

    def check_visual(self, image: np.ndarray) -> Dict:
        """Visual OpenCV-based checks (confidence-only, advisory)."""
        height, width = image.shape[:2]

        # 1. Aspect ratio check
        aspect_ratio = width / height if height > 0 else 0
        if CARD_ASPECT_MIN <= aspect_ratio <= CARD_ASPECT_MAX:
            aspect_ratio_score = 1.0
        else:
            # Distance from ideal range
            if aspect_ratio < CARD_ASPECT_MIN:
                aspect_ratio_score = max(0, aspect_ratio / CARD_ASPECT_MIN)
            else:
                aspect_ratio_score = max(0, 1.0 - (aspect_ratio - CARD_ASPECT_MAX) / CARD_ASPECT_MAX)

        # 2. Edge detection (check if card edges are visible)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / (width * height) if (width * height) > 0 else 0
        # A real document photo should have some edges (text, borders) but not too many
        if 0.01 < edge_ratio < 0.15:
            edge_score = 1.0
        elif edge_ratio <= 0.01:
            edge_score = edge_ratio / 0.01
        else:
            edge_score = max(0, 1.0 - (edge_ratio - 0.15) / 0.15)

        # 3. Color variance (real documents have some color variation)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        color_std = np.std(hsv[:, :, 1])  # saturation channel standard deviation
        color_score = min(1.0, color_std / 30.0)  # normalize

        # Overall visual confidence
        visual_confidence = (aspect_ratio_score + edge_score + color_score) / 3.0

        return {
            "aspect_ratio": round(aspect_ratio, 3),
            "aspect_ratio_score": round(aspect_ratio_score, 3),
            "edge_score": round(edge_score, 3),
            "color_score": round(color_score, 3),
            "visual_confidence": round(visual_confidence, 3),
        }

    def validate(self, text: str, image: np.ndarray, side: str = "front") -> Dict:
        """Combined structural + visual validation."""
        structural = self.check_structural(text, side)
        visual = self.check_visual(image)

        # Base confidence from structural (0.5 if authentic, 0 if not)
        base_confidence = 0.5 if structural["is_authentic"] else 0.0

        # Add up to 0.5 from visual checks
        visual_bonus = visual["visual_confidence"] * 0.5

        confidence = base_confidence + visual_bonus

        return {
            "is_authentic": structural["is_authentic"],
            "confidence": round(confidence, 3),
            "structural": structural,
            "visual": visual,
        }
