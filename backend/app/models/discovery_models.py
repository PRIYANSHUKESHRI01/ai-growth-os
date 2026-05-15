"""
app/models/discovery_models.py
───────────────────────────────
Automation 2 ORM models — Lead Discovery & Enrichment Engine.

Tables created:
  - discovery_jobs   : per-user discovery job with metrics + progress + credit tracking
  - raw_leads        : raw payloads from source adapters
  - enriched_leads   : fully enriched, verified, normalised leads (with field-level provenance)
  - lead_signals     : per-lead audit trail (hiring, funding, engagement signals)
  - dedupe_keys      : composite dedup hashes to prevent duplicate ingestion
  - user_credits     : per-user credit balance for monetisation

IMPORTANT: Does NOT touch any Automation 1 tables.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime, Float, ForeignKey, Index, Integer, JSON,
    String, Text, UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    PENDING    = "PENDING"
    RUNNING    = "RUNNING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    CANCELLED  = "CANCELLED"


class EnrichmentStatus(str, enum.Enum):
    PENDING    = "PENDING"
    ENRICHED   = "ENRICHED"
    PARTIAL    = "PARTIAL"
    FAILED     = "FAILED"


class VerificationStatus(str, enum.Enum):
    PENDING    = "PENDING"
    VERIFIED   = "VERIFIED"
    INVALID    = "INVALID"
    UNVERIFIED = "UNVERIFIED"


class SignalType(str, enum.Enum):
    HIRING     = "hiring"
    FUNDING    = "funding"
    ENGAGEMENT = "engagement"
    GROWTH     = "growth"
    INTENT     = "intent"


class RawLeadStatus(str, enum.Enum):
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    DONE       = "DONE"
    FAILED     = "FAILED"


# ── DiscoveryJob ──────────────────────────────────────────────────────────────

class DiscoveryJob(Base, TimestampMixin):
    """
    Represents one end-to-end lead discovery run for a user.

    Enterprise additions:
      - Metrics: total_raw, total_enriched, success_count, failed_count, enrichment_rate
      - Progress: total_items, processed_items, current_stage
      - Credit tracking: credits_used
    """
    __tablename__ = "discovery_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # ── Status ───────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        SAEnum(JobStatus, name="job_status_enum"), nullable=False,
        default=JobStatus.PENDING, index=True,
    )
    current_stage: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="discovery | enrichment | verification | deduplication | normalization | handoff",
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Input ────────────────────────────────────────────────────────────────
    input_filters: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment='ICP filters: {"industry": "SaaS", "title_keywords": ["VP", "Director"], ...}',
    )
    source_adapter: Mapped[str] = mapped_column(
        String(100), nullable=False, default="mock",
        comment="Which source adapter was used",
    )

    # ── Job Metrics (Enterprise Feature #2) ──────────────────────────────────
    total_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_enriched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enrichment_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Progress Tracking (Enterprise Feature #3) ─────────────────────────────
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Credit Tracking (Enterprise Feature #1) ───────────────────────────────
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    raw_leads: Mapped[list["RawLead"]] = relationship(
        "RawLead", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DiscoveryJob id={self.id} user={self.user_id} status={self.status}>"


# ── RawLead ───────────────────────────────────────────────────────────────────

class RawLead(Base):
    """Raw payload from a source adapter — stored before any enrichment."""

    __tablename__ = "raw_leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        SAEnum(RawLeadStatus, name="raw_lead_status_enum"),
        nullable=False, default=RawLeadStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    job: Mapped["DiscoveryJob"] = relationship("DiscoveryJob", back_populates="raw_leads")

    def __repr__(self) -> str:
        return f"<RawLead id={self.id} source={self.source} job={self.job_id}>"


# ── EnrichedLead ──────────────────────────────────────────────────────────────

class EnrichedLead(Base, TimestampMixin):
    """
    Fully enriched, verified, and normalised lead.

    Enterprise additions:
      - Field-level provenance (#5): *_source + *_confidence for email, company, full_name
      - Source reliability (#4): source_reliability_score absorbed into confidence calc
    """

    __tablename__ = "enriched_leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("discovery_jobs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Contact Fields ───────────────────────────────────────────────────────
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Source Info ──────────────────────────────────────────────────────────
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Source Reliability Score (Enterprise Feature #4) ─────────────────────
    source_reliability_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0.0–1.0 reliability score of the source adapter that discovered this lead",
    )

    # ── Field-Level Provenance (Enterprise Feature #5) ────────────────────────
    email_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email_field_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    company_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_field_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    name_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name_field_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Composite Confidence Scores ───────────────────────────────────────────
    identity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    email_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    company_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Status Fields ────────────────────────────────────────────────────────
    enrichment_status: Mapped[str] = mapped_column(
        SAEnum(EnrichmentStatus, name="enrichment_status_enum"),
        nullable=False, default=EnrichmentStatus.PENDING,
    )
    verification_status: Mapped[str] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status_enum"),
        nullable=False, default=VerificationStatus.PENDING,
    )

    # ── Automation 1 Handoff ──────────────────────────────────────────────────
    automation1_lead_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True,
        comment="Set after successful handoff to Automation 1 leads table",
    )

    # ── Extra Enrichment Data ─────────────────────────────────────────────────
    enrichment_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Raw enrichment responses, provider chain results, etc.",
    )

    # ── Relationships ────────────────────────────────────────────────────────
    signals: Mapped[list["LeadSignal"]] = relationship(
        "LeadSignal", back_populates="enriched_lead", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EnrichedLead id={self.id} email={self.email} status={self.enrichment_status}>"


# ── LeadSignal ────────────────────────────────────────────────────────────────

class LeadSignal(Base):
    """
    Audit trail of signals detected for a lead.
    Signal types: hiring, funding, engagement, growth, intent.
    """

    __tablename__ = "lead_signals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("enriched_leads.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    signal_type: Mapped[str] = mapped_column(
        SAEnum(SignalType, name="signal_type_enum"), nullable=False, index=True,
    )
    signal_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    enriched_lead: Mapped["EnrichedLead"] = relationship(
        "EnrichedLead", back_populates="signals"
    )

    def __repr__(self) -> str:
        return f"<LeadSignal lead={self.lead_id} type={self.signal_type} conf={self.confidence}>"


# ── DedupeKey ─────────────────────────────────────────────────────────────────

class DedupeKey(Base):
    """
    Composite dedup hashes to prevent re-ingesting the same lead.
    Hash = SHA256(email + domain + normalized_full_name).
    """

    __tablename__ = "dedupe_keys"
    __table_args__ = (
        UniqueConstraint("hash_key", name="uq_dedupe_hash"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hash_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("enriched_leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<DedupeKey hash={self.hash_key[:12]}... lead={self.lead_id}>"


# ── UserCredit ────────────────────────────────────────────────────────────────

class UserCredit(Base, TimestampMixin):
    """
    Enterprise Feature #1 — Credit System.

    Tracks per-user discovery credits:
      - discovery_credits: deducted per job run (1 per job)
      - enrichment_credits: deducted per enriched lead
    """

    __tablename__ = "user_credits"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_credit_user"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    discovery_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enrichment_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    total_jobs_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_leads_enriched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<UserCredit user={self.user_id} "
            f"discovery={self.discovery_credits} enrichment={self.enrichment_credits}>"
        )
