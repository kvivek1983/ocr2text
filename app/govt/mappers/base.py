from abc import ABC, abstractmethod
from pydantic import BaseModel

class BaseGovtMapper(ABC):
    @abstractmethod
    def normalize(self, raw_response: dict, doc_type: str) -> BaseModel:
        ...
