"""
app/api/routes.py
──────────────────
All API route definitions — v2.0.

Endpoints:
  POST /leads/upload         — ingest leads (CSV or JSON)
  GET  /leads                — list leads (paginated, user-scoped)
  GET  /leads/{id}/explanation — get score explanation for a lead
  POST /campaign/run         — launch a campaign
  GET  /campaign/status      — get campaign status
  GET  /campaign/analytics   — get campaign analytics (scores, threshold)
  GET  /health               — health check
"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.modules.lead_scoring.services.lead_service import LeadService
from app.modules.lead_scoring.services.campaign_service import CampaignService
from app.repositories.lead_repository import LeadRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.score_repository import ScoreRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.lead import LeadResponse, LeadListResponse, LeadUploadResponse, DashboardStatsResponse
from app.schemas.score import LeadExplanationResponse, compute_lead_tag, compute_intent_label
from app.schemas.campaign import (
    CampaignRunRequest,
    CampaignRunResponse,
    CampaignStatusResponse,
    CampaignAnalyticsResponse,
    CampaignListResponse,
)
from app.models.message import MessageStatus
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@router.get(
    "/dashboard/stats",
    response_model=DashboardStatsResponse,
    tags=["Dashboard"],
    summary="Get aggregated statistics for the dashboard",
)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns high-level growth metrics:
    - total_leads: total leads ingested
    - avg_score: mean intelligence score across all leads
    - hot_leads_count: leads with final_score >= 0.8
    - campaigns_count: total campaigns created
    """
    lead_repo = LeadRepository(db)
    score_repo = ScoreRepository(db)
    campaign_repo = CampaignRepository(db)

    # 1. Total Leads
    total_leads = lead_repo.count_by_user(user_id)

    # 2. Avg Score & Hot Leads
    all_leads, _ = lead_repo.get_all(user_id=user_id, page=1, page_size=100000, with_scores=False)
    lead_ids = [l.id for l in all_leads]

    avg_score = 0.0
    hot_count = 0
    if lead_ids:
        avg_score = score_repo.get_avg_score(lead_ids)
        hot_count = len(score_repo.get_scored_lead_ids_above_threshold(lead_ids, threshold=0.8))

    # 3. Campaigns Count
    _, campaigns_count = campaign_repo.get_all(user_id=user_id, page=1, page_size=1)

    return DashboardStatsResponse(
        total_leads=total_leads,
        avg_score=avg_score,
        hot_leads_count=hot_count,
        campaigns_count=campaigns_count,
    )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
def health_check():
    """Service health probe — used by load balancers and orchestrators."""
    return {"status": "healthy", "service": "AI Growth OS", "scoring_engine": "v2.0"}


# ── Score All UNSCORED Leads ─────────────────────────────────────────────────

@router.post(
    "/leads/score-all",
    tags=["Leads"],
    summary="Score all UNSCORED leads for the current user",
    description=(
        "Runs the AI scoring engine only on leads that do NOT yet have a score. "
        "Already-scored leads are skipped. Returns the count of newly scored leads."
    ),
)
def score_all_leads(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    from app.modules.lead_scoring.services.scoring_service import ScoringService
    from app.models.lead_score import LeadScore
    svc = ScoringService(db)
    try:
        # Get all user lead IDs
        lead_repo = LeadRepository(db)
        all_leads, _ = lead_repo.get_all(user_id=user_id, page=1, page_size=100000, with_scores=False)
        all_ids = [l.id for l in all_leads]

        # Find which lead IDs already have a score record
        scored_ids = set(
            row[0] for row in
            db.query(LeadScore.lead_id).filter(LeadScore.lead_id.in_(all_ids)).all()
        )

        # Only score the ones that don't have a score yet
        unscored_ids = [lid for lid in all_ids if lid not in scored_ids]

        if not unscored_ids:
            return {
                "status": "complete",
                "scored": 0,
                "message": "All leads are already scored. Nothing to do.",
            }

        results = svc.score_leads(unscored_ids, user_id)
        scored = len(results)
        logger.info("[ScoreAll] Scored %d unscored leads for user=%s", scored, user_id)
        return {
            "status": "complete",
            "scored": scored,
            "message": f"Scored {scored} lead{'s' if scored != 1 else ''} successfully.",
        }
    except Exception as exc:
        logger.error("[ScoreAll] Failed for user=%s: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}")


# ── Score Single Lead ─────────────────────────────────────────────────────────

@router.post(
    "/leads/{lead_id}/score",
    tags=["Leads"],
    summary="Score a single lead by ID",
    description="Runs the AI scoring engine on a single lead and persists the result.",
)
def score_single_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    import uuid as _uuid
    try:
        _uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="lead_id must be a valid UUID.")

    lead_repo = LeadRepository(db)
    lead = lead_repo.get_by_id(lead_id, user_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead '{lead_id}' not found.")

    from app.modules.lead_scoring.services.scoring_service import ScoringService
    svc = ScoringService(db)
    try:
        results = svc.score_leads([lead_id], user_id)
        if not results:
            raise HTTPException(status_code=500, detail="Scoring returned no results.")
        r = results[0]
        logger.info("[ScoreSingle] lead_id=%s final=%.3f", lead_id, r["final_score"])
        return {
            "status":      "scored",
            "lead_id":     lead_id,
            "final_score": r["final_score"],
            "tag":         r.get("tag", ""),
            "message":     f"Lead scored successfully: {r.get('tag', 'OK')} ({round(r['final_score'] * 100)})",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[ScoreSingle] Failed lead_id=%s: %s", lead_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}")


# ── Delete Lead ───────────────────────────────────────────────────────────────

@router.delete(
    "/leads/{lead_id}",
    status_code=status.HTTP_200_OK,
    tags=["Leads"],
    summary="Delete a lead (and its score) by ID",
    description=(
        "Hard-deletes a lead and its associated score record. "
        "The operation is scoped to the authenticated user — you cannot delete other users' leads."
    ),
)
def delete_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    import uuid as _uuid
    try:
        _uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="lead_id must be a valid UUID.")

    repo = LeadRepository(db)
    deleted = repo.delete(lead_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found or not accessible.",
        )
    logger.info("[Delete] lead_id=%s deleted by user=%s", lead_id, user_id)
    return {"status": "deleted", "lead_id": lead_id}


