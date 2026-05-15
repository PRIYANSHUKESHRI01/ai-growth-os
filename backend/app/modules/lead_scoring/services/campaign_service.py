"""
app/services/campaign_service.py
──────────────────────────────────
Orchestrates the full campaign pipeline:
  1. Resolve leads (scoped to user_id)
  2. Score them
  3. Filter by score threshold (MIN_SCORE_THRESHOLD)
  4. Sort by final_score (highest priority first)
  5. Generate LLM messages
  6. Save messages
  7. Dispatch async Celery tasks for email sending

All data operations are strictly scoped to user_id.
"""
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.lead_repository import LeadRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.score_repository import ScoreRepository
from app.repositories.message_repository import MessageRepository
from app.modules.lead_scoring.services.scoring_service import ScoringService
from app.modules.lead_scoring.services.llm_service import LLMService
from app.models.campaign import CampaignStatus
from app.schemas.campaign import CampaignRunRequest, CampaignRunResponse
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CampaignService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.campaign_repo = CampaignRepository(db)
        self.score_repo = ScoreRepository(db)
        self.msg_repo = MessageRepository(db)
        self.scoring_svc = ScoringService(db)
        self.llm_svc = LLMService()
        self.settings = get_settings()

    def launch_campaign(
        self,
        request: CampaignRunRequest,
        user_id: str,
    ) -> CampaignRunResponse:
        """
        Create campaign record and dispatch Celery task.
        Returns immediately — processing is async.
        """
        # 1. Resolve leads (all user-scoped)
        if request.lead_ids:
            leads = self.lead_repo.get_by_ids(request.lead_ids, user_id)
        else:
            leads, _ = self.lead_repo.get_all(
                user_id=user_id, page=1, page_size=10000, with_scores=False
            )

        if not leads:
            raise ValueError("No leads found for this user.")

        # 2. Create campaign record
        campaign = self.campaign_repo.create(
            user_id=user_id,
            name=request.campaign_name,
            total_leads=len(leads),
        )

        # 3. Dispatch async Celery task
        from app.modules.lead_scoring.workers.tasks import task_run_campaign
        task = task_run_campaign.delay(
            campaign_id=campaign.id,
            lead_ids=[l.id for l in leads],
            user_id=user_id,
        )

        self.campaign_repo.update_status(
            campaign.id,
            status=CampaignStatus.RUNNING,
            celery_task_id=task.id,
        )

        logger.info(
            "Campaign launched: campaign_id=%s celery_task=%s user_id=%s leads=%d",
            campaign.id, task.id, user_id, len(leads),
        )

        return CampaignRunResponse(
            campaign_id=campaign.id,
            status=CampaignStatus.RUNNING,
            total_leads=len(leads),
            message=f"Campaign '{request.campaign_name}' is running with {len(leads)} leads.",
        )

    def run_pipeline_sync(
        self,
        campaign_id: str,
        lead_ids: List[str],
        user_id: str,
    ) -> None:
        """
        Called by Celery worker — runs the full pipeline synchronously.
        Applies MIN_SCORE_THRESHOLD to skip low-quality leads.
        """
        threshold = self.settings.MIN_SCORE_THRESHOLD
        try:
            self.campaign_repo.update_status(campaign_id, CampaignStatus.RUNNING)

            # Score leads
            logger.info("Scoring %d leads for campaign_id=%s", len(lead_ids), campaign_id)
            self.scoring_svc.score_leads(lead_ids, user_id)

            # Load leads with scores, sort by final_score desc
            leads = self.lead_repo.get_by_ids(lead_ids, user_id)
            leads_with_scores = [
                (l, self.score_repo.get_by_lead_id(l.id))
                for l in leads
            ]
            leads_with_scores = [
                (l, s) for l, s in leads_with_scores if s is not None
            ]
            leads_with_scores.sort(key=lambda x: x[1].final_score, reverse=True)

            # Apply score threshold — skip low-scoring leads
            qualified = [(l, s) for l, s in leads_with_scores if s.final_score >= threshold]
            skipped_count = len(leads_with_scores) - len(qualified)
            if skipped_count > 0:
                logger.info(
                    "Threshold filter: %d leads skipped (score < %.2f), %d qualified for campaign_id=%s",
                    skipped_count, threshold, len(qualified), campaign_id,
                )

            # Generate messages + schedule email sends for qualified leads only
            for lead, score in qualified:
                try:
                    subject, body = self.llm_svc.generate_outreach(lead, score)
                    msg = self.msg_repo.create(
                        campaign_id=campaign_id,
                        lead_id=lead.id,
                        subject=subject,
                        body=body,
                    )

                    # Dispatch individual email task
                    from app.modules.lead_scoring.workers.tasks import task_send_email
                    task_send_email.delay(
                        message_id=msg.id,
                        to_email=lead.email,
                        to_name=f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                        subject=subject,
                        body=body,
                        user_id=user_id,
                    )
                    self.campaign_repo.increment_processed(campaign_id, success=True)

                except Exception as e:
                    logger.error(
                        "Failed to process lead_id=%s in campaign_id=%s: %s",
                        lead.id, campaign_id, e,
                    )
                    self.campaign_repo.increment_processed(campaign_id, success=False)

            self.campaign_repo.update_status(campaign_id, CampaignStatus.COMPLETED)
            logger.info("Campaign completed: campaign_id=%s", campaign_id)

        except Exception as e:
            logger.error("Campaign failed: campaign_id=%s error=%s", campaign_id, e)
            self.campaign_repo.update_status(
                campaign_id,
                CampaignStatus.FAILED,
                error_message=str(e)[:1000],
            )
            raise
