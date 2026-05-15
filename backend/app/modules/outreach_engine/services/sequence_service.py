"""
app/modules/outreach_engine/services/sequence_service.py
──────────────────────────────────────────────────────────
Sequence scheduling and state management for multi-step outreach.

Schedule:
  Step 1 → Day 0 (immediate)
  Step 2 → Day 2
  Step 3 → Day 5
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Sequence schedule (days after campaign run) ───────────────────────────────
STEP_SCHEDULE: dict[int, int] = {
    1: 0,
    2: 2,
    3: 5,
}
MAX_STEPS = 3


class SequenceService:
    """Manages per-lead sequence state and follow-up scheduling."""

    def __init__(self, db: Session):
        self.db = db

    def should_continue(self, campaign_lead: CampaignLead) -> bool:
        """Return False if sequence should stop for this lead."""
        stop_statuses = {
            CampaignLeadStatus.REPLIED,
            CampaignLeadStatus.UNSUBSCRIBED,
            CampaignLeadStatus.FAILED,
        }
        if campaign_lead.status in stop_statuses:
            logger.debug(
                "[Sequence] stopping lead_id=%s status=%s",
                campaign_lead.lead_id, campaign_lead.status,
            )
            return False
        if campaign_lead.current_step >= MAX_STEPS:
            logger.debug(
                "[Sequence] completed all steps for lead_id=%s",
                campaign_lead.lead_id,
            )
            return False
        return True

    def get_next_step(self, campaign_lead: CampaignLead) -> Optional[int]:
        """Get the next step number, or None if sequence is done."""
        next_step = campaign_lead.current_step + 1
        if next_step > MAX_STEPS:
            return None
        return next_step

    def get_eta(self, step_number: int, base_time: Optional[datetime] = None) -> datetime:
        """Calculate when step N should execute, relative to base_time (default: now)."""
        base = base_time or datetime.now(timezone.utc)
        delay_days = STEP_SCHEDULE.get(step_number, 0)
        return base + timedelta(days=delay_days)

    def schedule_followup(self, campaign_lead_id: str, step: int, eta: datetime) -> None:
        """
        Dispatch the outreach_followup_scheduler Celery task at the given ETA.
        Import here to avoid circular imports.
        """
        from app.modules.outreach_engine.workers.outreach_tasks import outreach_followup_scheduler
        outreach_followup_scheduler.apply_async(
            args=[campaign_lead_id, step],
            eta=eta,
        )
        logger.info(
            "[Sequence] follow-up scheduled campaign_lead_id=%s step=%d eta=%s",
            campaign_lead_id, step, eta.isoformat(),
        )

    def advance_step(self, campaign_lead: CampaignLead, step: int) -> None:
        """Mark the lead as having progressed to the given step."""
        campaign_lead.current_step = step
        campaign_lead.last_contacted_at = datetime.now(timezone.utc)
        self.db.commit()
