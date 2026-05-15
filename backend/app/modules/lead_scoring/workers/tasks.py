"""
app/workers/tasks.py
─────────────────────
Celery task definitions.

Tasks:
  - task_run_campaign    — full pipeline orchestrator
  - task_send_email      — send a single email with rate-limit handling & retry
"""
import time
import logging
from celery import shared_task
from celery.exceptions import Reject

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Campaign Orchestration Task ──────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.run_campaign",
    max_retries=2,
    default_retry_delay=30,
)
def task_run_campaign(self, campaign_id: str, lead_ids: list, user_id: str) -> dict:
    """
    Full pipeline: score leads → generate messages → dispatch email tasks.
    Runs synchronously inside the Celery worker process.
    """
    logger.info(
        "Worker: starting campaign_id=%s leads=%d user_id=%s",
        campaign_id, len(lead_ids), user_id,
    )
    db = SessionLocal()
    try:
        from app.modules.lead_scoring.services.campaign_service import CampaignService
        svc = CampaignService(db)
        svc.run_pipeline_sync(
            campaign_id=campaign_id,
            lead_ids=lead_ids,
            user_id=user_id,
        )
        return {"status": "completed", "campaign_id": campaign_id}
    except Exception as exc:
        logger.error("task_run_campaign failed for campaign_id=%s: %s", campaign_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for campaign_id=%s", campaign_id)
            return {"status": "failed", "campaign_id": campaign_id, "error": str(exc)}
    finally:
        db.close()


# ── Individual Email Send Task ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.send_email",
    max_retries=3,
    default_retry_delay=60,  # 60s between retries (respects rate limits)
)
def task_send_email(
    self,
    message_id: str,
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    user_id: str,
) -> dict:
    """
    Send a single email via SendGrid.
    Handles rate limiting by requeueing with delay.
    """
    db = SessionLocal()
    try:
        from app.modules.lead_scoring.services.email_service import EmailService, RateLimitExceeded
        from app.repositories.message_repository import MessageRepository

        msg_repo = MessageRepository(db)
        email_svc = EmailService()

        try:
            sg_message_id = email_svc.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                user_id=user_id,
                to_name=to_name or None,
            )
            msg_repo.mark_sent(message_id, sendgrid_message_id=sg_message_id)
            return {"status": "sent", "message_id": message_id}

        except RateLimitExceeded as rl_exc:
            logger.warning(
                "Rate limited for user_id=%s message_id=%s; retrying in 60s",
                user_id, message_id,
            )
            msg_repo.mark_rate_limited(message_id)
            raise self.retry(exc=rl_exc, countdown=60)

        except Exception as send_exc:
            logger.error(
                "Email send failed message_id=%s to=%s: %s",
                message_id, to_email, send_exc,
            )
            msg_repo.mark_failed(message_id, str(send_exc))
            raise self.retry(exc=send_exc, countdown=30)

    finally:
        db.close()
