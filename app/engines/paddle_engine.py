# app/engines/paddle_engine.py
import io
import time
from typing import Any, Dict

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

from .base import BaseOCREngine


class PaddleEngine(BaseOCREngine):
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    def extract(self, image: bytes) -> Dict[str, Any]:
        start = time.time()

        img = np.array(Image.open(io.BytesIO(image)))
        result = self.ocr.ocr(img)

        blocks = []
        all_text = []
        confidences = []

        if result and result[0]:
            for line in result[0]:
                bbox, (text, conf) = line
                blocks.append(
                    {
                        "text": text,
                        "confidence": conf,
                        "bbox": [
                            bbox[0][0],
                            bbox[0][1],
                            bbox[2][0],
                            bbox[2][1],
                        ],
                    }
                )
                all_text.append(text)
                confidences.append(conf)

        elapsed = int((time.time() - start) * 1000)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "raw_text": "\n".join(all_text),
            "confidence": avg_confidence,
            "blocks": blocks,
            "processing_time_ms": elapsed,
        }

    def get_name(self) -> str:
        return "paddle"
