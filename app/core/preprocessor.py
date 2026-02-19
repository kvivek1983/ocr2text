import cv2
import numpy as np


class ImagePreprocessor:
    """OpenCV-based image preprocessing for better OCR accuracy."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def process(self, image_bytes: bytes) -> bytes:
        """Apply preprocessing pipeline to image bytes."""
        if not self.enabled:
            return image_bytes

        img = self._bytes_to_cv2(image_bytes)
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
