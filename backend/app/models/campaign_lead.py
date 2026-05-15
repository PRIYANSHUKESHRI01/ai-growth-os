"""
app/models/campaign_lead.py
────────────────────────────
CampaignLead — tracks per-lead state within an outreach sequence.
Automation 3 (Outreach Engine) model.
"""
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import String, ForeignKey, DateTime, Integer, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CampaignLeadStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    REPLIED = "replied"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"
    SKIPPED = "skipped"


class ReplyType(str, enum.Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MEETING_REQUEST = "meeting_request"
    OBJECTION = "objection"
    UNKNOWN = "unknown"


class CampaignLead(Base, TimestampMixin):
    __tablename__ = "campaign_leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # ── Foreign keys ──────────────────────────────────────────────────────
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ── Sequence state ────────────────────────────────────────────────────
    status: Mapped[CampaignLeadStatus] = mapped_column(
        SAEnum(CampaignLeadStatus, name="campaign_lead_status", values_callable=lambda obj: [e.name for e in obj]),
        default=CampaignLeadStatus.PENDING,
        nullable=False,
        index=True,
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Reply intelligence ─────────────────────────────────────────────────
    reply_type: Mapped[Optional[ReplyType]] = mapped_column(
        SAEnum(ReplyType, name="reply_type", values_callable=lambda obj: [e.name for e in obj]), nullable=True
    )
    reply_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="campaign_leads")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="campaign_leads")

    def __repr__(self) -> str:
        return (
            f"<CampaignLead campaign={self.campaign_id} "
            f"lead={self.lead_id} step={self.current_step} status={self.status}>"
        )
