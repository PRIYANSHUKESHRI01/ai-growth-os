"""
app/schemas/discovery.py
─────────────────────────
Pydantic v2 schemas for Automation 2 API.

Schemas:
  - DiscoveryJobCreate    — POST /discovery/jobs body
  - DiscoveryJobResponse  — single job (with metrics + progress)
  - DiscoveryJobList      — paginated list of jobs
  - DiscoveryRunResponse  — immediate response after POST /discovery/run/{id}
  - EnrichedLeadResponse  — enriched lead with provenance fields
  - EnrichedLeadList      — paginated list
  - CreditBalance         — GET /discovery/credits response
  - CreditTopUpRequest    — admin top-up body
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Discovery Jobs ────────────────────────────────────────────────────────────

class DiscoveryJobCreate(BaseModel):
    """ICP filters for a new discovery job."""
    source_adapter: str = Field("mock", description="Source adapter to use: 'mock', 'apollo', etc.")
    industry: Optional[str] = Field(None, description="Target industry, e.g. 'SaaS'")
    title_keywords: Optional[List[str]] = Field(None, description="Job title keywords, e.g. ['VP', 'Director']")
    seniority_level: Optional[str] = Field(None, description="c_suite | vp | director | manager | ic")
    company_size: Optional[str] = Field(None, description="e.g. '51-200'")
    location: Optional[str] = Field(None, description="e.g. 'San Francisco, CA'")
    max_results: int = Field(10, ge=1, le=500, description="Max leads to discover per run")

    def to_filters(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class DiscoveryJobResponse(BaseModel):
    """Full job status with metrics, progress, and credit info."""
    id: str
    user_id: str
    status: str
    current_stage: Optional[str] = None
    source_adapter: str
    input_filters: Optional[dict] = None
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None

    # Metrics (Enterprise #2)
    total_raw: int = 0
    total_enriched: int = 0
    success_count: int = 0
    failed_count: int = 0
    enrichment_rate: Optional[float] = None

    # Progress (Enterprise #3)
    total_items: int = 0
    processed_items: int = 0

    # Credits (Enterprise #1)
    credits_used: int = 0

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DiscoveryJobListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    jobs: List[DiscoveryJobResponse]


class DiscoveryRunResponse(BaseModel):
    job_id: str
    celery_task_id: str
    status: str
    message: str


# ── Enriched Leads ────────────────────────────────────────────────────────────

class EnrichedLeadResponse(BaseModel):
    """Enriched lead with full field-level provenance."""
    id: str
    user_id: str
    job_id: Optional[str] = None

    # Contact
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None

    # Source
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_reliability_score: Optional[float] = None  # Enterprise #4

    # Field-level provenance (Enterprise #5)
    email_source: Optional[str] = None
    email_field_confidence: Optional[float] = None
    company_source: Optional[str] = None
    company_field_confidence: Optional[float] = None
    name_source: Optional[str] = None
    name_field_confidence: Optional[float] = None

    # Composite confidence scores
    identity_confidence: Optional[float] = None
    email_confidence: Optional[float] = None
    company_confidence: Optional[float] = None

    # Status
    enrichment_status: str
    verification_status: str

    # Handoff
    automation1_lead_id: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}


class EnrichedLeadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    leads: List[EnrichedLeadResponse]


# ── Credits ───────────────────────────────────────────────────────────────────

class CreditBalanceResponse(BaseModel):
    user_id: str
    discovery_credits: int
    enrichment_credits: int
    total_jobs_run: int
    total_leads_enriched: int
    updated_at: Optional[datetime] = None


class CreditTopUpRequest(BaseModel):
    discovery: int = Field(0, ge=0, description="Discovery credits to add")
    enrichment: int = Field(0, ge=0, description="Enrichment credits to add")
