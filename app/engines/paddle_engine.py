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

        try:
            pil_img = Image.open(io.BytesIO(image))
            pil_img.verify()  # catch truncated/corrupt files early
            pil_img = Image.open(io.BytesIO(image))  # reopen after verify
            pil_img = pil_img.convert("RGB")
            # Cap at 4096px to avoid memory issues
            max_dim = 4096
            w, h = pil_img.size
            if w > max_dim or h > max_dim:
                scale = max_dim / max(w, h)
                pil_img = pil_img.resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS
                )
                w, h = pil_img.size
            # Pad to nearest multiple of 32 — MKL/oneDNN requires this for CNN layers.
            # Prevents "could not execute a primitive" / "could not create a primitive
            # descriptor" crashes on images with odd/non-aligned dimensions.
            pad_w = (32 - w % 32) % 32
            pad_h = (32 - h % 32) % 32
            if pad_w or pad_h:
                padded = Image.new("RGB", (w + pad_w, h + pad_h), (255, 255, 255))
                padded.paste(pil_img, (0, 0))
                pil_img = padded
            img = np.array(pil_img)
        except Exception as e:
            raise ValueError(f"Invalid or corrupt image: {e}")

        try:
            result = self.ocr.ocr(img)
        except Exception as e:
            raise ValueError(f"PaddleOCR failed: {e}")

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
