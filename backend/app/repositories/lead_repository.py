"""
app/repositories/lead_repository.py
──────────────────────────────────────
All queries MUST pass user_id to enforce multi-tenant isolation.
"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models.lead import Lead
from app.schemas.lead import LeadCreate
from app.core.logging import get_logger

logger = get_logger(__name__)


class LeadRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_many(self, leads_data: List[LeadCreate], user_id: str) -> List[Lead]:
        """Bulk-insert leads; skips duplicates (same email+user_id)."""
        existing_emails = {
            e for (e,) in self.db.query(Lead.email)
            .filter(Lead.user_id == user_id)
            .all()
        }
        new_leads: List[Lead] = []
        for ld in leads_data:
            if ld.email in existing_emails:
                logger.info("Skipping duplicate lead email=%s user_id=%s", ld.email, user_id)
                continue
            lead = Lead(**ld.model_dump(), user_id=user_id)
            self.db.add(lead)
            new_leads.append(lead)
            existing_emails.add(ld.email)

        self.db.commit()
        for lead in new_leads:
            self.db.refresh(lead)
        logger.info("Inserted %d leads for user_id=%s", len(new_leads), user_id)
        return new_leads

    def get_all(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        with_scores: bool = True,
    ) -> tuple[List[Lead], int]:
        query = (
            self.db.query(Lead)
            .filter(Lead.user_id == user_id)
        )
        if with_scores:
            try:
                # Defensive lookup - using options(joinedload) acts as outer join smoothly 
                query = query.options(joinedload(Lead.score))
            except Exception as e:
                logger.warning("Could not outerjoin scores, falling back to Lead-only: %s", e)

        total = query.count()
        leads = (
            query
            .order_by(Lead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return leads, total

    def get_by_id(self, lead_id: str, user_id: str) -> Optional[Lead]:
        return (
            self.db.query(Lead)
            .filter(Lead.id == lead_id, Lead.user_id == user_id)
            .options(joinedload(Lead.score))
            .first()
        )

    def get_by_ids(self, lead_ids: List[str], user_id: str) -> List[Lead]:
        return (
            self.db.query(Lead)
            .filter(Lead.id.in_(lead_ids), Lead.user_id == user_id)
            .all()
        )

    def count_by_user(self, user_id: str) -> int:
        return self.db.query(Lead).filter(Lead.user_id == user_id).count()

    def delete(self, lead_id: str, user_id: str) -> bool:
        """
        Hard-delete a lead and its associated score (user-scoped).
        Returns True if the lead was found and deleted, False if not found.
        """
        from app.models.lead_score import LeadScore
        lead = (
            self.db.query(Lead)
            .filter(Lead.id == lead_id, Lead.user_id == user_id)
            .first()
        )
        if not lead:
            return False
        # Cascade-delete the score first (FK constraint)
        self.db.query(LeadScore).filter(LeadScore.lead_id == lead_id).delete()
        self.db.delete(lead)
        self.db.commit()
        logger.info("Deleted lead id=%s user_id=%s", lead_id, user_id)
        return True

    def get_by_ids(self, lead_ids: list[str], user_id: str) -> list[Lead]:
        """Fetch multiple leads by their IDs, scoped to the user."""
        if not lead_ids:
            return []
        return (
            self.db.query(Lead)
            .filter(Lead.user_id == user_id, Lead.id.in_(lead_ids))
            .all()
        )

