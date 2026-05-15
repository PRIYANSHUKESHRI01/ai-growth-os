"""
app/repositories/score_repository.py
──────────────────────────────────────
CRUD for LeadScore records — v2.0 two-layer scoring.
"""
import json
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.lead_score import LeadScore
from app.schemas.score import compute_lead_tag, compute_intent_label
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScoreRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(
        self,
        lead_id: str,
        reply_probability: float,
        conversion_probability: float,
        final_score: float,
        value_score: float = 0.0,
        confidence_score: float = 0.0,
        signal_score: float = 0.0,
        explanation: Optional[dict] = None,
        model_version: str = "v2.0",
    ) -> LeadScore:
        """Create or update a lead's score, applying smoothing if updating."""
        explanation_json = json.dumps(explanation or {})
        raw_score = final_score

        existing = self.db.query(LeadScore).filter(LeadScore.lead_id == lead_id).first()
        if existing:
            previous_score = existing.final_score
            smoothed_score = 0.7 * previous_score + 0.3 * raw_score

            existing.previous_score = previous_score
            existing.raw_score = raw_score
            existing.smoothed_score = smoothed_score
            existing.final_score = smoothed_score

            existing.reply_probability = reply_probability
            existing.conversion_probability = conversion_probability
            existing.value_score = value_score
            existing.confidence_score = confidence_score
            existing.signal_score = signal_score
            existing.model_version = model_version
            existing.explanation = explanation_json
            existing.tag = compute_lead_tag(smoothed_score)
            existing.intent_label = compute_intent_label(smoothed_score)
            existing.scored_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        smoothed_score = raw_score
        score = LeadScore(
            lead_id=lead_id,
            reply_probability=reply_probability,
            conversion_probability=conversion_probability,
            value_score=value_score,
            confidence_score=confidence_score,
            signal_score=signal_score,
            raw_score=raw_score,
            smoothed_score=smoothed_score,
            final_score=smoothed_score,
            model_version=model_version,
            explanation=explanation_json,
            tag=compute_lead_tag(smoothed_score),
            intent_label=compute_intent_label(smoothed_score)
        )
        self.db.add(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def get_by_lead_id(self, lead_id: str) -> Optional[LeadScore]:
        return self.db.query(LeadScore).filter(LeadScore.lead_id == lead_id).first()

    def get_avg_score(self, lead_ids: List[str]) -> float:
        """Compute average final_score for a list of lead IDs."""
        result = (
            self.db.query(func.avg(LeadScore.final_score))
            .filter(LeadScore.lead_id.in_(lead_ids))
            .scalar()
        )
        return round(float(result or 0.0), 4)

    def get_scored_lead_ids_above_threshold(
        self, lead_ids: List[str], threshold: float
    ) -> List[str]:
        """Return lead IDs with final_score >= threshold."""
        rows = (
            self.db.query(LeadScore.lead_id)
            .filter(
                LeadScore.lead_id.in_(lead_ids),
                LeadScore.final_score >= threshold,
            )
            .all()
        )
        return [r[0] for r in rows]

    def get_top_scored_lead_ids(self, lead_ids: List[str], limit: int = 50) -> List[str]:
        """Return top lead IDs ordered by final_score descending."""
        rows = (
            self.db.query(LeadScore.lead_id)
            .filter(LeadScore.lead_id.in_(lead_ids))
            .order_by(LeadScore.final_score.desc())
            .limit(limit)
            .all()
        )
        return [r[0] for r in rows]
