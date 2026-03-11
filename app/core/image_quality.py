import cv2
import numpy as np
from typing import Dict, List, Optional

from app.mappers.rc_book import FRONT_MANDATORY, BACK_MANDATORY


class ImageQualityAssessor:
    """Two-layer image quality assessment for OCR documents."""

    # Thresholds
    MIN_RESOLUTION = (400, 300)  # minimum width x height
    GOOD_RESOLUTION = (800, 600)
    BLUR_THRESHOLD = 100.0  # Laplacian variance threshold
    BRIGHTNESS_LOW = 50
    BRIGHTNESS_HIGH = 200

    def assess_image_properties(self, image: np.ndarray) -> Dict:
        """Layer A: Pre-OCR image property assessment."""
        # Blur detection using Laplacian variance
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Normalize blur score: higher variance = sharper image
        # Use log scale for better distribution
        blur_score = min(1.0, laplacian_var / self.BLUR_THRESHOLD)

        # Brightness assessment
        mean_brightness = np.mean(gray)
        if mean_brightness < self.BRIGHTNESS_LOW:
            brightness_score = mean_brightness / self.BRIGHTNESS_LOW
        elif mean_brightness > self.BRIGHTNESS_HIGH:
            brightness_score = max(0, 1.0 - (mean_brightness - self.BRIGHTNESS_HIGH) / (255 - self.BRIGHTNESS_HIGH))
        else:
            brightness_score = 1.0

        # Resolution assessment — compare orientation-independent
        height, width = image.shape[:2]
        long_side = max(width, height)
        short_side = min(width, height)
        good_long = max(self.GOOD_RESOLUTION)
        good_short = min(self.GOOD_RESOLUTION)
        min_long = max(self.MIN_RESOLUTION)
        min_short = min(self.MIN_RESOLUTION)

        if long_side >= good_long and short_side >= good_short:
            resolution_score = 1.0
        elif long_side < min_long or short_side < min_short:
            resolution_score = min(
                long_side / min_long,
                short_side / min_short,
            )
        else:
            resolution_score = 0.5 + 0.5 * min(
                (long_side - min_long) / (good_long - min_long),
                (short_side - min_short) / (good_short - min_short),
            )

        # Overall Layer A score (equal weights)
        layer_a_score = (blur_score + brightness_score + resolution_score) / 3.0

        return {
            "blur_score": round(blur_score, 3),
            "brightness_score": round(brightness_score, 3),
            "resolution_score": round(resolution_score, 3),
            "layer_a_score": round(layer_a_score, 3),
        }

    def assess_completeness(self, fields: List[Dict[str, str]], side: str = "front") -> Dict:
        """Layer B: Post-OCR extraction completeness assessment."""
        mandatory = FRONT_MANDATORY if side == "front" else BACK_MANDATORY

        extracted_labels = {f["label"] for f in fields}
        found = [m for m in mandatory if m in extracted_labels]
        missing = [m for m in mandatory if m not in extracted_labels]

        total = len(mandatory)
        completeness_score = len(found) / total if total > 0 else 0.0

        return {
            "completeness_score": round(completeness_score, 3),
            "missing_mandatory": missing,
            "total_mandatory": total,
            "found_mandatory": len(found),
            "layer_b_score": round(completeness_score, 3),
        }

    def combine(self, layer_a: Dict, layer_b: Dict) -> Dict:
        """Combine Layer A and Layer B into overall quality assessment."""
        overall_score = 0.3 * layer_a["layer_a_score"] + 0.7 * layer_b["layer_b_score"]

        # Determine acceptability
        missing_count = len(layer_b["missing_mandatory"])
        is_blurry = layer_a["blur_score"] < 0.5

        # Rules: 2+ missing mandatory = unacceptable; blur + 1 missing = unacceptable
        if missing_count >= 2:
            is_acceptable = False
        elif is_blurry and missing_count >= 1:
            is_acceptable = False
        else:
            is_acceptable = True

        # Generate feedback messages
        feedback = []
        if is_blurry:
            feedback.append("Image appears blurry. Please upload a clearer photo.")
        if layer_a["brightness_score"] < 0.5:
            feedback.append("Image is too dark or overexposed. Please ensure good lighting.")
        if layer_a["resolution_score"] < 0.5:
            feedback.append("Image resolution is too low. Please upload a higher resolution image.")
        if missing_count > 0:
            feedback.append(f"Could not extract {missing_count} mandatory field(s): {', '.join(layer_b['missing_mandatory'])}.")

        return {
            "overall_score": round(overall_score, 3),
            "is_acceptable": is_acceptable,
            "feedback": feedback,
            **layer_a,
            **layer_b,
        }
