from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.storage.models import (
    DocumentValidation,
    LLMExtraction,
    GovtVerification,
    FieldComparison,
    GovtReseller,
    DriverOnboardingStatus,
)


# =============================================================================
# NEW — Unified repositories for /verify/document pipeline
# =============================================================================

class DocumentValidationRepository:
    """Unified repository for all doc types (rc_book, driving_license, aadhaar)."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> DocumentValidation:
        record = DocumentValidation(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_id(self, validation_id: str) -> Optional[DocumentValidation]:
        return (
            self.session.query(DocumentValidation)
            .filter(DocumentValidation.id == validation_id)
            .first()
        )

    def get_pending_back_for_driver(self, driver_id: str, doc_type: str) -> Optional[DocumentValidation]:
        """Find the most recent front-only record for a driver awaiting back upload."""
        return (
            self.session.query(DocumentValidation)
            .filter(
                DocumentValidation.driver_id == driver_id,
                DocumentValidation.doc_type == doc_type,
                DocumentValidation.overall_status == "pending_back",
            )
            .order_by(DocumentValidation.created_at.desc())
            .first()
        )

    def get_latest_for_driver(self, driver_id: str, doc_type: str) -> Optional[DocumentValidation]:
        """Find the most recent record for a driver + doc_type (any status)."""
        return (
            self.session.query(DocumentValidation)
            .filter(
                DocumentValidation.driver_id == driver_id,
                DocumentValidation.doc_type == doc_type,
            )
            .order_by(DocumentValidation.created_at.desc())
            .first()
        )

    def update(self, record: DocumentValidation, **kwargs) -> DocumentValidation:
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
        doc_type: Optional[str] = None,
    ) -> List[DocumentValidation]:
        q = self.session.query(DocumentValidation).filter(DocumentValidation.requires_review == True)
        if status:
            q = q.filter(DocumentValidation.overall_status == status)
        if doc_type:
            q = q.filter(DocumentValidation.doc_type == doc_type)
        return q.order_by(DocumentValidation.created_at.desc()).offset(offset).limit(limit).all()

    def count_review_queue(self, status: Optional[str] = None, doc_type: Optional[str] = None) -> int:
        q = self.session.query(DocumentValidation).filter(DocumentValidation.requires_review == True)
        if status:
            q = q.filter(DocumentValidation.overall_status == status)
        if doc_type:
            q = q.filter(DocumentValidation.doc_type == doc_type)
        return q.count()

    def mark_reviewed(
        self,
        validation_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> Optional[DocumentValidation]:
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
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> LLMExtraction:
        record = LLMExtraction(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_validation_id(self, validation_id: str) -> Optional[LLMExtraction]:
        return (
            self.session.query(LLMExtraction)
            .filter(LLMExtraction.validation_id == validation_id)
            .order_by(LLMExtraction.created_at.desc())
            .first()
        )


class GovtVerificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> GovtVerification:
        record = GovtVerification(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_by_validation_id(self, validation_id: str) -> Optional[GovtVerification]:
        return (
            self.session.query(GovtVerification)
            .filter(GovtVerification.validation_id == validation_id)
            .order_by(GovtVerification.created_at.desc())
            .first()
        )


class FieldComparisonRepository:
    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, comparisons: list) -> list:
        records = []
        for data in comparisons:
            record = FieldComparison(**data)
            self.session.add(record)
            records.append(record)
        self.session.commit()
        for record in records:
            self.session.refresh(record)
        return records

    def get_by_validation_id(self, validation_id: str) -> list:
        return (
            self.session.query(FieldComparison)
            .filter(FieldComparison.validation_id == validation_id)
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

    def record_success(self, reseller_id: str, response_time_ms: int) -> Optional[GovtReseller]:
        record = (
            self.session.query(GovtReseller)
            .filter(GovtReseller.id == reseller_id)
            .with_for_update()
            .first()
        )
        if not record:
            return None
        record.total_requests = (record.total_requests or 0) + 1
        record.successful_requests = (record.successful_requests or 0) + 1
        record.consecutive_failures = 0
        record.circuit_state = "closed"
        prev_avg = record.avg_response_ms or response_time_ms
        total = record.total_requests
        record.avg_response_ms = int((prev_avg * (total - 1) + response_time_ms) / total)
        record.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(record)
        return record

    def record_failure(self, reseller_id: str, reason: str) -> Optional[GovtReseller]:
        record = (
            self.session.query(GovtReseller)
            .filter(GovtReseller.id == reseller_id)
            .with_for_update()
            .first()
        )
        if not record:
            return None
        record.total_requests = (record.total_requests or 0) + 1
        record.consecutive_failures = (record.consecutive_failures or 0) + 1
        record.last_failure_at = datetime.utcnow()
        if record.consecutive_failures >= 5:
            record.circuit_state = "open"
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
        record = (
            self.session.query(DriverOnboardingStatus)
            .filter(DriverOnboardingStatus.driver_id == driver_id)
            .with_for_update()
            .first()
        )
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
