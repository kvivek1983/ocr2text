import base64
import hashlib

import httpx


def decode_base64_image(data: str) -> bytes:
    """Decode base64 string to image bytes. Handles data URI prefix."""
    if "," in data:
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def fetch_image_url(url: str) -> bytes:
    """Download image from URL and return bytes."""
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def hash_image(image_bytes: bytes) -> str:
    """Return SHA-256 hash of image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()
