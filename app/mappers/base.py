from abc import ABC, abstractmethod
from typing import List, Dict


class BaseMapper(ABC):
    """Abstract base class for document-type-specific field mappers."""

    @abstractmethod
    def map_fields(self, raw_text: str) -> List[Dict[str, str]]:
        """Extract type-specific fields from raw OCR text."""
        pass

    @abstractmethod
    def document_type(self) -> str:
        """Return the document type this mapper handles."""
        pass
