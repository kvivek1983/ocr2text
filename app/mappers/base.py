from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseMapper(ABC):
    """Abstract base class for document-type-specific field mappers."""

    @abstractmethod
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        """Extract type-specific fields from raw OCR text."""
        pass

    def map_fields_spatial(
        self, blocks: List[Dict], raw_text: str
    ) -> List[Dict[str, str]]:
        """Extract fields using OCR blocks with bounding boxes.

        Default implementation falls back to text-based map_fields.
        Subclasses can override for spatial/positional extraction.
        """
        return self.map_fields(raw_text)

    @abstractmethod
    def document_type(self) -> str:
        """Return the document type this mapper handles."""
        pass
