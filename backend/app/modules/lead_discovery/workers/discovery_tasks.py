"""
app/workers/discovery_tasks.py
────────────────────────────────
Automation 2 — 6-step async Celery pipeline.

Pipeline stages:
  1. task_run_discovery_job   — root orchestrator + credit deduction
  2. task_enrichment           — waterfall enrichment via providers
  3. task_verification         — email/domain/confidence validation
  4. task_deduplication        — composite hash check
  5. task_normalization        — canonical schema + insert enriched_leads
  6. task_handoff              — push to Automation 1 leads table

Enterprise Features:
  #1 — Credits deducted per enriched lead
  #2 — Metrics (total_raw, success_count, etc.) updated after each stage
  #3 — Progress (processed_items, current_stage) updated atomically

Architecture add-ons:
  #2 — Pipeline state machine via DiscoveryJob.status + current_stage
  #3 — Batch processing with configurable chunk size
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)

from app.modules.lead_discovery.constants import (
    ENRICHMENT_BATCH_SIZE,
    ENRICHMENT_CREDIT_COST_PER_LEAD,
)


# ── Task 1: Root Orchestrator ──────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.run_job",
    max_retries=2,
    default_retry_delay=30,
    queue="discovery",
)
def task_run_discovery_job(self, job_id: str, user_id: str) -> dict:
    """
    Stage 1 — Discovery.
    1. Fetch job + ICP filters
    2. Instantiate the correct source adapter
    3. Run adapter.discover(filters) → list of raw lead dicts
    4. Bulk-insert into raw_leads table
    5. Update job metrics + progress
    6. Dispatch enrichment task (with retry-safe chaining)
    """
    print(f"Discovery task started for job_id={job_id}")
    logger.info("Task received: %s", self.request.id)
    logger.info("[Discovery] Starting job_id=%s user_id=%s", job_id, user_id)
    db = SessionLocal()
    try:
        from app.repositories.discovery_repository import DiscoveryRepository
        from app.models.discovery_models import JobStatus, DiscoveryJob
        from app.modules.lead_discovery.adapters import get_adapter

        repo = DiscoveryRepository(db)

        # Update status → RUNNING
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="discovery")

        job = db.query(DiscoveryJob).filter_by(id=job_id).first()
        if not job:
            logger.error("[Discovery] Job not found: job_id=%s", job_id)
            return {"status": "failed", "job_id": job_id}

        filters = job.input_filters or {}
        adapter = get_adapter(job.source_adapter)

        # Run discovery
        raw_leads = adapter.discover(filters)
        logger.info("[Discovery] Adapter=%s returned %d leads", job.source_adapter, len(raw_leads))

        # Store raw leads
        repo.create_raw_leads(job_id, raw_leads)

        # Update metrics (Enterprise #2)
        repo.update_job_metrics(
            job_id,
            total_raw=len(raw_leads),
            total_items=len(raw_leads),
            processed_items=0,
            current_stage="enrichment",
        )

        # ── Dispatch enrichment ───────────────────────────────────────────────
        task_enrichment.apply_async(
            args=[job_id, user_id, raw_leads],
            queue="discovery",
        )

        return {"status": "discovery_complete", "job_id": job_id, "leads_found": len(raw_leads)}

    except Exception as exc:
        logger.error("[Discovery] task_run_discovery_job failed job_id=%s: %s", job_id, exc)
        try:
            from app.repositories.discovery_repository import DiscoveryRepository
            from app.models.discovery_models import JobStatus
            repo = DiscoveryRepository(db)
            repo.update_job_status(job_id, JobStatus.FAILED, error_message=str(exc))
        except Exception:
            pass
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Task 2: Waterfall Enrichment ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.enrichment",
    max_retries=3,
    default_retry_delay=15,
    queue="discovery",
)
def task_enrichment(self, job_id: str, user_id: str, raw_leads: list[dict]) -> dict:
    """
    Stage 2 — Enrichment.
    Runs waterfall enrichment on each raw lead in batches.
    Updates job progress after every lead (Enterprise #3).
    """
    logger.info("[Enrichment] Starting job_id=%s leads=%d", job_id, len(raw_leads))
    db = SessionLocal()
    try:
        from app.modules.lead_discovery.services.enrichment_service import EnrichmentService
        from app.repositories.discovery_repository import DiscoveryRepository
        from app.models.discovery_models import JobStatus

        repo = DiscoveryRepository(db)
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="enrichment")

        # Connect to Redis for circuit breaker (optional)
        redis_client = _get_redis_client()
        enricher = EnrichmentService(redis_client=redis_client)

        enriched = enricher.enrich_batch(raw_leads, batch_size=ENRICHMENT_BATCH_SIZE)

        logger.info("[Enrichment] Completed job_id=%s enriched=%d", job_id, len(enriched))

        # Update progress (Enterprise #3)
        repo.update_job_metrics(job_id, current_stage="verification")

        # Dispatch verification
        task_verification.apply_async(
            args=[job_id, user_id, enriched],
            queue="discovery",
        )

        return {"status": "enrichment_complete", "job_id": job_id, "enriched": len(enriched)}

    except Exception as exc:
        logger.error("[Enrichment] Failed job_id=%s: %s", job_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_job_failed(job_id, str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Task 3: Verification ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.verification",
    max_retries=2,
    default_retry_delay=10,
    queue="discovery",
)
def task_verification(self, job_id: str, user_id: str, enriched_leads: list[dict]) -> dict:
    """
    Stage 3 — Verification.
    Validates email, company, and computes 3 composite confidence scores.
    """
    logger.info("[Verification] Starting job_id=%s leads=%d", job_id, len(enriched_leads))
    db = SessionLocal()
    try:
        from app.modules.lead_discovery.services.verification_service import VerificationService
        from app.repositories.discovery_repository import DiscoveryRepository
        from app.models.discovery_models import JobStatus

        repo = DiscoveryRepository(db)
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="verification")

        verifier = VerificationService()
        verified_leads = []

        for lead in enriched_leads:
            try:
                v_result = verifier.verify_lead(lead)
                lead.update(v_result)
                verified_leads.append(lead)
            except Exception as e:
                logger.warning("[Verification] Lead failed: %s — %s", lead.get("email"), e)
                lead["verification_status"] = "INVALID"
                lead["rejection_reason"] = str(e)
                verified_leads.append(lead)

        repo.update_job_metrics(job_id, current_stage="deduplication")

        # Dispatch deduplication
        task_deduplication.apply_async(
            args=[job_id, user_id, verified_leads],
            queue="discovery",
        )

        return {"status": "verification_complete", "job_id": job_id, "verified": len(verified_leads)}

    except Exception as exc:
        logger.error("[Verification] Failed job_id=%s: %s", job_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_job_failed(job_id, str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Task 4: Deduplication ──────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.deduplication",
    max_retries=2,
    default_retry_delay=10,
    queue="discovery",
)
def task_deduplication(self, job_id: str, user_id: str, leads: list[dict]) -> dict:
    """
    Stage 4 — Deduplication.
    Generates SHA256 composite hash (email + domain + name).
    Skips leads whose hash already exists in dedupe_keys.
    """
    logger.info("[Dedup] Starting job_id=%s leads=%d", job_id, len(leads))
    db = SessionLocal()
    try:
        from app.modules.lead_discovery.services.normalization_service import NormalizationService
        from app.repositories.discovery_repository import DiscoveryRepository, DedupeRepository
        from app.models.discovery_models import JobStatus

        repo = DiscoveryRepository(db)
        dedup_repo = DedupeRepository(db)
        normalizer = NormalizationService()

        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="deduplication")

        unique_leads = []
        skipped = 0

        for lead in leads:
            email = lead.get("email")
            domain = lead.get("domain")
            full_name = lead.get("full_name") or (
                f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            )
            hash_key = normalizer.generate_dedupe_hash(email, domain, full_name)
            lead["_dedupe_hash"] = hash_key

            if dedup_repo.exists(hash_key):
                skipped += 1
                logger.debug("[Dedup] Skipping duplicate hash=%s email=%s", hash_key[:12], email)
            else:
                unique_leads.append(lead)

        logger.info(
            "[Dedup] job_id=%s unique=%d skipped=%d",
            job_id, len(unique_leads), skipped,
        )

        repo.update_job_metrics(job_id, current_stage="normalization")

        # Dispatch normalization
        task_normalization.apply_async(
            args=[job_id, user_id, unique_leads],
            queue="discovery",
        )

        return {
            "status": "dedup_complete",
            "job_id": job_id,
            "unique": len(unique_leads),
            "skipped": skipped,
        }

    except Exception as exc:
        logger.error("[Dedup] Failed job_id=%s: %s", job_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_job_failed(job_id, str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Task 5: Normalization + Insert EnrichedLeads ──────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.normalization",
    max_retries=2,
    default_retry_delay=10,
    queue="discovery",
)
def task_normalization(self, job_id: str, user_id: str, leads: list[dict]) -> dict:
    """
    Stage 5 — Normalization.
    Cleans data, inserts into enriched_leads, registers dedupe hashes,
    deducts enrichment credits (Enterprise #1).
    """
    logger.info("[Normalization] Starting job_id=%s leads=%d", job_id, len(leads))
    db = SessionLocal()
    try:
        from app.modules.lead_discovery.services.normalization_service import NormalizationService
        from app.repositories.discovery_repository import (
            DiscoveryRepository, EnrichedLeadRepository, DedupeRepository, CreditRepository,
        )
        from app.models.discovery_models import JobStatus

        repo = DiscoveryRepository(db)
        enriched_repo = EnrichedLeadRepository(db)
        dedup_repo = DedupeRepository(db)
        credit_repo = CreditRepository(db)
        normalizer = NormalizationService()

        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="normalization")

        inserted_ids = []
        success = 0
        failed = 0

        for i, lead in enumerate(leads):
            try:
                normalized = normalizer.normalize_lead(lead)
                hash_key = lead.get("_dedupe_hash")

                # Build enrichment metadata from provider chain
                enrichment_meta = lead.pop("_enrichment_meta", None)
                normalized.pop("_enrichment_meta", None)
                normalized.pop("_raw", None)
                normalized.pop("_dedupe_hash", None)

                normalized["enrichment_metadata"] = enrichment_meta

                enriched_lead = enriched_repo.create(user_id, job_id, normalized)
                inserted_ids.append(enriched_lead.id)

                # Register dedup hash
                if hash_key:
                    try:
                        dedup_repo.register(hash_key, enriched_lead.id, user_id)
                    except Exception:
                        pass  # Race condition: another worker registered it first

                # Deduct enrichment credit (Enterprise #1)
                credit_repo.deduct_enrichment(user_id, ENRICHMENT_CREDIT_COST_PER_LEAD)

                success += 1

                # Update progress (Enterprise #3)
                if (i + 1) % 10 == 0 or i == len(leads) - 1:
                    repo.update_job_metrics(
                        job_id,
                        processed_items=i + 1,
                        current_stage="normalization",
                    )

            except Exception as e:
                logger.warning("[Normalization] Lead failed: %s — %s", lead.get("email"), e)
                failed += 1

        # Final metrics update (Enterprise #2)
        repo.update_job_metrics(
            job_id,
            total_enriched=success,
            success_count=success,
            failed_count=failed,
            processed_items=len(leads),
            credits_used=success * ENRICHMENT_CREDIT_COST_PER_LEAD,
            current_stage="handoff",
        )

        # Dispatch handoff
        task_handoff.apply_async(
            args=[job_id, user_id, inserted_ids],
            queue="discovery",
        )

        return {
            "status": "normalization_complete",
            "job_id": job_id,
            "inserted": success,
            "failed": failed,
        }

    except Exception as exc:
        logger.error("[Normalization] Failed job_id=%s: %s", job_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_job_failed(job_id, str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Task 6: Automation 1 Handoff ──────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="discovery.handoff",
    max_retries=3,
    default_retry_delay=20,
    queue="discovery",
)
def task_handoff(self, job_id: str, user_id: str, enriched_lead_ids: list[str]) -> dict:
    """
    Stage 6 — Automation 1 Handoff.
    Converts enriched leads into Automation 1's LeadCreate schema
    and inserts them via LeadRepository.create_many() — the same path
    used by CSV and JSON uploads. Zero changes to Automation 1 code.
    """
    logger.info("[Handoff] Starting job_id=%s leads=%d", job_id, len(enriched_lead_ids))
    db = SessionLocal()
    try:
        from app.repositories.discovery_repository import EnrichedLeadRepository
        from app.repositories.discovery_repository import DiscoveryRepository
        from app.repositories.lead_repository import LeadRepository
        from app.schemas.lead import LeadCreate
        from app.modules.lead_discovery.services.normalization_service import NormalizationService
        from app.models.discovery_models import JobStatus

        repo = DiscoveryRepository(db)
        enriched_repo = EnrichedLeadRepository(db)
        lead_repo = LeadRepository(db)
        normalizer = NormalizationService()

        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="handoff")

        # Fetch enriched leads by IDs
        from app.models.discovery_models import EnrichedLead
        enriched_leads = (
            db.query(EnrichedLead)
            .filter(EnrichedLead.id.in_(enriched_lead_ids), EnrichedLead.user_id == user_id)
            .all()
        )

        # Convert to LeadCreate payloads
        lead_creates = []
        enriched_map = {}
        for el in enriched_leads:
            payload = {
                "email":        el.email,
                "first_name":   el.first_name,
                "last_name":    el.last_name,
                "company_name": el.company_name,
                "company":      el.company_name,
                "title":        el.title,
                "industry":     el.industry,
                "source":       f"discovery:{el.source or 'auto'}",
                "linkedin_url": el.linkedin_url,
                "identity_confidence": el.identity_confidence,
                "email_confidence": el.email_confidence,
                "company_confidence": el.company_confidence,
            }
            try:
                lc_data = normalizer.to_automation1_lead_create(
                    {k: getattr(el, k, None) for k in el.__table__.columns.keys()}
                )
                lc = LeadCreate(**lc_data)
                lead_creates.append(lc)
                enriched_map[el.email] = el.id
            except Exception as e:
                logger.warning("[Handoff] Skip lead id=%s: %s", el.id, e)

        # Bulk insert via Automation 1's own LeadRepository (no Automation 1 code modified)
        created_leads = lead_repo.create_many(lead_creates, user_id)

        # Back-fill automation1_lead_id
        for lead in created_leads:
            enriched_id = enriched_map.get(lead.email)
            if enriched_id:
                enriched_repo.mark_automation1_handoff(enriched_id, lead.id)

        # Mark job COMPLETED (Enterprise #2 — pipeline state machine)
        from app.models.discovery_models import JobStatus
        repo.update_job_status(job_id, JobStatus.COMPLETED, current_stage=None)

        logger.info(
            "[Handoff] Complete job_id=%s handed_off=%d",
            job_id, len(created_leads),
        )
        return {
            "status": "handoff_complete",
            "job_id": job_id,
            "handed_off": len(created_leads),
        }

    except Exception as exc:
        logger.error("[Handoff] Failed job_id=%s: %s", job_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_job_failed(job_id, str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        db.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_redis_client():
    """Return Redis client for circuit breaker. Returns None if unavailable."""
    try:
        import redis
        from app.core.config import get_settings
        settings = get_settings()
        import ssl
        client = redis.from_url(settings.REDIS_URL, ssl_cert_reqs=ssl.CERT_NONE)
        client.ping()
        return client
    except Exception:
        logger.warning("[Discovery] Redis unavailable — circuit breaker disabled")
        return None


def _mark_job_failed(job_id: str, error: str) -> None:
    """Best-effort: mark job as FAILED in DB."""
    try:
        db = SessionLocal()
        from app.repositories.discovery_repository import DiscoveryRepository
        from app.models.discovery_models import JobStatus
        DiscoveryRepository(db).update_job_status(
            job_id, JobStatus.FAILED, error_message=error
        )
        db.close()
    except Exception:
        pass
