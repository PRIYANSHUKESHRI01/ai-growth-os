"""
app/modules/outreach_engine/services/safety_service.py
────────────────────────────────────────────────────────
Campaign safety system:
  - Auto-pauses campaign if bounce rate > 20%
  - Auto-pauses campaign if negative reply rate > 40%

Called after each batch send cycle.
"""
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_lead import CampaignLead, CampaignLeadStatus, ReplyType
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
BOUNCE_RATE_THRESHOLD = 0.20       # 20% failure rate → pause
NEGATIVE_REPLY_RATE_THRESHOLD = 0.40  # 40% not-interested rate → pause


class SafetyService:
    """
    Monitors campaign health and auto-pauses on unsafe sending patterns.
    """

    def __init__(self, db: Session):
        self.db = db

    def check_and_enforce(self, campaign_id: str) -> bool:
        """
        Run all safety checks for a campaign.
        Returns True if the campaign was paused (unsafe), False if healthy.
        """
        campaign = self.db.get(Campaign, campaign_id)
        if not campaign or campaign.status != CampaignStatus.RUNNING:
            return False

        # ── Bounce rate check ─────────────────────────────────────────────
        if self._check_bounce_rate(campaign):
            logger.warning(
                "[Safety] Campaign paused (bounce rate exceeded) campaign_id=%s", campaign_id
            )
            self._pause(campaign, "Auto-paused: bounce rate exceeded 20%")
            return True

        # ── Negative reply rate check ─────────────────────────────────────
        if self._check_negative_reply_rate(campaign):
            logger.warning(
                "[Safety] Campaign paused (negative reply rate exceeded) campaign_id=%s", campaign_id
            )
            self._pause(campaign, "Auto-paused: negative reply rate exceeded 40%")
            return True

        return False

    def _check_bounce_rate(self, campaign: Campaign) -> bool:
        all_leads = (
            self.db.query(CampaignLead)
            .filter(CampaignLead.campaign_id == campaign.id)
            .all()
        )
        if len(all_leads) < 5:  # Not enough data to judge yet
            return False

        failed = sum(1 for cl in all_leads if cl.status == CampaignLeadStatus.FAILED)
        rate = failed / len(all_leads)
        if rate > BOUNCE_RATE_THRESHOLD:
            logger.info(
                "[Safety] Bounce rate=%.1f%% campaign_id=%s",
                rate * 100, campaign.id,
            )
            return True
        return False

    def _check_negative_reply_rate(self, campaign: Campaign) -> bool:
        replied_leads = (
            self.db.query(CampaignLead)
            .filter(
                CampaignLead.campaign_id == campaign.id,
                CampaignLead.status == CampaignLeadStatus.REPLIED,
            )
            .all()
        )
        if len(replied_leads) < 3:  # Not enough replies to judge yet
            return False

        negative = sum(
            1 for cl in replied_leads
            if cl.reply_type == ReplyType.NOT_INTERESTED
        )
        rate = negative / len(replied_leads)
        if rate > NEGATIVE_REPLY_RATE_THRESHOLD:
            logger.info(
                "[Safety] Negative reply rate=%.1f%% campaign_id=%s",
                rate * 100, campaign.id,
            )
            return True
        return False

    def _pause(self, campaign: Campaign, reason: str) -> None:
        campaign.status = CampaignStatus.PAUSED
        campaign.error_message = reason
        self.db.commit()
