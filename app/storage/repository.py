from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.storage.models import Extraction, RCValidation


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
