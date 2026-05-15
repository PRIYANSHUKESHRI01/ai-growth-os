"""
app/repositories/discovery_repository.py
──────────────────────────────────────────
CRUD layer for all Automation 2 tables.

Multi-tenant safety: every write/read is scoped by user_id.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.discovery_models import (
    DiscoveryJob, RawLead, EnrichedLead, LeadSignal, DedupeKey, UserCredit,
    JobStatus, EnrichmentStatus, VerificationStatus, RawLeadStatus,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── DiscoveryJob CRUD ─────────────────────────────────────────────────────────

class DiscoveryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Jobs ─────────────────────────────────────────────────────────────────

    def create_job(
        self,
        user_id: str,
        input_filters: dict,
        source_adapter: str = "mock",
    ) -> DiscoveryJob:
        job = DiscoveryJob(
            user_id=user_id,
            input_filters=input_filters,
            source_adapter=source_adapter,
            status=JobStatus.PENDING,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        logger.info("Created DiscoveryJob id=%s user=%s", job.id, user_id)
        return job

    def get_job(self, job_id: str, user_id: str) -> Optional[DiscoveryJob]:
        return (
            self.db.query(DiscoveryJob)
            .filter(DiscoveryJob.id == job_id, DiscoveryJob.user_id == user_id)
            .first()
        )

    def list_jobs(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[DiscoveryJob], int]:
        q = self.db.query(DiscoveryJob).filter(DiscoveryJob.user_id == user_id)
        total = q.count()
        jobs = (
            q.order_by(DiscoveryJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return jobs, total

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
        celery_task_id: Optional[str] = None,
    ) -> None:
        job = self.db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
        if not job:
            return
        job.status = status
        if current_stage is not None:
            job.current_stage = current_stage
        if error_message is not None:
            job.error_message = error_message
        if celery_task_id is not None:
            job.celery_task_id = celery_task_id
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_job_metrics(
        self,
        job_id: str,
        *,
        total_raw: Optional[int] = None,
        total_enriched: Optional[int] = None,
        success_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        total_items: Optional[int] = None,
        processed_items: Optional[int] = None,
        credits_used: Optional[int] = None,
        current_stage: Optional[str] = None,
    ) -> None:
        """
        Enterprise Features #2 + #3 — Update metrics and progress atomically.
        Called by Celery tasks after each pipeline stage.
        """
        job = self.db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
        if not job:
            return
        if total_raw is not None:
            job.total_raw = total_raw
            job.total_items = total_raw
        if total_enriched is not None:
            job.total_enriched = total_enriched
        if success_count is not None:
            job.success_count = success_count
        if failed_count is not None:
            job.failed_count = failed_count
        if total_items is not None:
            job.total_items = total_items
        if processed_items is not None:
            job.processed_items = processed_items
        if credits_used is not None:
            job.credits_used = credits_used
        if current_stage is not None:
            job.current_stage = current_stage
        # Recompute enrichment_rate
        if job.total_raw and job.total_enriched is not None:
            job.enrichment_rate = round(job.total_enriched / job.total_raw, 4)
        self.db.commit()

    # ── RawLeads ──────────────────────────────────────────────────────────────

    def create_raw_leads(self, job_id: str, leads: list[dict]) -> list[RawLead]:
        """Bulk-insert raw leads for a job. Returns created records."""
        records = []
        for lead in leads:
            raw_payload = lead.pop("_raw", lead.copy())  # store full raw payload
            record = RawLead(
                job_id=job_id,
                source=lead.get("source", "unknown"),
                raw_payload=raw_payload if isinstance(raw_payload, dict) else lead,
                processing_status=RawLeadStatus.PENDING,
            )
            self.db.add(record)
            records.append(record)
        self.db.commit()
        for r in records:
            self.db.refresh(r)
        return records

    def get_raw_leads_for_job(self, job_id: str) -> list[RawLead]:
        return (
            self.db.query(RawLead)
            .filter(RawLead.job_id == job_id)
            .all()
        )

    def mark_raw_lead_done(self, raw_lead_id: str) -> None:
        rl = self.db.query(RawLead).filter(RawLead.id == raw_lead_id).first()
        if rl:
            rl.processing_status = RawLeadStatus.DONE
            self.db.commit()

    def mark_raw_lead_failed(self, raw_lead_id: str) -> None:
        rl = self.db.query(RawLead).filter(RawLead.id == raw_lead_id).first()
        if rl:
            rl.processing_status = RawLeadStatus.FAILED
            self.db.commit()


# ── EnrichedLead CRUD ─────────────────────────────────────────────────────────

class EnrichedLeadRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: str, job_id: str, data: dict) -> EnrichedLead:
        lead = EnrichedLead(
            user_id=user_id,
            job_id=job_id,
            **{k: v for k, v in data.items() if hasattr(EnrichedLead, k) and v is not None},
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def get_all(
        self, user_id: str, page: int = 1, page_size: int = 50
    ) -> tuple[list[EnrichedLead], int]:
        q = self.db.query(EnrichedLead).filter(EnrichedLead.user_id == user_id)
        total = q.count()
        leads = (
            q.order_by(EnrichedLead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return leads, total

    def get_by_job(self, job_id: str, user_id: str) -> list[EnrichedLead]:
        return (
            self.db.query(EnrichedLead)
            .filter(EnrichedLead.job_id == job_id, EnrichedLead.user_id == user_id)
            .all()
        )

    def mark_automation1_handoff(self, enriched_lead_id: str, automation1_lead_id: str) -> None:
        lead = self.db.query(EnrichedLead).filter(EnrichedLead.id == enriched_lead_id).first()
        if lead:
            lead.automation1_lead_id = automation1_lead_id
            self.db.commit()

    # ── LeadSignal ────────────────────────────────────────────────────────────

    def add_signal(
        self, lead_id: str, signal_type: str, signal_value: str,
        confidence: float, source: str,
    ) -> LeadSignal:
        signal = LeadSignal(
            lead_id=lead_id,
            signal_type=signal_type,
            signal_value=signal_value,
            confidence=confidence,
            source=source,
        )
        self.db.add(signal)
        self.db.commit()
        return signal


# ── DedupeKey CRUD ────────────────────────────────────────────────────────────

class DedupeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def exists(self, hash_key: str) -> bool:
        return (
            self.db.query(DedupeKey.id)
            .filter(DedupeKey.hash_key == hash_key)
            .first()
        ) is not None

    def register(self, hash_key: str, lead_id: str, user_id: str) -> None:
        key = DedupeKey(hash_key=hash_key, lead_id=lead_id, user_id=user_id)
        self.db.add(key)
        self.db.commit()


# ── UserCredit CRUD ───────────────────────────────────────────────────────────

class CreditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, user_id: str) -> UserCredit:
        credit = (
            self.db.query(UserCredit)
            .filter(UserCredit.user_id == user_id)
            .first()
        )
        if not credit:
            credit = UserCredit(user_id=user_id)
            self.db.add(credit)
            self.db.commit()
            self.db.refresh(credit)
        return credit

    def has_discovery_credits(self, user_id: str, required: int = 1) -> bool:
        credit = self.get_or_create(user_id)
        return credit.discovery_credits >= required

    def has_enrichment_credits(self, user_id: str, required: int = 1) -> bool:
        credit = self.get_or_create(user_id)
        return credit.enrichment_credits >= required

    def deduct_discovery(self, user_id: str, amount: int = 1) -> UserCredit:
        credit = self.get_or_create(user_id)
        credit.discovery_credits = max(0, credit.discovery_credits - amount)
        credit.total_jobs_run += 1
        self.db.commit()
        logger.info("Deducted %d discovery credit(s) for user=%s. Remaining=%d",
                    amount, user_id, credit.discovery_credits)
        return credit

    def deduct_enrichment(self, user_id: str, amount: int = 1) -> UserCredit:
        credit = self.get_or_create(user_id)
        credit.enrichment_credits = max(0, credit.enrichment_credits - amount)
        credit.total_leads_enriched += amount
        self.db.commit()
        return credit

    def add_credits(self, user_id: str, discovery: int = 0, enrichment: int = 0) -> UserCredit:
        """Admin call to top up credits (e.g., after subscription payment)."""
        credit = self.get_or_create(user_id)
        credit.discovery_credits += discovery
        credit.enrichment_credits += enrichment
        self.db.commit()
        return credit
