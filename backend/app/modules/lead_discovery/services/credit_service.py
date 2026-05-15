"""
app/services/credit_service.py
────────────────────────────────
Enterprise Feature #1 — Credit System.

Provides a clean service interface over CreditRepository.
Used by API endpoints to expose credit balance and admin top-ups.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.discovery_repository import CreditRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class CreditService:
    def __init__(self, db: Session) -> None:
        self._repo = CreditRepository(db)

    def get_balance(self, user_id: str) -> dict:
        credit = self._repo.get_or_create(user_id)
        return {
            "user_id":             credit.user_id,
            "discovery_credits":   credit.discovery_credits,
            "enrichment_credits":  credit.enrichment_credits,
            "total_jobs_run":      credit.total_jobs_run,
            "total_leads_enriched": credit.total_leads_enriched,
            "updated_at":          credit.updated_at,
        }

    def top_up(self, user_id: str, discovery: int = 0, enrichment: int = 0) -> dict:
        """Admin endpoint — add credits to a user account."""
        credit = self._repo.add_credits(user_id, discovery=discovery, enrichment=enrichment)
        logger.info(
            "Credit top-up: user=%s +discovery=%d +enrichment=%d",
            user_id, discovery, enrichment,
        )
        return {
            "user_id":            credit.user_id,
            "discovery_credits":  credit.discovery_credits,
            "enrichment_credits": credit.enrichment_credits,
        }
