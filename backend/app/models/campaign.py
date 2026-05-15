"""
app/models/campaign.py
───────────────────────
Campaign model — scoped to user_id, tracks pipeline status.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import Base, TimestampMixin


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # ── Multi-tenant scope ──────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ── Campaign metadata ────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status", values_callable=lambda obj: [e.name for e in obj]), 
        default=CampaignStatus.PENDING, 
        nullable=False
    )
    total_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # ── Outreach Engine (Automation 3) ────────────────────────────────
    min_score_filter: Mapped[Optional[float]] = mapped_column(nullable=True, default=0.5)
    total_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_replied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_opened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="campaigns")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="campaign", cascade="all, delete-orphan"
    )
    campaign_leads: Mapped[list["CampaignLead"]] = relationship(
        "CampaignLead", back_populates="campaign", cascade="all, delete-orphan"
    )
    step_stats: Mapped[list["CampaignStepStats"]] = relationship(
        "CampaignStepStats", back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name} status={self.status}>"
