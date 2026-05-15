"""
app/modules/outreach_engine/routes.py
───────────────────────────────────────
FastAPI routes for Automation 3 — Outreach Engine.

Endpoints:
  POST /outreach/campaigns              — Create campaign (score filter)
  GET  /outreach/campaigns              — List all campaigns (paginated)
  GET  /outreach/campaigns/{id}         — Detail: leads + messages + per-step stats
  POST /outreach/campaigns/{id}/run     — Launch outreach sequence
  POST /outreach/campaigns/{id}/pause   — Pause running campaign
  GET  /outreach/campaigns/{id}/stats   — Stats (sent/replied/step breakdown)
  POST /outreach/reply                  — Reply webhook / manual flag
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.modules.outreach_engine.services.outreach_service import OutreachService
from app.modules.outreach_engine.services.webhook_service import WebhookService
from app.modules.outreach_engine.schemas.outreach import (
    CampaignCreateRequest,
    CampaignCreateResponse,
    CampaignDetailResponse,
    CampaignStatsResponse,
    OutreachCampaignListResponse,
    ReplyWebhookPayload,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

outreach_router = APIRouter(prefix="/outreach", tags=["Outreach"])


# ── POST /outreach/campaigns ──────────────────────────────────────────────────

@outreach_router.post(
    "/campaigns",
    response_model=CampaignCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an outreach campaign (score-filtered leads)",
)
def create_campaign(
    body: CampaignCreateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Creates campaign + attaches all scored leads above min_score_filter.
    Status starts as 'draft'. Use POST /{id}/run to launch the sequence.
    """
    svc = OutreachService(db)
    try:
        result = svc.create_campaign(
            user_id=user_id,
            name=body.name,
            min_score_filter=body.min_score_filter,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("create_campaign failed user=%s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create campaign: {str(e)}"
        )


# ── GET /outreach/campaigns ───────────────────────────────────────────────────

@outreach_router.get(
    "/campaigns",
    response_model=OutreachCampaignListResponse,
    summary="List outreach campaigns (paginated)",
)
def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    return svc.list_campaigns(user_id, page=page, page_size=page_size)


# ── GET /outreach/campaigns/{id} ──────────────────────────────────────────────

@outreach_router.get(
    "/campaigns/{campaign_id}",
    response_model=CampaignDetailResponse,
    summary="Get campaign detail (leads, messages, reply status)",
)
def get_campaign_detail(
    campaign_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    try:
        return svc.get_campaign_detail(campaign_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── POST /outreach/campaigns/{id}/run ────────────────────────────────────────

@outreach_router.post(
    "/campaigns/{campaign_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch outreach sequence (async)",
)
def run_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Dispatches the Celery campaign runner.
    Step 1 sent immediately, Steps 2/3 scheduled via ETA (Day 2, Day 5).
    """
    svc = OutreachService(db)
    try:
        return svc.run_campaign(campaign_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("run_campaign failed campaign=%s user=%s: %s", campaign_id, user_id, e)
        raise HTTPException(status_code=500, detail="Failed to run campaign.")


# ── POST /outreach/campaigns/{id}/pause ──────────────────────────────────────

@outreach_router.post(
    "/campaigns/{campaign_id}/pause",
    summary="Pause an outreach campaign",
)
def pause_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    try:
        return svc.pause_campaign(campaign_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── GET /outreach/campaigns/{id}/stats ───────────────────────────────────────

@outreach_router.get(
    "/campaigns/{campaign_id}/stats",
    response_model=CampaignStatsResponse,
    summary="Get campaign stats (sent/replied/rate per step)",
)
def get_campaign_stats(
    campaign_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    try:
        return svc.get_stats(campaign_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── DELETE /outreach/campaigns/{id} ──────────────────────────────────────────

@outreach_router.delete(
    "/campaigns/{campaign_id}",
    summary="Delete a campaign",
)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    try:
        svc.delete_campaign(campaign_id, user_id)
        return {"status": "success", "message": "Campaign deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── POST /outreach/reply ──────────────────────────────────────────────────────

@outreach_router.post(
    "/reply",
    summary="Mark a lead as replied (webhook / manual)",
    description=(
        "Marks the lead as replied, stopping the sequence. "
        "If reply_text is provided, an async OpenAI classification task "
        "will store reply_type (interested/not_interested/meeting_request/objection) "
        "and reply_summary."
    ),
)
def mark_reply(
    body: ReplyWebhookPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    svc = OutreachService(db)
    try:
        return svc.mark_replied(
            campaign_id=body.campaign_id,
            lead_id=body.lead_id,
            user_id=user_id,
            reply_text=body.reply_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("mark_reply failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to mark reply.")


# ── GET /outreach/webhook/open  ─────────────────────────────────────────
# No auth — called by email client loading the invisible tracking pixel.

@outreach_router.get(
    "/webhook/open",
    summary="Email open tracking pixel",
    response_class=Response,
    include_in_schema=False,
)
def tracking_pixel(
    mid: str,          # message_id passed as query param in the pixel URL
    db: Session = Depends(get_db),
):
    """
    Returns a 1×1 transparent GIF and records the open event.
    Embed in emails as: <img src="https://api.example.com/api/v1/outreach/webhook/open?mid={message_id}" />
    """
    svc = WebhookService(db)
    svc.record_open(mid)
    return Response(
        content=WebhookService.get_tracking_gif(),
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


# ── POST /outreach/webhook/events  ──────────────────────────────────────
# No auth — called by SendGrid. Optionally verify HMAC signature.

@outreach_router.post(
    "/webhook/events",
    summary="SendGrid event webhook (delivered/open/bounce)",
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
)
async def sendgrid_events(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receives raw SendGrid Event Webhook POST (list of event dicts).
    Verifies HMAC signature if SENDGRID_WEBHOOK_KEY is set.
    Handles: delivered, open, bounce, dropped, spamreport, blocked.
    """
    raw_body = await request.body()

    # Optional signature verification
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
    if not WebhookService.verify_sendgrid_signature(raw_body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        import json
        events = json.loads(raw_body)
        if not isinstance(events, list):
            raise ValueError("Expected a list of events")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    svc = WebhookService(db)
    result = svc.process_sendgrid_events(events)
    return {"status": "ok", "processed": result}
