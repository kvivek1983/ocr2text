import base64
import json
import os
import time
from typing import Any, Dict

from google.cloud import vision
from google.oauth2 import service_account

from .base import BaseOCREngine


class GoogleVisionEngine(BaseOCREngine):
    def __init__(self):
        # Support base64-encoded service account JSON via GOOGLE_CREDENTIALS_JSON env var
        # (for Railway/Docker where you can't mount a file)
        creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_b64:
            creds_json = json.loads(base64.b64decode(creds_b64))
            credentials = service_account.Credentials.from_service_account_info(creds_json)
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
        else:
            # Falls back to GOOGLE_APPLICATION_CREDENTIALS file path or default credentials
            self.client = vision.ImageAnnotatorClient()

    def extract(self, image: bytes) -> Dict[str, Any]:
        start = time.time()

        vision_image = vision.Image(content=image)
        response = self.client.text_detection(image=vision_image)

        if response.error.message:
            raise RuntimeError(f"Google Vision error: {response.error.message}")

        raw_text = ""
        blocks = []
        confidences = []

        if response.text_annotations:
            raw_text = response.text_annotations[0].description.strip()

        if response.full_text_annotation:
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    confidences.append(block.confidence)
                    for paragraph in block.paragraphs:
                        words = []
                        for word in paragraph.words:
                            word_text = "".join(
                                [symbol.text for symbol in word.symbols]
                            )
                            words.append(word_text)
                        blocks.append(
                            {
                                "text": " ".join(words),
                                "confidence": block.confidence,
                                "bbox": [],
                            }
                        )

        elapsed = int((time.time() - start) * 1000)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "raw_text": raw_text,
            "confidence": avg_confidence,
            "blocks": blocks,
            "processing_time_ms": elapsed,
        }

    def get_name(self) -> str:
        return "google"
