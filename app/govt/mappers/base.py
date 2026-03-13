from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseGovtMapper(ABC):
    @abstractmethod
    def normalize(self, raw_response: dict, doc_type: str) -> Dict[str, Any]:
        ...
