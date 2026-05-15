"""
app/modules/lead_discovery/routes.py
─────────────────────────────────────
FastAPI routes for Automation 2 — Lead Discovery & Enrichment Engine.

Endpoints:
  POST /discovery/jobs              — Create a new discovery job (credit check)
  GET  /discovery/jobs              — List all jobs for the current user
  GET  /discovery/jobs/{id}         — Job status + metrics + progress
  POST /discovery/run/{id}          — Trigger job execution via Celery (async)
  POST /discovery/run-sync/{id}     — Run full pipeline synchronously (no Celery needed)
  GET  /discovery/jobs/{id}/csv     — Download discovered leads as CSV
  POST /discovery/jobs/{id}/send-to-scoring — Send leads to AI scoring engine
  GET  /discovery/leads             — List enriched leads (user-scoped, paginated)
  GET  /discovery/credits           — Current credit balance
  POST /discovery/credits/topup     — Admin: add credits (dev/testing)

All endpoints enforce multi-tenant isolation via user_id from JWT.
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.modules.lead_discovery.services.discovery_service import DiscoveryService
from app.modules.lead_discovery.services.credit_service import CreditService
from app.repositories.discovery_repository import EnrichedLeadRepository
from app.schemas.discovery import (
    DiscoveryJobCreate,
    DiscoveryJobResponse,
    DiscoveryJobListResponse,
    DiscoveryRunResponse,
    EnrichedLeadResponse,
    EnrichedLeadListResponse,
    CreditBalanceResponse,
    CreditTopUpRequest,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

discovery_router = APIRouter(prefix="/discovery", tags=["Discovery"])


# ── POST /discovery/jobs ──────────────────────────────────────────────────────

@discovery_router.post(
    "/jobs",
    response_model=DiscoveryJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead discovery job",
    description=(
        "Creates a discovery job with ICP filters. "
        "Checks credit balance before creation. "
        "Use POST /discovery/run-sync/{id} to execute immediately."
    ),
)
def create_discovery_job(
    body: DiscoveryJobCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = DiscoveryService(db)
    try:
        filters = body.to_filters()
        filters["max_results"] = body.max_results
        job = svc.create_job(
            user_id=user_id,
            input_filters=filters,
            source_adapter=body.source_adapter,
        )
        return job
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))
    except Exception as e:
        logger.error("create_discovery_job failed user=%s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to create discovery job.")


# ── GET /discovery/jobs ───────────────────────────────────────────────────────

@discovery_router.get(
    "/jobs",
    response_model=DiscoveryJobListResponse,
    summary="List discovery jobs for the current user",
)
def list_discovery_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = DiscoveryService(db)
    jobs, total = svc.list_jobs(user_id, page=page, page_size=page_size)
    return DiscoveryJobListResponse(
        total=total, page=page, page_size=page_size, jobs=jobs
    )


# ── GET /discovery/jobs/{id} ──────────────────────────────────────────────────

@discovery_router.get(
    "/jobs/{job_id}",
    response_model=DiscoveryJobResponse,
    summary="Get discovery job status, metrics, and progress",
)
def get_discovery_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = DiscoveryService(db)
    job = svc.get_job(job_id, user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery job '{job_id}' not found or not accessible.",
        )
    return job


# ── POST /discovery/run/{id} ──────────────────────────────────────────────────

@discovery_router.post(
    "/run/{job_id}",
    response_model=DiscoveryRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger discovery job execution via Celery (async)",
    description=(
        "Dispatches the 6-stage Celery pipeline. Requires a running Celery worker. "
        "If Celery is not running, use POST /discovery/run-sync/{id} instead."
    ),
)
def run_discovery_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = DiscoveryService(db)
    try:
        result = svc.trigger_job(job_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("trigger_job failed job=%s user=%s: %s", job_id, user_id, e)
        raise HTTPException(status_code=500, detail="Failed to trigger job.")


# ── POST /discovery/run-sync/{id} ─────────────────────────────────────────────

@discovery_router.post(
    "/run-sync/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Run discovery pipeline synchronously (no Celery required)",
    description=(
        "Executes the full 6-stage discovery pipeline in-process and returns "
        "discovered leads immediately. No Celery worker required."
    ),
)
def run_discovery_job_sync(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Synchronous discovery pipeline — runs everything in-process without Celery.
    This is the reliable path when Celery workers are not available.
    """
    from app.repositories.discovery_repository import (
        DiscoveryRepository, EnrichedLeadRepository as EnrichedRepo,
        DedupeRepository, CreditRepository,
    )
    from app.modules.lead_discovery.adapters import get_adapter
    from app.modules.lead_discovery.services.enrichment_service import EnrichmentService
    from app.modules.lead_discovery.services.verification_service import VerificationService
    from app.modules.lead_discovery.services.normalization_service import NormalizationService
    from app.models.discovery_models import JobStatus, DiscoveryJob, EnrichedLead
    from app.modules.lead_discovery.constants import (
        ENRICHMENT_BATCH_SIZE, ENRICHMENT_CREDIT_COST_PER_LEAD,
    )

    repo = DiscoveryRepository(db)
    enriched_repo = EnrichedRepo(db)
    dedup_repo = DedupeRepository(db)
    credit_repo = CreditRepository(db)
    normalizer = NormalizationService()

    # ── Validate job ownership ────────────────────────────────────────────────
    job = db.query(DiscoveryJob).filter_by(id=job_id, user_id=user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status not in (JobStatus.PENDING, JobStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Job is in '{job.status}' state — only PENDING or FAILED jobs can be run.",
        )

    try:
        # ── Stage 1: Discovery ────────────────────────────────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="discovery")
        db.refresh(job)

        filters = job.input_filters or {}
        adapter = get_adapter(job.source_adapter)
        raw_leads = adapter.discover(filters)
        logger.info("[Sync] Discovery: adapter=%s returned %d leads", job.source_adapter, len(raw_leads))

        # Deep-copy for DB storage (create_raw_leads pops _raw from the dicts)
        import copy
        raw_leads_for_db = copy.deepcopy(raw_leads)
        repo.create_raw_leads(job_id, raw_leads_for_db)

        repo.update_job_metrics(
            job_id,
            total_raw=len(raw_leads),
            total_items=len(raw_leads),
            processed_items=0,
            current_stage="enrichment",
        )

        # ── Stage 2: Enrichment ───────────────────────────────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="enrichment")
        enricher = EnrichmentService(redis_client=None)
        enriched = enricher.enrich_batch(raw_leads, batch_size=ENRICHMENT_BATCH_SIZE)
        logger.info("[Sync] Enrichment: %d leads enriched", len(enriched))
        repo.update_job_metrics(job_id, current_stage="verification")

        # ── Stage 3: Verification ─────────────────────────────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="verification")
        verifier = VerificationService()
        verified_leads = []
        for lead in enriched:
            try:
                v_result = verifier.verify_lead(lead)
                lead.update(v_result)
            except Exception as e:
                lead["verification_status"] = "INVALID"
                lead["rejection_reason"] = str(e)
            verified_leads.append(lead)
        logger.info("[Sync] Verification: %d leads verified", len(verified_leads))
        repo.update_job_metrics(job_id, current_stage="deduplication")

        # ── Stage 4: Deduplication ────────────────────────────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="deduplication")
        unique_leads = []
        skipped = 0
        for lead in verified_leads:
            email = lead.get("email")
            domain = lead.get("domain")
            full_name = lead.get("full_name") or (
                f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            )
            hash_key = normalizer.generate_dedupe_hash(email, domain, full_name)
            lead["_dedupe_hash"] = hash_key
            if dedup_repo.exists(hash_key):
                skipped += 1
            else:
                unique_leads.append(lead)
        logger.info("[Sync] Dedup: unique=%d skipped=%d", len(unique_leads), skipped)
        repo.update_job_metrics(job_id, current_stage="normalization")

        # ── Stage 5: Normalization + Insert ───────────────────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="normalization")
        inserted_ids = []
        success = 0
        failed = 0

        for lead in unique_leads:
            try:
                normalized = normalizer.normalize_lead(lead)
                hash_key = lead.get("_dedupe_hash")
                enrichment_meta = lead.pop("_enrichment_meta", None)
                normalized.pop("_enrichment_meta", None)
                normalized.pop("_raw", None)
                normalized.pop("_dedupe_hash", None)
                normalized["enrichment_metadata"] = enrichment_meta

                enriched_lead = enriched_repo.create(user_id, job_id, normalized)
                inserted_ids.append(enriched_lead.id)

                if hash_key:
                    try:
                        dedup_repo.register(hash_key, enriched_lead.id, user_id)
                    except Exception:
                        pass  # Race condition: another worker registered it first

                credit_repo.deduct_enrichment(user_id, ENRICHMENT_CREDIT_COST_PER_LEAD)
                success += 1
            except Exception as e:
                logger.warning("[Sync] Normalization failed for lead %s: %s", lead.get("email"), e)
                failed += 1

        repo.update_job_metrics(
            job_id,
            total_enriched=success,
            success_count=success,
            failed_count=failed,
            processed_items=len(unique_leads),
            credits_used=success * ENRICHMENT_CREDIT_COST_PER_LEAD,
            current_stage="handoff",
        )
        logger.info("[Sync] Normalization: inserted=%d failed=%d", success, failed)

        # ── Stage 6: Handoff to Automation 1 (Scoring) ───────────────────────
        repo.update_job_status(job_id, JobStatus.RUNNING, current_stage="handoff")
        from app.repositories.lead_repository import LeadRepository
        from app.schemas.lead import LeadCreate

        enriched_leads_db = (
            db.query(EnrichedLead)
            .filter(EnrichedLead.id.in_(inserted_ids), EnrichedLead.user_id == user_id)
            .all()
        )

        lead_repo = LeadRepository(db)
        lead_creates = []
        enriched_map = {}
        for el in enriched_leads_db:
            try:
                lc_data = normalizer.to_automation1_lead_create(
                    {k: getattr(el, k, None) for k in el.__table__.columns.keys()}
                )
                lc = LeadCreate(**lc_data)
                lead_creates.append(lc)
                enriched_map[el.email] = el.id
            except Exception as e:
                logger.warning("[Sync] Handoff skip lead id=%s: %s", el.id, e)

        created_leads = lead_repo.create_many(lead_creates, user_id)
        for lead in created_leads:
            enriched_id = enriched_map.get(lead.email)
            if enriched_id:
                enriched_repo.mark_automation1_handoff(enriched_id, lead.id)

        # ── Mark COMPLETED ────────────────────────────────────────────────────
        repo.update_job_status(job_id, JobStatus.COMPLETED, current_stage=None)
        logger.info(
            "[Sync] Pipeline COMPLETED job_id=%s discovered=%d enriched=%d handed_off=%d",
            job_id, len(raw_leads), success, len(created_leads),
        )

        # ── Build response with lead previews ─────────────────────────────────
        lead_previews = []
        for el in enriched_leads_db:
            lead_previews.append({
                "id":                   el.id,
                "full_name":            f"{el.first_name or ''} {el.last_name or ''}".strip(),
                "email":                el.email,
                "title":                el.title,
                "company":              el.company_name,
                "industry":             el.industry,
                "location":             el.location,
                "linkedin_url":         el.linkedin_url,
                "identity_confidence":  el.identity_confidence,
                "email_confidence":     el.email_confidence,
                "company_confidence":   el.company_confidence,
            })

        return {
            "job_id":        job_id,
            "status":        "completed",
            "discovered":    len(raw_leads),
            "enriched":      success,
            "handed_off":    len(created_leads),
            "skipped_dupes": skipped,
            "leads":         lead_previews,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[Sync] Pipeline FAILED job_id=%s: %s", job_id, exc, exc_info=True)
        try:
            repo.update_job_status(job_id, JobStatus.FAILED, error_message=str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Discovery pipeline failed: {exc}")


# ── GET /discovery/jobs/{id}/csv ──────────────────────────────────────────────

@discovery_router.get(
    "/jobs/{job_id}/csv",
    summary="Download discovered leads as CSV",
    description="Returns all enriched leads from a discovery job as a downloadable CSV file.",
    response_class=StreamingResponse,
)
def download_job_csv(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    from app.models.discovery_models import EnrichedLead, DiscoveryJob

    # Validate job ownership
    job = db.query(DiscoveryJob).filter_by(id=job_id, user_id=user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    enriched_leads = (
        db.query(EnrichedLead)
        .filter(EnrichedLead.job_id == job_id, EnrichedLead.user_id == user_id)
        .order_by(EnrichedLead.created_at.asc())
        .all()
    )

    if not enriched_leads:
        raise HTTPException(
            status_code=404,
            detail="No leads found for this job. Run the discovery pipeline first.",
        )

    # Build CSV in memory
    output = io.StringIO()
    fieldnames = [
        "full_name", "email", "title", "company_name", "industry",
        "location", "linkedin_url", "phone",
        "identity_confidence", "email_confidence", "company_confidence",
        "verification_status", "source",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for el in enriched_leads:
        writer.writerow({
            "full_name":            f"{el.first_name or ''} {el.last_name or ''}".strip(),
            "email":                el.email or "",
            "title":                el.title or "",
            "company_name":         el.company_name or "",
            "industry":             el.industry or "",
            "location":             el.location or "",
            "linkedin_url":         el.linkedin_url or "",
            "phone":                el.phone or "",
            "identity_confidence":  round(el.identity_confidence or 0, 3),
            "email_confidence":     round(el.email_confidence or 0, 3),
            "company_confidence":   round(el.company_confidence or 0, 3),
            "verification_status":  el.verification_status or "",
            "source":               el.source or "discovery",
        })

    output.seek(0)
    filename = f"leads_job_{job_id[:8]}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── POST /discovery/jobs/{id}/send-to-scoring ─────────────────────────────────

@discovery_router.post(
    "/jobs/{job_id}/send-to-scoring",
    status_code=status.HTTP_200_OK,
    summary="Send discovered leads to AI scoring engine",
    description=(
        "Runs the AI scoring engine on all leads discovered in a completed job. "
        "Results appear on the Leads dashboard with scores and explanations."
    ),
)
def send_job_to_scoring(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    from app.models.discovery_models import EnrichedLead, DiscoveryJob

    # Validate job ownership
    job = db.query(DiscoveryJob).filter_by(id=job_id, user_id=user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Fetch all leads that were handed off to automation1
    enriched_leads = (
        db.query(EnrichedLead)
        .filter(
            EnrichedLead.job_id == job_id,
            EnrichedLead.user_id == user_id,
            EnrichedLead.automation1_lead_id.isnot(None),
        )
        .all()
    )

    if not enriched_leads:
        raise HTTPException(
            status_code=404,
            detail=(
                "No leads have been handed off yet. "
                "Run POST /discovery/run-sync/{job_id} first."
            ),
        )

    lead_ids = [el.automation1_lead_id for el in enriched_leads if el.automation1_lead_id]

    try:
        # ✅ Correct import path — module is lead_scoring, not scoring_engine
        from app.modules.lead_scoring.services.scoring_service import ScoringService
        scoring_svc = ScoringService(db)

        # ✅ Correct method — score_leads() takes a list + user_id (batch scoring)
        results = scoring_svc.score_leads(lead_ids, user_id)
        scored = len(results)
        errors = len(lead_ids) - scored

        logger.info(
            "[Scoring] job_id=%s scored=%d errors=%d user=%s",
            job_id, scored, errors, user_id,
        )
        return {
            "job_id":      job_id,
            "total_leads": len(lead_ids),
            "scored":      scored,
            "errors":      errors,
            "status":      "scoring_complete",
            "message":     f"Successfully scored {scored} leads. Check the Leads dashboard.",
        }
    except ImportError as ie:
        logger.error("[Scoring] ImportError — check module path: %s", ie)
        raise HTTPException(
            status_code=500,
            detail=f"Scoring engine import failed: {ie}",
        )
    except Exception as exc:
        logger.error("[Scoring] send_to_scoring failed job=%s: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}")


# ── GET /discovery/leads ──────────────────────────────────────────────────────

@discovery_router.get(
    "/leads",
    response_model=EnrichedLeadListResponse,
    summary="List enriched leads for the current user (paginated)",
)
def list_enriched_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = EnrichedLeadRepository(db)
    leads, total = repo.get_all(user_id, page=page, page_size=page_size)
    return EnrichedLeadListResponse(
        total=total, page=page, page_size=page_size, leads=leads
    )


# ── GET /discovery/credits ────────────────────────────────────────────────────

@discovery_router.get(
    "/credits",
    response_model=CreditBalanceResponse,
    summary="Get current discovery & enrichment credit balance",
)
def get_credit_balance(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = CreditService(db)
    return svc.get_balance(user_id)


# ── POST /discovery/credits/topup ─────────────────────────────────────────────

@discovery_router.post(
    "/credits/topup",
    summary="[Admin] Add credits to current user account",
    description="Development / admin endpoint to top up credits. Protect with admin role in production.",
)
def topup_credits(
    body: CreditTopUpRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = CreditService(db)
    return svc.top_up(user_id, discovery=body.discovery, enrichment=body.enrichment)


# ── GET /discovery/test-apollo ────────────────────────────────────────────────

@discovery_router.get(
    "/test-apollo",
    summary="[Debug] Test Apollo Integration Workflow",
    description="Makes a small request to Apollo API to ensure the setup is functioning.",
)
def test_apollo():
    from app.modules.lead_discovery.adapters import get_adapter
    try:
        adapter = get_adapter("apollo")
        leads = adapter.search({"max_results": 2})
        return {"status": "ok", "leads_fetched": len(leads)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
