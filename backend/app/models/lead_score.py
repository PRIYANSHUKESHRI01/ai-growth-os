"""
app/models/lead_score.py
─────────────────────────
Lead scoring results — one-to-one with Lead.
v2.0: Two-layer scoring (value + confidence) with explanations.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # ── Scores ───────────────────────────────────────────────────────────
    reply_probability: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_probability: Mapped[float] = mapped_column(Float, nullable=False)
    value_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    signal_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Stability Layer
    previous_score: Mapped[float] = mapped_column(Float, nullable=True)
    raw_score: Mapped[float] = mapped_column(Float, nullable=True)
    smoothed_score: Mapped[float] = mapped_column(Float, nullable=True)
    
    final_score: Mapped[float] = mapped_column(Float, nullable=False)  # Is equal to smoothed_score if smoothing applied
    model_version: Mapped[str] = mapped_column(String(50), default="v2.0", nullable=False)

    # ── Explanation ──────────────────────────────────────────────────────
    explanation: Mapped[str] = mapped_column(Text, nullable=True)  # JSON-encoded dict (value_factors, conf_factors, reasoning)

    # ── Classification ───────────────────────────────────────────────────
    tag: Mapped[str] = mapped_column(String(20), nullable=True)  # HOT 🔥 / WARM / COLD
    intent_label: Mapped[str] = mapped_column(String(50), nullable=True)  # Very High Intent, etc.

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────
    lead: Mapped["Lead"] = relationship("Lead", back_populates="score")

    def __repr__(self) -> str:
        return f"<LeadScore lead_id={self.lead_id} final={self.final_score:.3f} value={self.value_score:.3f} conf={self.confidence_score:.3f}>"
