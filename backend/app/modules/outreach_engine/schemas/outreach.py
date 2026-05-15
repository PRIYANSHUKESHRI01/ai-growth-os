"""
app/modules/outreach_engine/schemas/outreach.py
─────────────────────────────────────────────────
Pydantic schemas for the Outreach Engine (Automation 3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.campaign import CampaignStatus
from app.models.campaign_lead import CampaignLeadStatus, ReplyType


# ── Campaign Creation ─────────────────────────────────────────────────────────

class CampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    min_score_filter: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Minimum lead score to include (0.0 = all scored leads)"
    )
    # Optional: target only specific lead IDs (bypasses score filter)
    lead_ids: Optional[List[str]] = Field(
        default=None,
        description="Explicit list of lead IDs to target (overrides score filter)"
    )
    # Optional: filter leads by creation date
    date_filter: Optional[str] = Field(
        default="all",
        description="Date filter: 'today', 'week', or 'all'"
    )


class CampaignCreateResponse(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    lead_count: int
    message: str

    model_config = {"from_attributes": True}


# ── Campaign List ─────────────────────────────────────────────────────────────

class OutreachCampaignSummary(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    min_score_filter: Optional[float]
    total_leads: int
    total_sent: int
    total_replied: int
    total_opened: int
    reply_rate: float
    open_rate: float
    created_at: datetime

    model_config = {"from_attributes": True}


class OutreachCampaignListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    campaigns: List[OutreachCampaignSummary]


# ── Campaign Detail ───────────────────────────────────────────────────────────

class CampaignLeadDetail(BaseModel):
    campaign_lead_id: str
    lead_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: str
    company: Optional[str]
    title: Optional[str]
    status: CampaignLeadStatus
    current_step: int
    last_contacted_at: Optional[datetime]
    reply_type: Optional[ReplyType]
    reply_summary: Optional[str]
    subject: Optional[str] = None
    body: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignDetailResponse(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    min_score_filter: Optional[float]
    total_leads: int
    total_sent: int
    total_replied: int
    total_opened: int
    reply_rate: float
    open_rate: float
    created_at: datetime
    leads: List[CampaignLeadDetail]

    model_config = {"from_attributes": True}


# ── Campaign Stats ────────────────────────────────────────────────────────────

class StepStatDetail(BaseModel):
    step_number: int
    total_sent: int
    total_replied: int
    total_failed: int
    total_opened: int
    reply_rate: float
    open_rate: float


class CampaignStatsResponse(BaseModel):
    campaign_id: str
    name: str
    status: CampaignStatus
    total_leads: int
    total_sent: int
    total_replied: int
    total_opened: int
    reply_rate: float
    open_rate: float
    step_stats: List[StepStatDetail]


# ── Reply Webhook ─────────────────────────────────────────────────────────────

class ReplyWebhookPayload(BaseModel):
    campaign_id: str
    lead_id: str
    reply_text: Optional[str] = Field(
        default=None,
        description="Raw reply text for AI classification (optional)"
    )


# ── SendGrid Webhook ────────────────────────────────────────────────

class SendGridEvent(BaseModel):
    """Single event object from SendGrid event webhook batch."""
    event: str                            # delivered, open, bounce, dropped ...
    sg_message_id: Optional[str] = None  # maps to Message.sendgrid_message_id
    timestamp: Optional[int] = None      # unix epoch
    email: Optional[str] = None
    reason: Optional[str] = None         # bounce reason

    model_config = {"extra": "allow"}    # SendGrid adds many extra fields


class SendGridWebhookPayload(BaseModel):
    """SendGrid sends an array of events."""
    events: List[SendGridEvent]

    model_config = {"extra": "allow"}
