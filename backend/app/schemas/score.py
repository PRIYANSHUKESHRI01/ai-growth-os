"""
app/schemas/score.py
─────────────────────
Pydantic schemas for lead scoring — v2.0 two-layer scoring with tags.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


def compute_lead_tag(final_score: float) -> str:
    """Compute lead tag from final_score: HOT 🔥 / WARM / COLD."""
    if final_score >= 0.8:
        return "HOT 🔥"
    elif final_score >= 0.5:
        return "WARM"
    return "COLD"


def compute_intent_label(final_score: float) -> str:
    """Compute business-level intent label."""
    if final_score >= 0.90:
        return "Very High Intent"
    elif final_score >= 0.75:
        return "High Intent"
    elif final_score >= 0.50:
        return "Medium Intent"
    return "Low Intent"


class LeadScoreResponse(BaseModel):
    id: str
    lead_id: str
    reply_probability: float
    conversion_probability: float
    value_score: float
    confidence_score: float
    signal_score: float
    previous_score: Optional[float] = None
    raw_score: Optional[float] = None
    smoothed_score: Optional[float] = None
    final_score: float
    model_version: str
    tag: Optional[str] = None
    intent_label: Optional[str] = None
    explanation: Optional[dict] = None
    scored_at: datetime

    model_config = {
        "from_attributes": True,
        "protected_namespaces": ()
    }


class LeadExplanationResponse(BaseModel):
    """Response for GET /leads/{id}/explanation."""
    lead_id: str
    score: float
    smoothed_score: Optional[float] = None
    value_score: float
    confidence_score: float
    signal_score: float
    tag: str
    intent_label: str
    top_reasons: List[str]
    value_factors: List[str]
    confidence_factors: List[str]
    summary: str
    reasons: List[str]  # Kept for backward compatibility if needed
