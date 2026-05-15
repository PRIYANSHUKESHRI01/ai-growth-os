"""
app/models/campaign_step_stats.py
───────────────────────────────────
CampaignStepStats — per-step sequence performance metrics.
Automation 3 (Outreach Engine) model.
"""
import uuid
from sqlalchemy import String, ForeignKey, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CampaignStepStats(Base, TimestampMixin):
    __tablename__ = "campaign_step_stats"
    __table_args__ = (
        UniqueConstraint("campaign_id", "step_number", name="uq_campaign_step"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Metrics ───────────────────────────────────────────────────────────
    total_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_replied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_opened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reply_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    open_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # ── Relationship ───────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="step_stats")

    def __repr__(self) -> str:
        return (
            f"<CampaignStepStats campaign={self.campaign_id} "
            f"step={self.step_number} sent={self.total_sent} replied={self.total_replied}>"
        )
