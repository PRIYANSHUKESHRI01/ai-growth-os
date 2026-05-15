"""
app/schemas/message.py
───────────────────────
Pydantic schemas for Message.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.message import MessageStatus


class MessageResponse(BaseModel):
    id: str
    campaign_id: str
    lead_id: str
    subject: Optional[str]
    body: Optional[str]
    status: MessageStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    sendgrid_message_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
