from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.storage.models import (
    Extraction,
    RCValidation,
    DLValidation,
    AadhaarValidation,
    RCLLMExtraction,
    DLLLMExtraction,
    AadhaarLLMExtraction,
    RCGovtVerification,
    DLGovtVerification,
    AadhaarGovtVerification,
    RCFieldComparison,
    DLFieldComparison,
    AadhaarFieldComparison,
    GovtReseller,
    DriverOnboardingStatus,
)


class ExtractionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> Extraction:
        extraction = Extraction(**kwargs)
        self.session.add(extraction)
        self.session.commit()
        self.session.refresh(extraction)
        return extraction

    def get_by_image_hash(self, image_hash: str) -> Optional[Extraction]:
        return (
            self.session.query(Extraction)
            .filter(Extraction.image_hash == image_hash)
            .first()
        )

    def get_by_id(self, extraction_id: str) -> Optional[Extraction]:
        return (
            self.session.query(Extraction)
            .filter(Extraction.id == extraction_id)
            .first()
        )


class RCValidationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> RCValidation:
        record = RCValidation(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_id(self, validation_id: str) -> Optional[RCValidation]:
        return (
            self.session.query(RCValidation)
            .filter(RCValidation.id == validation_id)
            .first()
        )

    def get_pending_back_for_driver(self, driver_id: str) -> Optional[RCValidation]:
        """Find the most recent front-only record for a driver awaiting back upload."""
        return (
            self.session.query(RCValidation)
            .filter(
                RCValidation.driver_id == driver_id,
                RCValidation.overall_status == "pending_back",
            )
            .order_by(RCValidation.created_at.desc())
            .first()
        )

    def update(self, record: RCValidation, **kwargs) -> RCValidation:
        for key, value in kwargs.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_review_queue(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[RCValidation]:
        q = self.session.query(RCValidation).filter(RCValidation.requires_review == True)
        if status:
            q = q.filter(RCValidation.overall_status == status)
        return q.order_by(RCValidation.created_at.desc()).offset(offset).limit(limit).all()

    def count_review_queue(self, status: Optional[str] = None) -> int:
        q = self.session.query(RCValidation).filter(RCValidation.requires_review == True)
        if status:
            q = q.filter(RCValidation.overall_status == status)
        return q.count()

    def mark_reviewed(
        self,
        validation_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[RCValidation]:
        record = self.get_by_id(validation_id)
        if not record:
            return None
        record.requires_review = False
        record.reviewed_at = datetime.utcnow()
        record.reviewed_by = reviewed_by
        record.review_notes = review_notes
        self.session.commit()
        self.session.refresh(record)
        return record


class DLValidationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> DLValidation:
        record = DLValidation(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_id(self, validation_id: str) -> Optional[DLValidation]:
        return (
            self.session.query(DLValidation)
            .filter(DLValidation.id == validation_id)
            .first()
        )

    def get_pending_back_for_driver(self, driver_id: str) -> Optional[DLValidation]:
        """Find the most recent front-only record for a driver awaiting back upload."""
        return (
            self.session.query(DLValidation)
            .filter(
                DLValidation.driver_id == driver_id,
                DLValidation.overall_status == "pending_back",
            )
            .order_by(DLValidation.created_at.desc())
            .first()
        )

    def update(self, record: DLValidation, **kwargs) -> DLValidation:
        for key, value in kwargs.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_review_queue(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[DLValidation]:
        q = self.session.query(DLValidation).filter(DLValidation.requires_review == True)
        if status:
            q = q.filter(DLValidation.overall_status == status)
        return q.order_by(DLValidation.created_at.desc()).offset(offset).limit(limit).all()

    def count_review_queue(self, status: Optional[str] = None) -> int:
        q = self.session.query(DLValidation).filter(DLValidation.requires_review == True)
        if status:
            q = q.filter(DLValidation.overall_status == status)
        return q.count()

    def mark_reviewed(
        self,
        validation_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[DLValidation]:
        record = self.get_by_id(validation_id)
        if not record:
            return None
        record.requires_review = False
        record.reviewed_at = datetime.utcnow()
        record.reviewed_by = reviewed_by
        record.review_notes = review_notes
        self.session.commit()
        self.session.refresh(record)
        return record


class AadhaarValidationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> AadhaarValidation:
        record = AadhaarValidation(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_id(self, validation_id: str) -> Optional[AadhaarValidation]:
        return (
            self.session.query(AadhaarValidation)
            .filter(AadhaarValidation.id == validation_id)
            .first()
        )

    def get_pending_back_for_driver(self, driver_id: str) -> Optional[AadhaarValidation]:
        """Find the most recent front-only record for a driver awaiting back upload."""
        return (
            self.session.query(AadhaarValidation)
            .filter(
                AadhaarValidation.driver_id == driver_id,
                AadhaarValidation.overall_status == "pending_back",
            )
            .order_by(AadhaarValidation.created_at.desc())
            .first()
        )

    def update(self, record: AadhaarValidation, **kwargs) -> AadhaarValidation:
        for key, value in kwargs.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_review_queue(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[AadhaarValidation]:
        q = self.session.query(AadhaarValidation).filter(AadhaarValidation.requires_review == True)
        if status:
            q = q.filter(AadhaarValidation.overall_status == status)
        return q.order_by(AadhaarValidation.created_at.desc()).offset(offset).limit(limit).all()

    def count_review_queue(self, status: Optional[str] = None) -> int:
        q = self.session.query(AadhaarValidation).filter(AadhaarValidation.requires_review == True)
        if status:
            q = q.filter(AadhaarValidation.overall_status == status)
        return q.count()

    def mark_reviewed(
        self,
        validation_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[AadhaarValidation]:
        record = self.get_by_id(validation_id)
        if not record:
            return None
        record.requires_review = False
        record.reviewed_at = datetime.utcnow()
        record.reviewed_by = reviewed_by
        record.review_notes = review_notes
        self.session.commit()
        self.session.refresh(record)
        return record


class LLMExtractionRepository:
    _MODELS = {
        "rc_book": RCLLMExtraction,
        "driving_license": DLLLMExtraction,
        "aadhaar": AadhaarLLMExtraction,
    }

    def __init__(self, session: Session, doc_type: str):
        self.session = session
        self.model = self._MODELS[doc_type]

    def create(self, **kwargs):
        record = self.model(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_validation_id(self, validation_id: str):
        return (
            self.session.query(self.model)
            .filter(self.model.validation_id == validation_id)
            .order_by(self.model.created_at.desc())
            .first()
        )


class GovtVerificationRepository:
    _MODELS = {
        "rc_book": RCGovtVerification,
        "driving_license": DLGovtVerification,
        "aadhaar": AadhaarGovtVerification,
    }
    _NUMBER_FIELDS = {
        "rc_book": "govt_registration_number",
        "driving_license": "govt_dl_number",
        "aadhaar": "govt_aadhaar_number",
    }

    def __init__(self, session: Session, doc_type: str):
        self.session = session
        self.doc_type = doc_type
        self.model = self._MODELS[doc_type]
        self._number_field = self._NUMBER_FIELDS[doc_type]

    def create(self, **kwargs):
        record = self.model(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_validation_id(self, validation_id: str):
        return (
            self.session.query(self.model)
            .filter(self.model.validation_id == validation_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def get_by_reg_number(self, number: str):
        field = getattr(self.model, self._number_field)
        return (
            self.session.query(self.model)
            .filter(field == number)
            .order_by(self.model.created_at.desc())
            .first()
        )


class FieldComparisonRepository:
    _MODELS = {
        "rc_book": RCFieldComparison,
        "driving_license": DLFieldComparison,
        "aadhaar": AadhaarFieldComparison,
    }

    def __init__(self, session: Session, doc_type: str):
        self.session = session
        self.model = self._MODELS[doc_type]

    def bulk_create(self, comparisons: list) -> list:
        records = []
        for data in comparisons:
            record = self.model(**data)
            self.session.add(record)
            records.append(record)
        self.session.commit()
        for record in records:
            self.session.refresh(record)
        return records

    def get_by_validation_id(self, validation_id: str) -> list:
        return (
            self.session.query(self.model)
            .filter(self.model.validation_id == validation_id)
            .all()
        )


class GovtResellerRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_ordered(self, doc_type: Optional[str] = None) -> List[GovtReseller]:
        q = self.session.query(GovtReseller).filter(GovtReseller.is_active == True)
        results = q.order_by(GovtReseller.priority.asc()).all()
        if doc_type:
            results = [r for r in results if r.supported_doc_types and doc_type in r.supported_doc_types]
        return results

    def update_stats(self, reseller_id: str, success: bool, response_ms: int) -> Optional[GovtReseller]:
        record = self.session.query(GovtReseller).filter(GovtReseller.id == reseller_id).first()
        if not record:
            return None
        record.total_requests = (record.total_requests or 0) + 1
        if success:
            record.successful_requests = (record.successful_requests or 0) + 1
            record.consecutive_failures = 0
        else:
            record.consecutive_failures = (record.consecutive_failures or 0) + 1
            record.last_failure_at = datetime.utcnow()
        prev_avg = record.avg_response_ms or response_ms
        total = record.total_requests
        record.avg_response_ms = int((prev_avg * (total - 1) + response_ms) / total)
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record

    def update_circuit_state(self, reseller_id: str, state: str) -> Optional[GovtReseller]:
        record = self.session.query(GovtReseller).filter(GovtReseller.id == reseller_id).first()
        if not record:
            return None
        record.circuit_state = state
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record


class DriverOnboardingRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_driver_id(self, driver_id: str) -> Optional[DriverOnboardingStatus]:
        return (
            self.session.query(DriverOnboardingStatus)
            .filter(DriverOnboardingStatus.driver_id == driver_id)
            .first()
        )

    def upsert(self, driver_id: str, **kwargs) -> DriverOnboardingStatus:
        record = self.get_by_driver_id(driver_id)
        if record:
            for key, value in kwargs.items():
                setattr(record, key, value)
            record.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(record)
        else:
            record = DriverOnboardingStatus(driver_id=driver_id, **kwargs)
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
        return record
