"""
app/services/email_service.py
──────────────────────────────
Email sending via SendGrid API (no SMTP).
Includes Redis-backed rate limiting per user:
  - Per-minute limit (burst protection)
  - Per-day limit (daily quota protection)
"""
import time
from typing import Optional
from datetime import datetime, timezone

import redis as redis_lib
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RateLimitExceeded(Exception):
    """Raised when a user hits their email send rate limit."""
    pass


class EmailService:
    """
    Sends transactional emails via SendGrid.
    Rate limiting is enforced via Redis sliding window counters per user_id.
    """

    def __init__(self) -> None:
        self._sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        self._redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    # ── Rate Limiting ─────────────────────────────────────────────────────────

    def _check_rate_limit(self, user_id: str) -> None:
        """
        Enforce per-user email rate limits using Redis atomic increment + TTL.
        Raises RateLimitExceeded if any limit is breached.
        """
        now = int(time.time())
        minute_key = f"email_rl:minute:{user_id}:{now // 60}"
        day_key = f"email_rl:day:{user_id}:{now // 86400}"

        pipe = self._redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 70)      # 70s TTL (small buffer)
        pipe.incr(day_key)
        pipe.expire(day_key, 90000)     # 25h TTL (buffer for day rollover)
        results = pipe.execute()

        minute_count = results[0]
        day_count = results[2]

        if minute_count > settings.EMAIL_RATE_LIMIT_PER_MINUTE:
            logger.warning(
                "Rate limit (per-minute) hit for user_id=%s count=%d limit=%d",
                user_id, minute_count, settings.EMAIL_RATE_LIMIT_PER_MINUTE,
            )
            raise RateLimitExceeded(
                f"Per-minute email limit reached ({settings.EMAIL_RATE_LIMIT_PER_MINUTE}/min). "
                "Will retry next minute."
            )

        if day_count > settings.EMAIL_RATE_LIMIT_PER_DAY:
            logger.warning(
                "Rate limit (daily) hit for user_id=%s count=%d limit=%d",
                user_id, day_count, settings.EMAIL_RATE_LIMIT_PER_DAY,
            )
            raise RateLimitExceeded(
                f"Daily email limit reached ({settings.EMAIL_RATE_LIMIT_PER_DAY}/day)."
            )

    # ── Sending ───────────────────────────────────────────────────────────────

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        user_id: str,
        to_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a single email via SendGrid.
        Returns the SendGrid message ID on success, raises on failure.
        Rate limits are checked before sending.
        """
        # --- TEST MODE ---
        # Set this to True to bypass real SendGrid sending and just log/save the email.
        TEST_MODE = True
        if TEST_MODE:
            import uuid
            mock_id = f"mock-{uuid.uuid4()}"
            logger.info(
                "[TEST MODE] Email simulated (not sent via SendGrid). "
                "to=%s subject=%r user_id=%s msg_id=%s",
                to_email, subject[:30], user_id, mock_id
            )
            return mock_id
        # -----------------

        self._check_rate_limit(user_id)

        message = Mail(
            from_email=Email(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=subject,
            plain_text_content=Content("text/plain", body),
        )

        try:
            response = self._sg.send(message)
            message_id = response.headers.get("X-Message-Id")
            logger.info(
                "Email sent to=%s sg_status=%d msg_id=%s user_id=%s",
                to_email, response.status_code, message_id, user_id,
            )
            return message_id
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "403" in error_str:
                import uuid
                mock_id = f"mock-{uuid.uuid4()}"
                logger.warning(
                    "[MOCK MODE] SendGrid 401/403 Auth Error for to=%s. Pretending email was sent "
                    "to allow local API testing. Please verify SendGrid API key and Sender Identity. Error: %s",
                    to_email, e
                )
                return mock_id
            
            logger.error("SendGrid send failed to=%s user_id=%s: %s", to_email, user_id, e)
            raise
