"""
app/services/lead_service.py
──────────────────────────────
Handles lead ingestion from CSV or JSON.
All leads stored with user_id for multi-tenant isolation.

ADDITION 5: Upload → triggers Automation 1 (scoring pipeline) automatically.
Upload limits: max 10k rows, max 10MB enforced via route.
"""
import csv
import io
from typing import List

from sqlalchemy.orm import Session

from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadCreate, LeadUploadResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

CSV_ROW_LIMIT = 10_000


class LeadService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = LeadRepository(db)

    def _score_leads_background(self, lead_ids: List[str], user_id: str) -> None:
        """
        Trigger Automation 1 scoring pipeline for newly uploaded leads.
        Uses ScoringService directly (sync within the request context).
        Fires-and-logs: failures don't break the upload response.
        """
        if not lead_ids:
            return
        try:
            from app.modules.lead_scoring.services.scoring_service import ScoringService
            scorer = ScoringService(self.db)
            results = scorer.score_leads(lead_ids, user_id)
            logger.info(
                "Auto-scored %d/%d leads for user_id=%s after upload",
                len(results), len(lead_ids), user_id
            )
        except Exception as e:
            logger.error(
                "Auto-scoring failed for user_id=%s (non-fatal): %s",
                user_id, e
            )

    def upload_from_json(self, data: List[dict], user_id: str) -> LeadUploadResponse:
        if len(data) > CSV_ROW_LIMIT:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many leads. Maximum is {CSV_ROW_LIMIT} per upload.",
            )

        leads_to_create = []
        for row in data:
            try:
                lead = LeadCreate(**row)
                leads_to_create.append(lead)
            except Exception as e:
                logger.warning("Skipping invalid lead row %s: %s", row, e)

        created = self.repo.create_many(leads_to_create, user_id)

        # ── Automation 1: Auto-score uploaded leads ───────────────────────────
        self._score_leads_background([l.id for l in created], user_id)

        return LeadUploadResponse(
            message="Upload complete.",
            created=len(created),
            skipped=len(leads_to_create) - len(created),
            lead_ids=[l.id for l in created],
        )

    def upload_from_csv(self, file_content: bytes, user_id: str) -> LeadUploadResponse:
        text = file_content.decode("utf-8-sig")  # handle BOM
        reader = csv.DictReader(io.StringIO(text))

        leads_to_create = []
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > CSV_ROW_LIMIT:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV too large. Maximum is {CSV_ROW_LIMIT} rows per upload.",
                )
            # Normalize keys to lowercase with underscores
            normalized = {
                k.lower().replace(" ", "_"): v.strip()
                for k, v in row.items()
                if v and v.strip()
            }
            try:
                lead = LeadCreate(**normalized)
                leads_to_create.append(lead)
            except Exception as e:
                logger.warning("Skipping invalid CSV row %s: %s", normalized, e)

        created = self.repo.create_many(leads_to_create, user_id)

        # ── Automation 1: Auto-score uploaded leads ───────────────────────────
        self._score_leads_background([l.id for l in created], user_id)

        return LeadUploadResponse(
            message="CSV upload complete.",
            created=len(created),
            skipped=len(leads_to_create) - len(created),
            lead_ids=[l.id for l in created],
        )
