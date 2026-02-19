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


from app.utils.text_utils import clean_text, normalize_amount, normalize_date


def test_clean_text():
    raw = "  Hello   World \n\n  Foo  "
    assert clean_text(raw) == "Hello World\nFoo"


def test_clean_text_removes_special_chars():
    raw = "Total: ₹1,234.00"
    assert clean_text(raw) == "Total: ₹1,234.00"


def test_normalize_amount():
    assert normalize_amount("₹1,234.00") == "1234.00"
    assert normalize_amount("Rs. 1,234.00") == "1234.00"
    assert normalize_amount("Rs.1234") == "1234"
    assert normalize_amount("1,23,456.78") == "123456.78"
    assert normalize_amount("") == ""


def test_normalize_date():
    assert normalize_date("15/01/2024") == "2024-01-15"
    assert normalize_date("15-01-2024") == "2024-01-15"
    assert normalize_date("01/15/2024") == "2024-01-15"
    assert normalize_date("2024-01-15") == "2024-01-15"
    assert normalize_date("not a date") is None
