# tests/test_preprocessor.py
import io
import numpy as np
from PIL import Image
from app.core.preprocessor import ImagePreprocessor


def _make_test_image(width=200, height=100) -> bytes:
    """Create a simple test image as bytes."""
    img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    pil_img = Image.fromarray(img)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def test_preprocessor_returns_bytes():
    preprocessor = ImagePreprocessor()
    image_bytes = _make_test_image()
    result = preprocessor.process(image_bytes)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_preprocessor_output_is_valid_image():
    preprocessor = ImagePreprocessor()
    image_bytes = _make_test_image()
    result = preprocessor.process(image_bytes)
    img = Image.open(io.BytesIO(result))
    assert img.size[0] > 0
    assert img.size[1] > 0


def test_preprocessor_disabled():
    preprocessor = ImagePreprocessor(enabled=False)
    image_bytes = _make_test_image()
    result = preprocessor.process(image_bytes)
    assert result == image_bytes
