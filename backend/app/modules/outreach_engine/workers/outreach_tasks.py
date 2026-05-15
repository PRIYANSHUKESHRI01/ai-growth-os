"""
app/modules/outreach_engine/workers/outreach_tasks.py
───────────────────────────────────────────────────────
Celery tasks for the Outreach Engine (Automation 3).

Tasks:
  outreach_campaign_runner       — Iterate CampaignLeads, send Step 1, schedule follow-ups
  outreach_send_email            — Send single email with deliverability + rate-limit + credit checks
  outreach_followup_scheduler    — Triggered at ETA; send the next step if not replied
  outreach_classify_reply        — Classify reply text via OpenAI, store reply_type + summary
"""
import time
import logging
from datetime import datetime, timezone

from celery import shared_task

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Outreach daily limit (configurable) ──────────────────────────────────────
OUTREACH_DAILY_LIMIT = 50  # emails per user per day via outreach engine


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_outreach_daily_count(redis_conn, user_id: str) -> int:
    """Return current outreach daily send count for user."""
    import time as _time
    day_key = f"outreach:daily:{user_id}:{int(_time.time()) // 86400}"
    val = redis_conn.get(day_key)
    return int(val) if val else 0


def _increment_outreach_daily(redis_conn, user_id: str) -> int:
    """Increment outreach daily counter and set TTL. Returns new count."""
    import time as _time
    day_key = f"outreach:daily:{user_id}:{int(_time.time()) // 86400}"
    count = redis_conn.incr(day_key)
    redis_conn.expire(day_key, 90000)  # 25h TTL
    return count


def _deduct_credit(db, user_id: str) -> bool:
    """
    Deduct 1 enrichment credit.
    Returns True if credit was available and deducted, False otherwise.
    """
    from app.models.discovery_models import UserCredit
    credit = db.query(UserCredit).filter(UserCredit.user_id == user_id).first()
    if not credit or credit.enrichment_credits < 1:
        logger.warning(
            "[Credit] insufficient outreach credits for user_id=%s", user_id
        )
        return False
    credit.enrichment_credits -= 1
    db.commit()
    return True


def _update_step_stats(db, campaign_id: str, step: int, *, sent=0, replied=0, failed=0) -> None:
    """Upsert CampaignStepStats for the given step."""
    from app.models.campaign_step_stats import CampaignStepStats
    stat = (
        db.query(CampaignStepStats)
        .filter(
            CampaignStepStats.campaign_id == campaign_id,
            CampaignStepStats.step_number == step,
        )
        .first()
    )
    if not stat:
        stat = CampaignStepStats(
            campaign_id=campaign_id,
            step_number=step,
            total_sent=0,
            total_replied=0,
            total_failed=0,
            reply_rate=0.0,
        )
        db.add(stat)

    stat.total_sent += sent
    stat.total_replied += replied
    stat.total_failed += failed

    if stat.total_sent > 0:
        stat.reply_rate = round(stat.total_replied / stat.total_sent, 4)

    db.commit()


