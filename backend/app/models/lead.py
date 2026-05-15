"""
app/models/lead.py
───────────────────
Lead model — scoped to user_id for multi-tenant isolation.
"""
import uuid
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # ── Multi-tenant scope ──────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ── Lead data ───────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    company_size: Mapped[str] = mapped_column(String(50), nullable=True)  # e.g. "1-10", "11-50"
    source: Mapped[str] = mapped_column(String(100), nullable=True)      # e.g. "csv_upload", "api"
    linkedin_url: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="leads")
    score: Mapped["LeadScore"] = relationship(
        "LeadScore", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="lead", cascade="all, delete-orphan"
    )
    campaign_leads: Mapped[list["CampaignLead"]] = relationship(
        "CampaignLead", back_populates="lead", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lead id={self.id} email={self.email} user_id={self.user_id}>"
