import cv2
import numpy as np
from typing import Dict


class ImageQualityAssessor:
    """
    Layer A: Pre-OCR image quality assessment.

    Runs on raw image_bytes BEFORE calling Google Vision or LLM.
    If quality is below threshold, we reject immediately and skip LLM (save cost).

    Checks:
    - Blur detection (Laplacian variance) — is the image sharp enough for OCR?
    - Brightness assessment (mean pixel value) — too dark or overexposed?
    - Resolution assessment (image dimensions) — enough pixels for text extraction?
    """

    # Thresholds
    MIN_RESOLUTION = (400, 300)   # minimum width x height
    GOOD_RESOLUTION = (800, 600)
    BLUR_THRESHOLD = 100.0        # Laplacian variance threshold
    BRIGHTNESS_LOW = 50
    BRIGHTNESS_HIGH = 200

    def assess_image_properties(self, image: np.ndarray) -> Dict:
        """
        Layer A: Pre-OCR image property assessment.

        Args:
            image: OpenCV BGR image (numpy array)

        Returns:
            Dict with blur_score, brightness_score, resolution_score, layer_a_score
            All scores are 0.0 - 1.0 (higher = better)
        """
        # Blur detection using Laplacian variance
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Normalize blur score: higher variance = sharper image
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
