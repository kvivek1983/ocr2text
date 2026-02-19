import time
from typing import Any, Dict

from google.cloud import vision

from .base import BaseOCREngine


class GoogleVisionEngine(BaseOCREngine):
    def __init__(self):
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
