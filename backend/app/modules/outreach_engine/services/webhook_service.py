"""
app/modules/outreach_engine/services/webhook_service.py
─────────────────────────────────────────────────────────
Handles inbound webhooks for email tracking:
  1. Tracking pixel open events  (/outreach/webhook/open)
  2. SendGrid event webhook       (/outreach/webhook/events)
     - delivered
     - open
     - bounce / dropped
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
from app.models.campaign_step_stats import CampaignStepStats
from app.models.message import Message, MessageStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

# 1×1 transparent GIF bytes
_TRACKING_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


class WebhookService:
    """Handles email open tracking and SendGrid delivery events."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Tracking Pixel ────────────────────────────────────────────────────────

    @staticmethod
    def get_tracking_gif() -> bytes:
        """Return the 1×1 transparent GIF payload for tracking pixel responses."""
        return _TRACKING_GIF

    def record_open(self, message_id: str) -> bool:
        """
        Mark the message as opened (idempotent).
        Updates both Message and Campaign.total_opened / CampaignStepStats.total_opened.
        Returns True if this is the first open, False if already opened.
        """
        msg: Message | None = (
            self.db.query(Message).filter(Message.id == message_id).first()
        )
        if not msg:
            logger.warning("record_open: message_id=%s not found", message_id)
            return False

        if msg.is_opened:
            return False  # Already counted — idempotent

        # Mark message
        msg.is_opened = True
        msg.opened_at = datetime.now(timezone.utc)
        if msg.status == MessageStatus.SENT or msg.status == MessageStatus.DELIVERED:
            msg.status = MessageStatus.OPENED

        # Increment campaign counter
        campaign: Campaign | None = (
            self.db.query(Campaign).filter(Campaign.id == msg.campaign_id).first()
        )
        if campaign:
            campaign.total_opened = (campaign.total_opened or 0) + 1

        # Increment step stat counter
        step_stat: CampaignStepStats | None = (
            self.db.query(CampaignStepStats)
            .filter(
                CampaignStepStats.campaign_id == msg.campaign_id,
                CampaignStepStats.step_number == msg.step_number,
            )
            .first()
        )
        if step_stat:
            step_stat.total_opened = (step_stat.total_opened or 0) + 1
            if step_stat.total_sent > 0:
                step_stat.open_rate = round(
                    step_stat.total_opened / step_stat.total_sent, 4
                )

        try:
            self.db.commit()
            logger.info(
                "Open recorded: message=%s campaign=%s step=%s",
                message_id, msg.campaign_id, msg.step_number,
            )
            return True
        except Exception as e:
            self.db.rollback()
            logger.error("record_open DB error: %s", e)
            return False

    # ── SendGrid Events ───────────────────────────────────────────────────────

    def process_sendgrid_events(self, events: List[Dict[str, Any]]) -> dict:
        """
        Process a batch of SendGrid event objects.
        Expected fields per event: event, sg_message_id, timestamp (unix)
        Supported events: delivered, open, bounce, dropped
        """
        processed = {"delivered": 0, "opened": 0, "bounced": 0, "unknown": 0}

        for event in events:
            event_type = event.get("event", "").lower()
            sg_id = event.get("sg_message_id", "").split(".")[0]  # strip suffix

            if not sg_id:
                processed["unknown"] += 1
                continue

            msg: Message | None = (
                self.db.query(Message)
                .filter(Message.sendgrid_message_id == sg_id)
                .first()
            )
            if not msg:
                logger.debug("SendGrid event for unknown msg sg_id=%s event=%s", sg_id, event_type)
                processed["unknown"] += 1
                continue

            if event_type == "delivered":
                self._handle_delivered(msg)
                processed["delivered"] += 1

            elif event_type == "open":
                self.record_open(msg.id)
                processed["opened"] += 1

            elif event_type in ("bounce", "dropped", "blocked", "spamreport"):
                self._handle_bounce(msg)
                processed["bounced"] += 1

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error("process_sendgrid_events commit error: %s", e)

        logger.info("SendGrid events processed: %s", processed)
        return processed

    def _handle_delivered(self, msg: Message) -> None:
        if msg.status == MessageStatus.SENT:
            msg.status = MessageStatus.DELIVERED

    def _handle_bounce(self, msg: Message) -> None:
        if msg.status not in (MessageStatus.REPLIED,):
            msg.status = MessageStatus.FAILED
            # Update campaign_lead status to failed if currently pending/sent
            cl: CampaignLead | None = (
                self.db.query(CampaignLead)
                .filter(
                    CampaignLead.campaign_id == msg.campaign_id,
                    CampaignLead.lead_id == msg.lead_id,
                )
                .first()
            )
            if cl and cl.status in (
                CampaignLeadStatus.PENDING, CampaignLeadStatus.SENT
            ):
                cl.status = CampaignLeadStatus.FAILED

    # ── HMAC Signature Verification (optional, for production) ───────────────

    @staticmethod
    def verify_sendgrid_signature(
        payload: bytes, timestamp: str, signature: str
    ) -> bool:
        """
        Verify SendGrid's ECDSA webhook signature.
        Only enforced when SENDGRID_WEBHOOK_KEY env var is set.
        """
        key = os.getenv("SENDGRID_WEBHOOK_KEY", "")
        if not key:
            return True  # Skip verification in dev/demo mode
        try:
            expected = hmac.new(
                key.encode(), timestamp.encode() + payload, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False