# ── Leads ─────────────────────────────────────────────────────────────────────

@router.post(
    "/leads/upload",
    response_model=LeadUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Upload leads via CSV file or JSON body",
)
async def upload_leads(
    file: Optional[UploadFile] = File(None, description="CSV file with lead data"),
    json_data: Optional[str] = Form(None, description="JSON array of lead objects"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Accept leads via:
    - **CSV file** (multipart/form-data, field `file`)
    - **JSON string** (form field `json_data`, an array of lead objects)

    All uploaded leads are scoped to the authenticated user.
    """
    svc = LeadService(db)

    if file and file.filename:
        content = await file.read()
        if not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported for file upload.",
            )
        return svc.upload_from_csv(content, user_id)

    elif json_data:
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in json_data field.",
            )
        if not isinstance(data, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="json_data must be a JSON array.",
            )
        return svc.upload_from_json(data, user_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide either a CSV file or json_data.",
    )


@router.get(
    "/leads",
    response_model=LeadListResponse,
    tags=["Leads"],
    summary="List all leads for the current user (paginated)",
)
def list_leads(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Results per page"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns paginated list of leads scoped to the authenticated user,
    with embedded scores if available.
    """
    repo = LeadRepository(db)
    leads, total = repo.get_all(user_id=user_id, page=page, page_size=page_size)

    return LeadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        leads=leads,
    )


@router.get(
    "/leads/top",
    response_model=LeadListResponse,
    tags=["Leads"],
    summary="Get top-scoring leads (highest first)",
)
def get_top_leads(
    limit: int = Query(50, ge=1, le=500, description="Number of top leads to return"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns the highest-scoring leads for the authenticated user,
    ordered by final_score descending. Each lead includes its tag
    (HOT 🔥 / WARM / COLD) based on score thresholds.
    """
    lead_repo = LeadRepository(db)
    score_repo = ScoreRepository(db)

    # Get all user lead IDs
    all_leads, total = lead_repo.get_all(user_id=user_id, page=1, page_size=10000, with_scores=False)
    all_lead_ids = [l.id for l in all_leads]

    # Get top scored lead IDs
    top_ids = score_repo.get_top_scored_lead_ids(all_lead_ids, limit=limit)
    if not top_ids:
        return LeadListResponse(total=0, page=1, page_size=limit, leads=[])

    # Fetch full lead objects with scores, preserving score order
    leads = lead_repo.get_by_ids(top_ids, user_id)
    lead_map = {l.id: l for l in leads}
    ordered_leads = [lead_map[lid] for lid in top_ids if lid in lead_map]

    # Eagerly load scores and attach tags
    for lead in ordered_leads:
        score = score_repo.get_by_lead_id(lead.id)
        if score:
            score.tag = compute_lead_tag(score.final_score)
            lead.score = score

    return LeadListResponse(
        total=len(ordered_leads),
        page=1,
        page_size=limit,
        leads=ordered_leads,
    )


@router.get(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Get a specific lead by ID",
)
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lead_id must be a valid UUID.",
        )
        
    repo = LeadRepository(db)
    lead = repo.get_by_id(lead_id, user_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found or not accessible.",
        )
    return lead


# ── Score Explanation ─────────────────────────────────────────────────────────

@router.get(
    "/leads/{lead_id}/explanation",
    response_model=LeadExplanationResponse,
    tags=["Leads"],
    summary="Get score explanation for a specific lead",
)
def get_lead_explanation(
    lead_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns the score breakdown and human-readable explanation reasons
    for a specific lead. Requires the lead to be scored first.
    """
    # Verify lead belongs to user
    lead_repo = LeadRepository(db)
    lead = lead_repo.get_by_id(lead_id, user_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found or not accessible.",
        )

    score_repo = ScoreRepository(db)
    score = score_repo.get_by_lead_id(lead_id)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No score found for lead '{lead_id}'. Score the lead first.",
        )

    # Parse explanation from JSON
    expl_data = {}
    if score.explanation:
        try:
            parsed = json.loads(score.explanation)
            if isinstance(parsed, dict):
                expl_data = parsed
            elif isinstance(parsed, list):
                expl_data = {"reasons": parsed}
        except (json.JSONDecodeError, TypeError):
            expl_data = {"reasons": [score.explanation] if isinstance(score.explanation, str) else []}

    return LeadExplanationResponse(
        lead_id=lead_id,
        score=score.final_score,
        smoothed_score=score.smoothed_score,
        value_score=score.value_score,
        confidence_score=score.confidence_score,
        signal_score=score.signal_score,
        tag=score.tag or compute_lead_tag(score.final_score),
        intent_label=score.intent_label or compute_intent_label(score.final_score),
        top_reasons=expl_data.get("top_reasons", []),
        value_factors=expl_data.get("value_factors", []),
        confidence_factors=expl_data.get("confidence_factors", []),
        summary=expl_data.get("summary", ""),
        reasons=expl_data.get("reasons", [])
    )



# ── Campaigns ─────────────────────────────────────────────────────────────────

@router.get(
    "/campaigns",
    response_model=CampaignListResponse,
    tags=["Campaigns"],
    summary="List all campaigns (paginated)",
)
def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = CampaignRepository(db)
    campaigns, total = repo.get_all(user_id=user_id, page=page, page_size=page_size)
    return CampaignListResponse(
        total=total,
        page=page,
        page_size=page_size,
        campaigns=campaigns,
    )

@router.post(
    "/campaign/run",
    response_model=CampaignRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Campaigns"],
    summary="Launch an outreach campaign (async)",
)
def run_campaign(
    request: CampaignRunRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Launches a campaign pipeline:
    1. Scores all specified leads (or all user leads if none specified)
    2. Filters leads below MIN_SCORE_THRESHOLD
    3. Generates personalized email for each qualified lead via LLM
    4. Sends emails via SendGrid (async, rate-limited)

    Returns immediately with campaign_id — use `/campaign/status` to track progress.
    """
    svc = CampaignService(db)
    try:
        return svc.launch_campaign(request, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to launch campaign for user_id=%s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to launch campaign. Check server logs.",
        )


@router.get(
    "/campaign/status",
    response_model=CampaignStatusResponse,
    tags=["Campaigns"],
    summary="Get campaign status and progress",
)
def get_campaign_status(
    campaign_id: str = Query(..., description="Campaign ID returned from /campaign/run"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns detailed campaign status including message delivery breakdown.
    Only returns campaigns that belong to the authenticated user.
    """
    campaign_repo = CampaignRepository(db)
    msg_repo = MessageRepository(db)

    campaign = campaign_repo.get_by_id(campaign_id, user_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found or not accessible.",
        )

    # Get message status counts
    status_counts = msg_repo.count_by_status(campaign_id)

    return CampaignStatusResponse(
        campaign_id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        total_leads=campaign.total_leads,
        processed_leads=campaign.processed_leads,
        failed_leads=campaign.failed_leads,
        celery_task_id=campaign.celery_task_id,
        created_at=campaign.created_at,
        completed_at=campaign.completed_at,
        error_message=campaign.error_message,
        messages_sent=status_counts.get(MessageStatus.SENT, 0),
        messages_pending=status_counts.get(MessageStatus.PENDING, 0),
        messages_failed=status_counts.get(MessageStatus.FAILED, 0),
        messages_rate_limited=status_counts.get(MessageStatus.RATE_LIMITED, 0),
    )


# ── Campaign Analytics ────────────────────────────────────────────────────────

@router.get(
    "/campaign/analytics",
    response_model=CampaignAnalyticsResponse,
    tags=["Campaigns"],
    summary="Get campaign analytics (scores, threshold, contacted vs skipped)",
)
def get_campaign_analytics(
    campaign_id: str = Query(..., description="Campaign ID"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns campaign analytics including:
    - total_leads: total leads in campaign
    - contacted: leads that passed threshold and were contacted
    - skipped: leads below threshold (not contacted)
    - avg_score: average final_score of all campaign leads
    - threshold: the MIN_SCORE_THRESHOLD used
    """
    settings = get_settings()
    campaign_repo = CampaignRepository(db)
    score_repo = ScoreRepository(db)

    campaign = campaign_repo.get_by_id(campaign_id, user_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found or not accessible.",
        )

    # Get all leads for this campaign via messages
    msg_repo = MessageRepository(db)
    lead_repo = LeadRepository(db)
    leads, _ = lead_repo.get_all(user_id=user_id, page=1, page_size=10000, with_scores=False)
    lead_ids = [l.id for l in leads]

    total = campaign.total_leads
    contacted = campaign.processed_leads
    skipped = total - contacted
    avg_score = score_repo.get_avg_score(lead_ids) if lead_ids else 0.0

    return CampaignAnalyticsResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        total_leads=total,
        contacted=contacted,
        skipped=skipped,
        avg_score=avg_score,
        threshold=settings.MIN_SCORE_THRESHOLD,
    )
