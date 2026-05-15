"""
app/services/discovery_service.py
───────────────────────────────────
Job orchestration service for Automation 2.

Responsibilities:
  1. Create and list DiscoveryJob records (with credit check)
  2. Trigger the Celery pipeline chain
  3. Expose job status to API layer

Enterprise Feature #1 — Credit check before job creation.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.discovery_models import JobStatus
from app.repositories.discovery_repository import (
    DiscoveryRepository, CreditRepository,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Credits consumed per discovery job
DISCOVERY_CREDIT_COST = 1


class DiscoveryService:
    def __init__(self, db: Session) -> None:
        self._repo = DiscoveryRepository(db)
        self._credit_repo = CreditRepository(db)

    # ── Job Management ────────────────────────────────────────────────────────

    def create_job(
        self,
        user_id: str,
        input_filters: dict[str, Any],
        source_adapter: str = "mock",
    ) -> dict[str, Any]:
        """
        Enterprise Feature #1 — Check credits before creating job.
        Returns job dict or raises ValueError on insufficient credits.
        """
        # Credit check
        if not self._credit_repo.has_discovery_credits(user_id, required=DISCOVERY_CREDIT_COST):
            raise ValueError(
                f"Insufficient discovery credits. "
                f"Please top up your account to continue."
            )

        job = self._repo.create_job(
            user_id=user_id,
            input_filters=input_filters,
            source_adapter=source_adapter,
        )
        logger.info("DiscoveryJob created: id=%s user=%s adapter=%s", job.id, user_id, source_adapter)
        return self._job_to_dict(job)

    def get_job(self, job_id: str, user_id: str) -> Optional[dict[str, Any]]:
        job = self._repo.get_job(job_id, user_id)
        return self._job_to_dict(job) if job else None

    def list_jobs(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        jobs, total = self._repo.list_jobs(user_id, page, page_size)
        return [self._job_to_dict(j) for j in jobs], total

    def trigger_job(self, job_id: str, user_id: str) -> dict[str, Any]:
        """
        Dispatch the Celery pipeline chain for this job.
        Deducts one discovery credit before dispatching.
        """
        job = self._repo.get_job(job_id, user_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found or not accessible.")

        if job.status not in (JobStatus.PENDING, JobStatus.FAILED):
            raise ValueError(
                f"Job '{job_id}' is in status '{job.status}' — "
                f"only PENDING or FAILED jobs can be triggered."
            )

        # Deduct credit
        self._credit_repo.deduct_discovery(user_id, amount=DISCOVERY_CREDIT_COST)

        # Dispatch Celery task (lazy import to avoid circular deps)
        from app.modules.lead_discovery.workers.discovery_tasks import task_run_discovery_job
        result = task_run_discovery_job.apply_async(
            args=[job_id, user_id],
            queue="discovery",
        )

        # Record task ID
        self._repo.update_job_status(
            job_id=job_id,
            status=JobStatus.RUNNING,
            current_stage="discovery",
            celery_task_id=result.id,
        )

        logger.info(
            "DiscoveryJob dispatched: job_id=%s celery_task_id=%s user=%s",
            job_id, result.id, user_id,
        )
        return {
            "job_id": job_id,
            "celery_task_id": result.id,
            "status": "RUNNING",
            "message": "Discovery pipeline started.",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _job_to_dict(job: Any) -> dict[str, Any]:
        return {
            "id":               job.id,
            "user_id":          job.user_id,
            "status":           job.status,
            "current_stage":    job.current_stage,
            "source_adapter":   job.source_adapter,
            "input_filters":    job.input_filters,
            "celery_task_id":   job.celery_task_id,
            "error_message":    job.error_message,
            # Metrics (Enterprise #2)
            "total_raw":        job.total_raw,
            "total_enriched":   job.total_enriched,
            "success_count":    job.success_count,
            "failed_count":     job.failed_count,
            "enrichment_rate":  job.enrichment_rate,
            # Progress (Enterprise #3)
            "total_items":      job.total_items,
            "processed_items":  job.processed_items,
            # Credit (Enterprise #1)
            "credits_used":     job.credits_used,
            # Timestamps
            "created_at":       job.created_at,
            "started_at":       job.started_at,
            "completed_at":     job.completed_at,
        }
