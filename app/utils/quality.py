import cv2
import numpy as np
from typing import Dict, List


def assess_image_quality(image_bytes: bytes) -> Dict:
    """Assess image quality and return scores + issues."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {
            "score": 0.0,
            "issues": ["Unable to decode image"],
        }

    issues: List[str] = []
    scores: List[float] = []

    # 1. Resolution check
    h, w = img.shape[:2]
    resolution_score = _score_resolution(w, h)
    scores.append(resolution_score)
    if resolution_score < 0.5:
        issues.append(f"Low resolution ({w}x{h}). Use at least 800x600 for best results.")

    # 2. Blur detection (Laplacian variance)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blur_score = _score_blur(gray)
    scores.append(blur_score)
    if blur_score < 0.5:
        issues.append("Image appears blurry. Hold the camera steady and ensure focus.")

    # 3. Brightness check
    brightness_score = _score_brightness(gray)
    scores.append(brightness_score)
    if brightness_score < 0.5:
        mean_val = np.mean(gray)
        if mean_val < 80:
            issues.append("Image is too dark. Try better lighting.")
        else:
            issues.append("Image is too bright/washed out. Reduce glare or flash.")

    # 4. Contrast check
    contrast_score = _score_contrast(gray)
    scores.append(contrast_score)
    if contrast_score < 0.5:
        issues.append("Low contrast. Ensure the document is well-lit and text is visible.")

    overall = sum(scores) / len(scores) if scores else 0.0

    return {
        "score": round(overall, 2),
        "issues": issues,
    }


def generate_feedback(
    image_quality: Dict,
    confidence: float,
    confidence_threshold: float,
    fields_count: int,
) -> Dict:
    """Generate user-facing feedback based on quality and confidence."""
    messages: List[str] = []
    quality_score = image_quality["score"]

    # Image quality feedback
    messages.extend(image_quality["issues"])

    # OCR confidence feedback
    if confidence < confidence_threshold:
        messages.append(
            f"OCR confidence is low ({confidence:.0%}). "
            "The extracted data may be inaccurate."
        )

    if fields_count == 0 and confidence < confidence_threshold:
        messages.append("No fields could be extracted. Please retake the photo.")

    # Determine overall quality level
    if quality_score >= 0.75 and confidence >= confidence_threshold:
        level = "good"
    elif quality_score >= 0.5 or confidence >= confidence_threshold:
        level = "acceptable"
    else:
        level = "poor"

    return {
        "quality_level": level,
        "image_quality_score": quality_score,
        "messages": messages,
    }


def _score_resolution(w: int, h: int) -> float:
    """Score resolution from 0-1. 800x600 = 0.5, 1600x1200+ = 1.0."""
    pixels = w * h
    if pixels >= 1_920_000:  # ~1600x1200
        return 1.0
    if pixels >= 480_000:  # ~800x600
        return 0.5 + 0.5 * (pixels - 480_000) / (1_920_000 - 480_000)
    if pixels >= 100_000:  # ~400x250
        return 0.5 * (pixels - 100_000) / (480_000 - 100_000)
    return 0.0


def _score_blur(gray: np.ndarray) -> float:
    """Score sharpness using Laplacian variance. Higher = sharper."""
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var >= 500:
        return 1.0
    if laplacian_var >= 100:
        return 0.5 + 0.5 * (laplacian_var - 100) / 400
    if laplacian_var >= 20:
        return 0.5 * (laplacian_var - 20) / 80
    return 0.0


def _score_brightness(gray: np.ndarray) -> float:
    """Score brightness. Ideal range: 100-180."""
    mean_val = np.mean(gray)
    if 100 <= mean_val <= 180:
        return 1.0
    if 80 <= mean_val < 100:
        return 0.5 + 0.5 * (mean_val - 80) / 20
    if 180 < mean_val <= 220:
        return 0.5 + 0.5 * (220 - mean_val) / 40
    if 50 <= mean_val < 80:
        return 0.5 * (mean_val - 50) / 30
    if 220 < mean_val <= 240:
        return 0.5 * (240 - mean_val) / 20
    return 0.0


def _score_contrast(gray: np.ndarray) -> float:
    """Score contrast using standard deviation of pixel values."""
    std_val = np.std(gray)
    if std_val >= 60:
        return 1.0
    if std_val >= 30:
        return 0.5 + 0.5 * (std_val - 30) / 30
    if std_val >= 10:
        return 0.5 * (std_val - 10) / 20
    return 0.0
