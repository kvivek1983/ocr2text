from typing import Optional

from sqlalchemy.orm import Session

from app.storage.models import Extraction


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
