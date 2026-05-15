"""
app/services/scoring_service.py
────────────────────────────────
Runs the ML + two-layer signal scoring pipeline for a list of leads.
v2.0: Includes value/confidence scoring, blended final score, and explanations.
"""
import json
from typing import List
from sqlalchemy.orm import Session

from app.repositories.lead_repository import LeadRepository
from app.repositories.score_repository import ScoreRepository
from app.modules.lead_scoring.ml.predictor import lead_scorer
from app.modules.lead_scoring.ml.signal_scorer import signal_scorer
from app.modules.lead_scoring.ml.features import extract_signals
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScoringService:
    def __init__(self, db: Session) -> None:
        self.lead_repo = LeadRepository(db)
        self.score_repo = ScoreRepository(db)

    def score_leads(self, lead_ids: List[str], user_id: str) -> List[dict]:
        """
        Score a list of leads (scoped to user_id) and persist results.
        Returns list of score dicts including value/confidence scores and explanation.
        """
        leads = self.lead_repo.get_by_ids(lead_ids, user_id)
        results = []

        for lead in leads:
            try:
                reply_prob, conversion_prob, final_score, value_score, confidence_score, explanation = (
                    lead_scorer.score_lead(lead)
                )

                # Compute blended signal score for backward compat
                signals = extract_signals(lead)
                _, _, blended_signal = signal_scorer.compute_scores(signals)

                saved_score = self.score_repo.upsert(
                    lead_id=lead.id,
                    reply_probability=reply_prob,
                    conversion_probability=conversion_prob,
                    final_score=final_score,
                    value_score=value_score,
                    confidence_score=confidence_score,
                    signal_score=blended_signal,
                    explanation=explanation,
                )
                results.append({
                    "lead_id": lead.id,
                    "reply_probability": reply_prob,
                    "conversion_probability": conversion_prob,
                    "value_score": value_score,
                    "confidence_score": confidence_score,
                    "signal_score": blended_signal,
                    "previous_score": saved_score.previous_score,
                    "raw_score": saved_score.raw_score,
                    "smoothed_score": saved_score.smoothed_score,
                    "final_score": saved_score.final_score,
                    "intent_label": saved_score.intent_label,
                    "tag": saved_score.tag,
                    "explanation": explanation,
                })
                logger.info(
                    "Scored lead_id=%s final=%.3f value=%.3f conf=%.3f",
                    lead.id, saved_score.final_score, value_score, confidence_score
                )
            except Exception as e:
                logger.error("Failed to score lead_id=%s: %s", lead.id, e)

        return results

    def score_all_user_leads(self, user_id: str) -> List[dict]:
        """Score all leads belonging to a user."""
        leads, _ = self.lead_repo.get_all(user_id=user_id, page=1, page_size=10000, with_scores=False)
        return self.score_leads([l.id for l in leads], user_id)
