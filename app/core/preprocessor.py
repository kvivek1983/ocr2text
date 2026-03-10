import cv2
import numpy as np


class ImagePreprocessor:
    """OpenCV-based image preprocessing for better OCR accuracy."""

    def __init__(self, enabled: bool = True, auto_rotate: bool = True):
        self.enabled = enabled
        self.auto_rotate = auto_rotate

    def process(self, image_bytes: bytes) -> bytes:
        """Apply preprocessing pipeline to image bytes."""
        if not self.enabled:
            return image_bytes

        img = self._bytes_to_cv2(image_bytes)
        if self.auto_rotate:
            img = self._correct_rotation(img)
        img = self._to_grayscale(img)
        img = self._denoise(img)
        img = self._enhance_contrast(img)
        img = self._adaptive_threshold(img)
        return self._cv2_to_bytes(img)

    def _bytes_to_cv2(self, image_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def _cv2_to_bytes(self, img: np.ndarray) -> bytes:
        _, buffer = cv2.imencode(".png", img)
        return buffer.tobytes()

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoising(img, None, 10, 7, 21)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def _adaptive_threshold(self, img: np.ndarray) -> np.ndarray:
        return cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

    def _correct_rotation(self, img: np.ndarray) -> np.ndarray:
        """Detect and correct 90/180/270 degree rotation using text line angles.

        Uses Hough line detection on edge-detected image to find dominant
        text orientation, then rotates to landscape/correct reading order.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Detect lines
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=80,
            minLineLength=60, maxLineGap=10,
        )

        if lines is None or len(lines) < 5:
            return img

        # Calculate angles of all detected lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            angles.append(angle)

        angles = np.array(angles)

        # Count lines near 0° (horizontal text) vs near 90° (rotated text)
        horizontal = np.sum(np.abs(angles) < 20)
        vertical = np.sum((np.abs(angles) > 70) & (np.abs(angles) < 110))

        # If mostly vertical lines, image is likely rotated 90°
        if vertical > horizontal * 1.5:
            h, w = img.shape[:2]
            # Determine rotation direction based on dominant angle sign
            mean_vert = np.mean(angles[(np.abs(angles) > 70) & (np.abs(angles) < 110)])
            if mean_vert > 0:
                # Rotated clockwise — need counter-clockwise correction
                img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

        return img
