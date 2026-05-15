"""
app/schemas/campaign.py
────────────────────────
Pydantic schemas for Campaign request / response.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.models.campaign import CampaignStatus


class CampaignRunRequest(BaseModel):
    campaign_name: str
    lead_ids: Optional[List[str]] = None  # None → use all user's leads


class CampaignRunResponse(BaseModel):
    campaign_id: str
    status: CampaignStatus
    total_leads: int
    message: str


class CampaignStatusResponse(BaseModel):
    campaign_id: str
    name: str
    status: CampaignStatus
    total_leads: int
    processed_leads: int
    failed_leads: int
    celery_task_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

    # Message breakdown
    messages_sent: int = 0
    messages_pending: int = 0
    messages_failed: int = 0
    messages_rate_limited: int = 0

    model_config = {"from_attributes": True}


class CampaignAnalyticsResponse(BaseModel):
    """Response for GET /campaign/analytics."""
    campaign_id: str
    campaign_name: str
    total_leads: int
    contacted: int
    skipped: int
    avg_score: float
    threshold: float


class CampaignResponse(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    total_leads: int
    processed_leads: int
    failed_leads: int
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    campaigns: List[CampaignResponse]