# ── Task 1: Campaign Runner ───────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="outreach.campaign_runner",
    max_retries=2,
    default_retry_delay=60,
)
def outreach_campaign_runner(self, campaign_id: str, user_id: str) -> dict:
    """
    Main campaign orchestrator.
    For each pending CampaignLead:
      1. Deliverability check
      2. Daily outreach limit check
      3. Credit check + deduct
      4. Generate Step 1 message
      5. Send email
      6. Schedule Step 2/3 ETA
      7. Run safety check after batch
    """
    logger.info(
        "[Campaign] runner started campaign_id=%s user_id=%s", campaign_id, user_id
    )
    db = SessionLocal()
    try:
        import redis as redis_lib
        from app.core.config import get_settings
        from app.models.campaign import Campaign, CampaignStatus
        from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
        from app.models.lead import Lead
        from app.modules.outreach_engine.services.personalization_service import PersonalizationService
        from app.modules.outreach_engine.services.deliverability_service import DeliverabilityService
        from app.modules.outreach_engine.services.sequence_service import SequenceService
        from app.modules.outreach_engine.services.safety_service import SafetyService
        from app.repositories.score_repository import ScoreRepository

        settings = get_settings()
        redis_conn = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        personalizer = PersonalizationService()
        deliverability = DeliverabilityService()
        seq_svc = SequenceService(db)
        safety_svc = SafetyService(db)
        score_repo = ScoreRepository(db)

        # Fetch campaign
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            logger.error("[Campaign] not found campaign_id=%s", campaign_id)
            return {"status": "error", "campaign_id": campaign_id}

        # Fetch pending CampaignLeads
        pending_leads = (
            db.query(CampaignLead)
            .filter(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.status == CampaignLeadStatus.PENDING,
            )
            .all()
        )

        logger.info(
            "[Campaign] processing %d leads campaign_id=%s", len(pending_leads), campaign_id
        )

        sent_count = 0
        for cl in pending_leads:
            lead = db.get(Lead, cl.lead_id)
            if not lead:
                continue

            # ── Deliverability check ──────────────────────────────────────
            valid, reason = deliverability.check(lead.email)
            if not valid:
                logger.info("[Deliverability] skip lead_id=%s reason=%s", lead.id, reason)
                cl.status = CampaignLeadStatus.SKIPPED
                db.commit()
                _update_step_stats(db, campaign_id, step=1, failed=1)
                continue

            # ── Daily outreach limit ──────────────────────────────────────
            daily_count = _get_outreach_daily_count(redis_conn, user_id)
            if daily_count >= OUTREACH_DAILY_LIMIT:
                logger.warning(
                    "[Outreach] daily limit reached user_id=%s limit=%d",
                    user_id, OUTREACH_DAILY_LIMIT,
                )
                break  # Stop batch for today

            # ── Credit check ──────────────────────────────────────────────
            has_credit = _deduct_credit(db, user_id)
            if not has_credit:
                cl.status = CampaignLeadStatus.SKIPPED
                db.commit()
                continue

            # ── Generate Step 1 message ───────────────────────────────────
            score = score_repo.get_by_lead_id(lead.id)
            subject, body = personalizer.generate(lead, score, step_number=1)

            # ── Dispatch send task ────────────────────────────────────────
            to_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
            outreach_send_email.delay(
                campaign_id=campaign_id,
                campaign_lead_id=cl.id,
                lead_id=lead.id,
                step_number=1,
                to_email=lead.email,
                to_name=to_name or None,
                subject=subject,
                body=body,
                user_id=user_id,
            )
            _increment_outreach_daily(redis_conn, user_id)
            sent_count += 1

            # ── Schedule Step 2 / Step 3 via ETA ─────────────────────────
            now = datetime.now(timezone.utc)
            eta_step2 = seq_svc.get_eta(step_number=2, base_time=now)
            eta_step3 = seq_svc.get_eta(step_number=3, base_time=now)

            seq_svc.schedule_followup(cl.id, step=2, eta=eta_step2)
            seq_svc.schedule_followup(cl.id, step=3, eta=eta_step3)

        # ── Safety check after batch ──────────────────────────────────────
        safety_svc.check_and_enforce(campaign_id)

        logger.info(
            "[Campaign] runner completed campaign_id=%s sent=%d", campaign_id, sent_count
        )
        return {"status": "completed", "campaign_id": campaign_id, "sent": sent_count}

    except Exception as exc:
        logger.error("[Campaign] runner failed campaign_id=%s: %s", campaign_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            db2 = SessionLocal()
            try:
                from app.models.campaign import Campaign, CampaignStatus
                c = db2.get(Campaign, campaign_id)
                if c:
                    c.status = CampaignStatus.FAILED
                    c.error_message = str(exc)[:1000]
                    db2.commit()
            finally:
                db2.close()
            return {"status": "failed", "campaign_id": campaign_id}
    finally:
        db.close()


# ── Task 2: Send Email ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="outreach.send_email",
    max_retries=3,
    default_retry_delay=60,
)
def outreach_send_email(
    self,
    campaign_id: str,
    campaign_lead_id: str,
    lead_id: str,
    step_number: int,
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    user_id: str,
) -> dict:
    """
    Send a single outreach email via SendGrid.
    On success: mark CampaignLead step + Message status, update campaign totals, update step stats.
    On rate limit: retry after 60s.
    """
    db = SessionLocal()
    try:
        from app.modules.lead_scoring.services.email_service import EmailService, RateLimitExceeded
        from app.models.campaign import Campaign
        from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
        from app.models.message import Message, MessageStatus
        from app.modules.outreach_engine.services.safety_service import SafetyService

        email_svc = EmailService()

        try:
            sg_id = email_svc.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                user_id=user_id,
                to_name=to_name or None,
            )
        except RateLimitExceeded as rl:
            logger.warning(
                "[Email] rate limited outreach user_id=%s lead_id=%s; retry in 60s",
                user_id, lead_id,
            )
            raise self.retry(exc=rl, countdown=60)

        logger.info("[Email] sent to=%s step=%d lead_id=%s", to_email, step_number, lead_id)

        # ── Update CampaignLead step ──────────────────────────────────────
        cl = db.get(CampaignLead, campaign_lead_id)
        if cl and cl.status != CampaignLeadStatus.REPLIED:
            cl.current_step = step_number
            cl.status = CampaignLeadStatus.SENT
            cl.last_contacted_at = datetime.now(timezone.utc)

        # ── Create Message record ─────────────────────────────────────────
        msg = Message(
            campaign_id=campaign_id,
            lead_id=lead_id,
            subject=subject,
            body=body,
            step_number=step_number,
            status=MessageStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            sendgrid_message_id=sg_id,
        )
        db.add(msg)

        # ── Update campaign totals ────────────────────────────────────────
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.total_sent = (campaign.total_sent or 0) + 1
            campaign.processed_leads = (campaign.processed_leads or 0) + 1

        db.commit()

        # ── Update step stats ─────────────────────────────────────────────
        _update_step_stats(db, campaign_id, step=step_number, sent=1)

        # ── Safety check ──────────────────────────────────────────────────
        SafetyService(db).check_and_enforce(campaign_id)

        return {"status": "sent", "lead_id": lead_id, "step": step_number}

    except Exception as exc:
        db2 = SessionLocal()
        try:
            from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
            cl = db2.get(CampaignLead, campaign_lead_id)
            if cl:
                cl.status = CampaignLeadStatus.FAILED
                db2.commit()
        finally:
            db2.close()
        _update_step_stats(db, campaign_id, step=step_number, failed=1)

        logger.error(
            "[Email] send failed lead_id=%s step=%d: %s", lead_id, step_number, exc
        )
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


