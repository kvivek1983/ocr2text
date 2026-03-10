import cv2
import numpy as np
import pytest

from app.utils.quality import (
    assess_image_quality,
    generate_feedback,
)


def _make_image(w: int, h: int, brightness: int = 128, add_text: bool = True) -> bytes:
    """Create a test image with given properties."""
    img = np.full((h, w, 3), brightness, dtype=np.uint8)
    if add_text:
        cv2.putText(img, "TEST RECEIPT", (10, h // 2),
                     cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        cv2.putText(img, "Total: 1000.00", (10, h // 2 + 40),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def test_good_quality_image():
    image_bytes = _make_image(1600, 1200, brightness=140)
    result = assess_image_quality(image_bytes)
    assert result["score"] >= 0.5
    assert isinstance(result["issues"], list)


def test_low_resolution_image():
    image_bytes = _make_image(200, 150, brightness=140)
    result = assess_image_quality(image_bytes)
    assert any("resolution" in msg.lower() for msg in result["issues"])


def test_dark_image():
    image_bytes = _make_image(800, 600, brightness=30, add_text=False)
    result = assess_image_quality(image_bytes)
    assert any("dark" in msg.lower() for msg in result["issues"])


def test_bright_image():
    image_bytes = _make_image(800, 600, brightness=245, add_text=False)
    result = assess_image_quality(image_bytes)
    assert any("bright" in msg.lower() or "glare" in msg.lower()
               for msg in result["issues"])


def test_low_contrast_image():
    # Uniform gray image = zero contrast
    image_bytes = _make_image(800, 600, brightness=128, add_text=False)
    result = assess_image_quality(image_bytes)
    assert any("contrast" in msg.lower() for msg in result["issues"])


def test_invalid_image_bytes():
    result = assess_image_quality(b"not an image")
    assert result["score"] == 0.0
    assert len(result["issues"]) > 0


def test_generate_feedback_good():
    quality = {"score": 0.85, "issues": []}
    feedback = generate_feedback(quality, confidence=0.8,
                                  confidence_threshold=0.5, fields_count=5)
    assert feedback["quality_level"] == "good"
    assert len(feedback["messages"]) == 0


def test_generate_feedback_low_confidence():
    quality = {"score": 0.85, "issues": []}
    feedback = generate_feedback(quality, confidence=0.3,
                                  confidence_threshold=0.5, fields_count=5)
    assert feedback["quality_level"] == "acceptable"
    assert any("confidence" in msg.lower() for msg in feedback["messages"])


def test_generate_feedback_poor():
    quality = {"score": 0.2, "issues": ["Image is too dark."]}
    feedback = generate_feedback(quality, confidence=0.2,
                                  confidence_threshold=0.5, fields_count=0)
    assert feedback["quality_level"] == "poor"
    assert any("retake" in msg.lower() for msg in feedback["messages"])


def test_generate_feedback_acceptable():
    quality = {"score": 0.6, "issues": ["Low contrast."]}
    feedback = generate_feedback(quality, confidence=0.6,
                                  confidence_threshold=0.5, fields_count=3)
    assert feedback["quality_level"] == "acceptable"
