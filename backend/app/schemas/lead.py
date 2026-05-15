"""
app/schemas/lead.py
────────────────────
Pydantic schemas for Lead request / response.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


class LeadCreate(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    source: Optional[str] = "api"
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class LeadScoreEmbed(BaseModel):
    reply_probability: float
    conversion_probability: float
    value_score: float
    confidence_score: float
    signal_score: float
    previous_score: Optional[float] = None
    raw_score: Optional[float] = None
    smoothed_score: Optional[float] = None
    final_score: float
    tag: Optional[str] = None
    intent_label: Optional[str] = None
    scored_at: datetime

    model_config = {"from_attributes": True}


class LeadResponse(BaseModel):
    id: str
    user_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    company: Optional[str]
    title: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    source: Optional[str]
    created_at: datetime
    score: Optional[LeadScoreEmbed] = None

    model_config = {"from_attributes": True}


class LeadUploadResponse(BaseModel):
    message: str
    created: int
    skipped: int
    lead_ids: List[str]


class LeadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    leads: List[LeadResponse]


class DashboardStatsResponse(BaseModel):
    total_leads: int
    avg_score: float
    hot_leads_count: int
    campaigns_count: int
