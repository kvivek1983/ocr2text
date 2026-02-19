import base64
import hashlib
from unittest.mock import patch, MagicMock
from app.utils.image_utils import decode_base64_image, fetch_image_url, hash_image


def test_decode_base64_image():
    original = b"fake image bytes"
    encoded = base64.b64encode(original).decode("utf-8")
    result = decode_base64_image(encoded)
    assert result == original


def test_decode_base64_image_with_data_uri():
    original = b"fake image bytes"
    encoded = base64.b64encode(original).decode("utf-8")
    data_uri = f"data:image/png;base64,{encoded}"
    result = decode_base64_image(data_uri)
    assert result == original


def test_hash_image():
    image_bytes = b"fake image bytes"
    expected = hashlib.sha256(image_bytes).hexdigest()
    assert hash_image(image_bytes) == expected


def test_fetch_image_url():
    mock_response = MagicMock()
    mock_response.content = b"downloaded image"
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("app.utils.image_utils.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response
        result = fetch_image_url("https://example.com/image.jpg")

    assert result == b"downloaded image"
