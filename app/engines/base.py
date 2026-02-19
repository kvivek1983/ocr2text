from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseOCREngine(ABC):
    """Abstract base class for all OCR engines."""

    @abstractmethod
    def extract(self, image: bytes) -> Dict[str, Any]:
        """
        Extract text from image.

        Returns:
            {
                "raw_text": str,
                "confidence": float,
                "blocks": [{"text": str, "confidence": float, "bbox": list}],
                "processing_time_ms": int
            }
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return engine identifier (e.g., 'paddle', 'google')"""
        pass

    def health_check(self) -> bool:
        """Check if engine is available."""
        return True
