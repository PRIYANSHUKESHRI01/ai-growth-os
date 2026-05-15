"""
app/models/__init__.py
Export all models so that `Base.metadata.create_all()` discovers them.
"""
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.lead import Lead
from app.models.lead_score import LeadScore
from app.models.campaign import Campaign, CampaignStatus
from app.models.message import Message, MessageStatus

# ── Automation 2 models (additive — do not break Automation 1) ────────────────
from app.models.discovery_models import (
    DiscoveryJob,
    RawLead,
    EnrichedLead,
    LeadSignal,
    DedupeKey,
    UserCredit,
    JobStatus,
    EnrichmentStatus,
    VerificationStatus,
    SignalType,
    RawLeadStatus,
)

# ── Automation 3 models (Outreach Engine) ─────────────────────────────────────
from app.models.campaign_lead import CampaignLead, CampaignLeadStatus, ReplyType
from app.models.campaign_step_stats import CampaignStepStats

__all__ = [
    # Core (Automation 1)
    "Base",
    "TimestampMixin",
    "User",
    "Lead",
    "LeadScore",
    "Campaign",
    "CampaignStatus",
    "Message",
    "MessageStatus",
    # Discovery (Automation 2)
    "DiscoveryJob",
    "RawLead",
    "EnrichedLead",
    "LeadSignal",
    "DedupeKey",
    "UserCredit",
    "JobStatus",
    "EnrichmentStatus",
    "VerificationStatus",
    "SignalType",
    "RawLeadStatus",
    # Outreach Engine (Automation 3)
    "CampaignLead",
    "CampaignLeadStatus",
    "ReplyType",
    "CampaignStepStats",
]

