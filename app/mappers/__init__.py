# app/mappers/__init__.py
from typing import Dict, List

from app.mappers.base import BaseMapper
from app.mappers.receipt import ReceiptMapper
from app.mappers.invoice import InvoiceMapper
from app.mappers.driving_license import DrivingLicenseMapper
from app.mappers.rc_book import RCBookMapper
from app.mappers.insurance import InsuranceMapper
from app.mappers.petrol_receipt import PetrolReceiptMapper
from app.mappers.odometer import OdometerMapper
from app.mappers.fuel_pump_reading import FuelPumpReadingMapper

_MAPPER_REGISTRY: Dict[str, BaseMapper] = {
    "receipt": ReceiptMapper(),
    "invoice": InvoiceMapper(),
    "driving_license": DrivingLicenseMapper(),
    "rc_book": RCBookMapper(),
    "insurance": InsuranceMapper(),
    "petrol_receipt": PetrolReceiptMapper(),
    "odometer": OdometerMapper(),
    "fuel_pump_reading": FuelPumpReadingMapper(),
}


def get_mapper(document_type: str) -> BaseMapper:
    """Get the field mapper for a document type."""
    if document_type not in _MAPPER_REGISTRY:
        raise ValueError(f"No mapper for document type: {document_type}")
    return _MAPPER_REGISTRY[document_type]


def list_document_types() -> List[str]:
    """List all supported document types."""
    return list(_MAPPER_REGISTRY.keys())
