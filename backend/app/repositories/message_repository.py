"""
app/repositories/message_repository.py
────────────────────────────────────────
CRUD for Message records.
"""
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.message import Message, MessageStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, campaign_id: str, lead_id: str, subject: str, body: str) -> Message:
        msg = Message(
            campaign_id=campaign_id,
            lead_id=lead_id,
            subject=subject,
            body=body,
            status=MessageStatus.PENDING,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_by_id(self, message_id: str) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == message_id).first()

    def get_by_campaign(self, campaign_id: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.campaign_id == campaign_id)
            .all()
        )

    def count_by_status(self, campaign_id: str) -> dict:
        """Return a dict of status -> count for a campaign."""
        rows = (
            self.db.query(Message.status, Message.status.label("cnt"))
            .filter(Message.campaign_id == campaign_id)
            .all()
        )
        # build a proper count
        from collections import Counter
        statuses = [row.status for row in self.db.query(Message.status)
                    .filter(Message.campaign_id == campaign_id).all()]
        return dict(Counter(statuses))

    def mark_sent(self, message_id: str, sendgrid_message_id: Optional[str] = None) -> None:
        msg = self.db.query(Message).filter(Message.id == message_id).first()
        if msg:
            msg.status = MessageStatus.SENT
            msg.sent_at = datetime.now(timezone.utc)
            msg.sendgrid_message_id = sendgrid_message_id
            self.db.commit()

    def mark_failed(self, message_id: str, error: str) -> None:
        msg = self.db.query(Message).filter(Message.id == message_id).first()
        if msg:
            msg.status = MessageStatus.FAILED
            msg.error_message = error[:1000]
            self.db.commit()

    def mark_rate_limited(self, message_id: str) -> None:
        msg = self.db.query(Message).filter(Message.id == message_id).first()
        if msg:
            msg.status = MessageStatus.RATE_LIMITED
            msg.error_message = "Rate limit reached; will retry."
            self.db.commit()
