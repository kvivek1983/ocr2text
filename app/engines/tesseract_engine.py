# app/engines/tesseract_engine.py
import io
import time
from typing import Any, Dict

from PIL import Image
import pytesseract

from .base import BaseOCREngine


class TesseractEngine(BaseOCREngine):
    def __init__(self, lang: str = "eng"):
        self.lang = lang

    def extract(self, image: bytes) -> Dict[str, Any]:
        start = time.time()

        img = Image.open(io.BytesIO(image))

        # Get full text
        raw_text = pytesseract.image_to_string(img, lang=self.lang).strip()

        # Get detailed data with confidence
        data = pytesseract.image_to_data(
            img, lang=self.lang, output_type=pytesseract.Output.DICT
        )

        blocks = []
        confidences = []

        for i, text in enumerate(data["text"]):
            conf = data["conf"][i]
            if text.strip() and conf > 0:
                blocks.append(
                    {
                        "text": text.strip(),
                        "confidence": conf / 100.0,
                        "bbox": [
                            data["left"][i],
                            data["top"][i],
                            data["left"][i] + data["width"][i],
                            data["top"][i] + data["height"][i],
                        ],
                    }
                )
                confidences.append(conf / 100.0)

        elapsed = int((time.time() - start) * 1000)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "raw_text": raw_text,
            "confidence": avg_confidence,
            "blocks": blocks,
            "processing_time_ms": elapsed,
        }

    def get_name(self) -> str:
        return "tesseract"
