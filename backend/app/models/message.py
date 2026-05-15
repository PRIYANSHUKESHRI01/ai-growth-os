"""
app/models/message.py
──────────────────────
Message model — generated outreach email per lead per campaign.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Text, DateTime, Enum as SAEnum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import Base, TimestampMixin


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

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
    # ── Content ───────────────────────────────────────────────────────────
    subject: Mapped[str] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    step_number: Mapped[int] = mapped_column(default=1, nullable=False)
    # ── Delivery ──────────────────────────────────────────────────────────
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus, name="message_status"), default=MessageStatus.PENDING, nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sendgrid_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sendgrid_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # ── Open tracking ────────────────────────────────────────────────────
    is_opened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="messages")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} lead_id={self.lead_id} status={self.status}>"