# ── Task 3: Follow-up Scheduler ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="outreach.followup_scheduler",
    max_retries=2,
    default_retry_delay=30,
)
def outreach_followup_scheduler(self, campaign_lead_id: str, step: int) -> dict:
    """
    Triggered at ETA.
    1. Check if lead has replied — if so, skip.
    2. Check campaign is still running.
    3. Generate step-specific message.
    4. Dispatch outreach_send_email.
    """
    db = SessionLocal()
    try:
        from app.core.config import get_settings
        from app.models.campaign import Campaign, CampaignStatus
        from app.models.campaign_lead import CampaignLead, CampaignLeadStatus
        from app.models.lead import Lead
        from app.modules.outreach_engine.services.personalization_service import PersonalizationService
        from app.modules.outreach_engine.services.sequence_service import SequenceService
        from app.modules.outreach_engine.services.deliverability_service import DeliverabilityService
        from app.repositories.score_repository import ScoreRepository
        import redis as redis_lib

        settings = get_settings()
        redis_conn = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        cl = db.get(CampaignLead, campaign_lead_id)
        if not cl:
            return {"status": "skipped", "reason": "campaign_lead not found"}

        campaign = db.get(Campaign, cl.campaign_id)
        if not campaign or campaign.status not in (CampaignStatus.RUNNING,):
            return {"status": "skipped", "reason": f"campaign not running (status={campaign.status if campaign else 'N/A'})"}

        seq_svc = SequenceService(db)
        if not seq_svc.should_continue(cl):
            return {"status": "skipped", "reason": f"sequence stopped (lead status={cl.status})"}

        lead = db.get(Lead, cl.lead_id)
        if not lead:
            return {"status": "skipped", "reason": "lead not found"}

        # Deliverability
        deliverability = DeliverabilityService()
        valid, reason = deliverability.check(lead.email)
        if not valid:
            logger.info("[Followup] skip lead_id=%s reason=%s", lead.id, reason)
            return {"status": "skipped", "reason": reason}

        # Daily limit
        daily_count = _get_outreach_daily_count(redis_conn, campaign.user_id)
        if daily_count >= OUTREACH_DAILY_LIMIT:
            logger.warning("[Followup] daily limit reached, skipping step=%d lead_id=%s", step, lead.id)
            return {"status": "skipped", "reason": "daily limit reached"}

        # Credit check
        has_credit = _deduct_credit(db, campaign.user_id)
        if not has_credit:
            return {"status": "skipped", "reason": "insufficient credits"}

        # Generate message for this step
        score_repo = ScoreRepository(db)
        score = score_repo.get_by_lead_id(lead.id)
        personalizer = PersonalizationService()
        subject, body = personalizer.generate(lead, score, step_number=step)

        to_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        outreach_send_email.delay(
            campaign_id=cl.campaign_id,
            campaign_lead_id=cl.id,
            lead_id=lead.id,
            step_number=step,
            to_email=lead.email,
            to_name=to_name or None,
            subject=subject,
            body=body,
            user_id=campaign.user_id,
        )
        _increment_outreach_daily(redis_conn, campaign.user_id)

        logger.info(
            "[Followup] scheduled campaign_lead_id=%s step=%d", campaign_lead_id, step
        )
        return {"status": "dispatched", "step": step, "lead_id": lead.id}

    except Exception as exc:
        logger.error("[Followup] failed campaign_lead_id=%s step=%d: %s", campaign_lead_id, step, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed"}
    finally:
        db.close()


# ── Task 4: Reply Classifier ───────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="outreach.classify_reply",
    max_retries=2,
    default_retry_delay=30,
)
def outreach_classify_reply(self, campaign_lead_id: str, lead_id: str, reply_text: str) -> dict:
    """
    Classify a reply using OpenAI and store reply_type + reply_summary.
    """
    db = SessionLocal()
    try:
        from langchain_openai import ChatOpenAI
        from langchain.prompts import ChatPromptTemplate
        from app.core.config import get_settings
        from app.models.campaign_lead import CampaignLead, ReplyType

        settings = get_settings()
        cl = db.get(CampaignLead, campaign_lead_id)
        if not cl:
            return {"status": "skipped"}

        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a B2B sales analyst. Classify the following reply into exactly ONE of these categories:\n"
             "- interested\n- not_interested\n- meeting_request\n- objection\n\n"
             "Also write a one-sentence summary of what the person said.\n"
             "Respond in this exact JSON format (no markdown):\n"
             '{{"type": "<category>", "summary": "<one sentence>"}}'),
            ("human", f"Reply text:\n{reply_text}"),
        ])

        try:
            chain = prompt | llm
            response = chain.invoke({})
            content = response.content.strip()

            import json
            data = json.loads(content)
            reply_type_str = data.get("type", "unknown").lower()
            summary = data.get("summary", "")

            # Map to enum (default to UNKNOWN)
            type_map = {
                "interested": ReplyType.INTERESTED,
                "not_interested": ReplyType.NOT_INTERESTED,
                "meeting_request": ReplyType.MEETING_REQUEST,
                "objection": ReplyType.OBJECTION,
            }
            cl.reply_type = type_map.get(reply_type_str, ReplyType.UNKNOWN)
            cl.reply_summary = summary[:500]
            db.commit()

            logger.info(
                "[Reply] classified lead_id=%s type=%s", lead_id, reply_type_str
            )
            return {"status": "classified", "type": reply_type_str, "summary": summary}

        except Exception as parse_exc:
            logger.warning(
                "[Reply] classification parse error lead_id=%s: %s", lead_id, parse_exc
            )
            cl.reply_type = ReplyType.UNKNOWN
            cl.reply_summary = reply_text[:250]
            db.commit()
            return {"status": "fallback", "type": "unknown"}

    except Exception as exc:
        logger.error("[Reply] classify failed lead_id=%s: %s", lead_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed"}
    finally:
        db.close()
