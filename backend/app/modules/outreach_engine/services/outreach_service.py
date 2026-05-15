"""
app/modules/outreach_engine/services/outreach_service.py
──────────────────────────────────────────────────────────
Main orchestrator for the Outreach Engine (Automation 3).

Responsibilities:
  - Create campaigns (filter by score threshold, attach leads)
  - Run / pause campaigns
  - Get campaign detail, stats, list
  - Mark lead as replied → trigger AI classification
  - Credit gate for sends
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_lead import CampaignLead, CampaignLeadStatus, ReplyType
from app.models.campaign_step_stats import CampaignStepStats
from app.models.lead import Lead
from app.models.lead_score import LeadScore
from app.repositories.lead_repository import LeadRepository
from app.repositories.score_repository import ScoreRepository
from app.modules.outreach_engine.schemas.outreach import (
    CampaignCreateResponse,
    CampaignDetailResponse,
    CampaignLeadDetail,
    CampaignStatsResponse,
    OutreachCampaignListResponse,
    OutreachCampaignSummary,
    StepStatDetail,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class OutreachService:
    """Campaign lifecycle management for the Outreach Engine."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.score_repo = ScoreRepository(db)

    # ── Create ────────────────────────────────────────────────────────────────

    def create_campaign(
        self,
        user_id: str,
        name: str,
        min_score_filter: float = 0.0,
        lead_ids: list | None = None,
        date_filter: str = "all",
    ) -> CampaignCreateResponse:
        """
        Creates a campaign with flexible lead targeting:
          1. lead_ids provided → target those specific leads (ignore score filter)
          2. date_filter → narrow the pool to today/week/all
          3. min_score_filter → include only leads scoring above threshold
             (if 0.0, any scored lead is included)
        """
        from datetime import timedelta

        # ── Mode 1: Specific lead IDs ─────────────────────────────────────────
        if lead_ids:
            leads = self.lead_repo.get_by_ids(lead_ids, user_id)
            if not leads:
                raise ValueError(
                    "None of the specified leads were found. "
                    "They may belong to a different account."
                )
            qualified_ids = [l.id for l in leads]

        # ── Mode 2: Date-filtered + score-filtered pool ───────────────────────
        else:
            all_leads, _ = self.lead_repo.get_all(
                user_id=user_id, page=1, page_size=50000, with_scores=False
            )
            if not all_leads:
                raise ValueError(
                    "No leads found in your account. "
                    "Add leads first via the Leads page or run a Discovery job."
                )

            # Apply date filter
            if date_filter == "today":
                today = datetime.now(timezone.utc).date()
                all_leads = [
                    l for l in all_leads
                    if l.created_at and l.created_at.date() == today
                ]
                if not all_leads:
                    raise ValueError(
                        "No leads were added today. "
                        "Try 'This Week' or 'All Time' instead."
                    )
            elif date_filter == "week":
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                all_leads = [
                    l for l in all_leads
                    if l.created_at and l.created_at >= week_ago
                ]
                if not all_leads:
                    raise ValueError(
                        "No leads were added in the past 7 days. "
                        "Try 'All Time' instead."
                    )

            pool_ids = [l.id for l in all_leads]

            # Apply score filter
            if min_score_filter > 0.0:
                qualified_ids = self.score_repo.get_scored_lead_ids_above_threshold(
                    pool_ids, threshold=min_score_filter
                )
                if not qualified_ids:
                    raise ValueError(
                        f"No leads have a score ≥ {min_score_filter:.0%}. "
                        f"Your leads currently score between 0–20%. "
                        f"Try setting the threshold to 0% to include all scored leads."
                    )
            else:
                # min_score_filter = 0 → include all leads that have ANY score
                scored_ids = set(
                    row[0] for row in
                    self.db.query(LeadScore.lead_id)
                    .filter(LeadScore.lead_id.in_(pool_ids))
                    .all()
                )
                qualified_ids = [lid for lid in pool_ids if lid in scored_ids]
                if not qualified_ids:
                    raise ValueError(
                        "None of your leads have been scored yet. "
                        "Go to Lead Scoring → Score All Unscored first."
                    )

        # ── Create campaign ───────────────────────────────────────────────────
        campaign = Campaign(
            user_id=user_id,
            name=name,
            status=CampaignStatus.DRAFT,
            total_leads=len(qualified_ids),
            min_score_filter=min_score_filter,
        )
        self.db.add(campaign)
        self.db.flush()

        for lead_id in qualified_ids:
            cl = CampaignLead(
                campaign_id=campaign.id,
                lead_id=lead_id,
                status=CampaignLeadStatus.PENDING,
                current_step=0,
            )
            self.db.add(cl)

        self.db.commit()
        self.db.refresh(campaign)

        logger.info(
            "[Campaign] created campaign_id=%s name=%r leads=%d user=%s",
            campaign.id, name, len(qualified_ids), user_id,
        )

        return CampaignCreateResponse(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            lead_count=len(qualified_ids),
            message=f"Campaign '{name}' created with {len(qualified_ids)} lead{'s' if len(qualified_ids) != 1 else ''}.",
        )

    # ── Run ───────────────────────────────────────────────────────────────────

    def run_campaign(self, campaign_id: str, user_id: str) -> dict:
        """
        Launch the outreach sequence. Checks credits, dispatches Celery task.
        """
        campaign = self._get_campaign_or_raise(campaign_id, user_id)

        if campaign.status == CampaignStatus.RUNNING:
            raise ValueError("Campaign is already running.")
        if campaign.status == CampaignStatus.COMPLETED:
            raise ValueError("Campaign has already completed.")

        # Dispatch Celery task
        from app.modules.outreach_engine.workers.outreach_tasks import outreach_campaign_runner
        task = outreach_campaign_runner.delay(campaign_id=campaign_id, user_id=user_id)

        campaign.status = CampaignStatus.RUNNING
        campaign.celery_task_id = task.id
        self.db.commit()

        logger.info(
            "[Campaign] started campaign_id=%s task_id=%s user_id=%s",
            campaign_id, task.id, user_id,
        )
        return {
            "campaign_id": campaign_id,
            "status": CampaignStatus.RUNNING,
            "task_id": task.id,
            "message": f"Campaign '{campaign.name}' is now running.",
        }

    # ── Pause ─────────────────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str, user_id: str) -> dict:
        campaign = self._get_campaign_or_raise(campaign_id, user_id)
        campaign.status = CampaignStatus.PAUSED
        self.db.commit()
        logger.info("[Campaign] paused campaign_id=%s user_id=%s", campaign_id, user_id)
        return {"campaign_id": campaign_id, "status": CampaignStatus.PAUSED}

    # ── List ──────────────────────────────────────────────────────────────────

    def list_campaigns(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> OutreachCampaignListResponse:
        query = (
            self.db.query(Campaign)
            .filter(Campaign.user_id == user_id)
            .order_by(Campaign.created_at.desc())
        )
        total = query.count()
        campaigns = query.offset((page - 1) * page_size).limit(page_size).all()

        summaries = []
        for c in campaigns:
            rate = (c.total_replied / c.total_sent) if c.total_sent > 0 else 0.0
            oRate = (c.total_opened / c.total_sent) if c.total_sent > 0 else 0.0
            summaries.append(OutreachCampaignSummary(
                id=c.id,
                name=c.name,
                status=c.status,
                min_score_filter=c.min_score_filter,
                total_leads=c.total_leads,
                total_sent=c.total_sent,
                total_replied=c.total_replied,
                total_opened=c.total_opened,
                reply_rate=round(rate, 4),
                open_rate=round(oRate, 4),
                created_at=c.created_at,
            ))

        return OutreachCampaignListResponse(
            total=total, page=page, page_size=page_size, campaigns=summaries
        )

    # ── Detail ────────────────────────────────────────────────────────────────

    def get_campaign_detail(
        self, campaign_id: str, user_id: str
    ) -> CampaignDetailResponse:
        campaign = self._get_campaign_or_raise(campaign_id, user_id)

        campaign_leads = (
            self.db.query(CampaignLead)
            .filter(CampaignLead.campaign_id == campaign_id)
            .all()
        )

        from app.models.message import Message
        messages = self.db.query(Message).filter(Message.campaign_id == campaign_id).all()
        latest_messages = {}
        for msg in messages:
            if msg.lead_id not in latest_messages or msg.step_number > latest_messages[msg.lead_id].step_number:
                latest_messages[msg.lead_id] = msg

        lead_details = []
        for cl in campaign_leads:
            lead = self.db.get(Lead, cl.lead_id)
            if not lead:
                continue
                
            msg = latest_messages.get(lead.id)
            
            lead_details.append(CampaignLeadDetail(
                campaign_lead_id=cl.id,
                lead_id=cl.lead_id,
                first_name=lead.first_name,
                last_name=lead.last_name,
                email=lead.email,
                company=lead.company,
                title=lead.title,
                status=cl.status,
                current_step=cl.current_step,
                last_contacted_at=cl.last_contacted_at,
                reply_type=cl.reply_type,
                reply_summary=cl.reply_summary,
                subject=msg.subject if msg else None,
                body=msg.body if msg else None,
            ))

        rate = (campaign.total_replied / campaign.total_sent) if campaign.total_sent > 0 else 0.0
        oRate = (campaign.total_opened / campaign.total_sent) if campaign.total_sent > 0 else 0.0
        return CampaignDetailResponse(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            min_score_filter=campaign.min_score_filter,
            total_leads=campaign.total_leads,
            total_sent=campaign.total_sent,
            total_replied=campaign.total_replied,
            total_opened=campaign.total_opened,
            reply_rate=round(rate, 4),
            open_rate=round(oRate, 4),
            created_at=campaign.created_at,
            leads=lead_details,
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self, campaign_id: str, user_id: str) -> CampaignStatsResponse:
        campaign = self._get_campaign_or_raise(campaign_id, user_id)

        step_stats = (
            self.db.query(CampaignStepStats)
            .filter(CampaignStepStats.campaign_id == campaign_id)
            .order_by(CampaignStepStats.step_number)
            .all()
        )

        step_detail = [
            StepStatDetail(
                step_number=s.step_number,
                total_sent=s.total_sent,
                total_replied=s.total_replied,
                total_failed=s.total_failed,
                total_opened=s.total_opened,
                reply_rate=s.reply_rate,
                open_rate=s.open_rate,
            )
            for s in step_stats
        ]

        rate = (campaign.total_replied / campaign.total_sent) if campaign.total_sent > 0 else 0.0
        oRate = (campaign.total_opened / campaign.total_sent) if campaign.total_sent > 0 else 0.0
        return CampaignStatsResponse(
            campaign_id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            total_leads=campaign.total_leads,
            total_sent=campaign.total_sent,
            total_replied=campaign.total_replied,
            total_opened=campaign.total_opened,
            reply_rate=round(rate, 4),
            open_rate=round(oRate, 4),
            step_stats=step_detail,
        )

    # ── Reply ─────────────────────────────────────────────────────────────────

    def mark_replied(
        self,
        campaign_id: str,
        lead_id: str,
        user_id: str,
        reply_text: Optional[str] = None,
    ) -> dict:
        """
        Mark a lead as replied + optionally classify the reply with OpenAI.
        """
        campaign = self._get_campaign_or_raise(campaign_id, user_id)

        cl = (
            self.db.query(CampaignLead)
            .filter(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.lead_id == lead_id,
            )
            .first()
        )
        if not cl:
            raise ValueError(f"Lead {lead_id} not in campaign {campaign_id}.")

        cl.status = CampaignLeadStatus.REPLIED
        campaign.total_replied = (campaign.total_replied or 0) + 1
        self.db.commit()

        logger.info(
            "[Reply] detected campaign_id=%s lead_id=%s", campaign_id, lead_id
        )

        # Async reply classification
        if reply_text:
            from app.modules.outreach_engine.workers.outreach_tasks import outreach_classify_reply
            outreach_classify_reply.delay(
                campaign_lead_id=cl.id,
                lead_id=lead_id,
                reply_text=reply_text,
            )

        return {
            "campaign_id": campaign_id,
            "lead_id": lead_id,
            "status": "replied",
            "classification": "queued" if reply_text else "skipped",
        }

    def delete_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Deletes a campaign and its associated records."""
        campaign = self._get_campaign_or_raise(campaign_id, user_id)
        self.db.delete(campaign)
        self.db.commit()
        logger.info("[Campaign] deleted campaign_id=%s user=%s", campaign_id, user_id)
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_campaign_or_raise(self, campaign_id: str, user_id: str) -> Campaign:
        campaign = (
            self.db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.user_id == user_id)
            .first()
        )
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found or not accessible.")
        return campaign
