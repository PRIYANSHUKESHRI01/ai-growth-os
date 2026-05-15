"""
app/ml/signal_scorer.py
────────────────────────
Two-layer weighted scoring engine: VALUE + CONFIDENCE.

VALUE signals measure the lead's business potential:
  - ML prediction, decision-maker status, engagement, company presence

CONFIDENCE signals measure data quality / verification:
  - Email domain quality (weak signal, no penalty), name quality, LinkedIn

Final formula:
  final_score = value_score × (0.7 + 0.3 × confidence_score)

Weights are configurable via environment variables for runtime tuning.
"""
import os
from typing import Dict, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)


def _env_float(key: str, default: float) -> float:
    """Read a float from environment, falling back to default."""
    val = os.environ.get(key)
    if val is not None:
        try:
            return float(val)
        except ValueError:
            logger.warning("Invalid float for env %s=%s, using default %.2f", key, val, default)
    return default


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Normalize weights to sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        total = 1.0
    return {k: v / total for k, v in weights.items()}


class SignalScorer:
    """
    Two-layer scorer: VALUE (business potential) + CONFIDENCE (data quality).

    All signal values are expected in [0, 1].
    Each layer's weights are normalised to sum to 1.0.
    """

    def __init__(self) -> None:
        # ── VALUE weights (business potential, NOT email type) ─────────
        raw_value = {
            "is_decision_maker":  _env_float("WEIGHT_DECISION_MAKER", 0.30),
            "title_score":        _env_float("WEIGHT_TITLE_SCORE", 0.25),
            "engagement_score":   _env_float("WEIGHT_ENGAGEMENT", 0.20),
            "has_company":        _env_float("WEIGHT_HAS_COMPANY", 0.15),
            "is_referral":        _env_float("WEIGHT_IS_REFERRAL", 0.10),
        }
        self.value_weights = _normalize_weights(raw_value)

        # ── CONFIDENCE weights (data quality / verification) ──────────
        raw_confidence = {
            "name_quality":       _env_float("WEIGHT_NAME_QUALITY", 0.35),
            "has_linkedin":       _env_float("WEIGHT_HAS_LINKEDIN", 0.30),
            "email_domain_score": _env_float("WEIGHT_EMAIL_DOMAIN", 0.20),
            "is_business_email":  _env_float("WEIGHT_BUSINESS_EMAIL", 0.15),
        }
        self.confidence_weights = _normalize_weights(raw_confidence)

        logger.info(
            "SignalScorer initialised — value_weights: %s, confidence_weights: %s",
            {k: round(v, 4) for k, v in self.value_weights.items()},
            {k: round(v, 4) for k, v in self.confidence_weights.items()},
        )

    @staticmethod
    def _weighted_sum(signals: Dict[str, float], weights: Dict[str, float]) -> float:
        """Compute clamped weighted sum."""
        score = 0.0
        for name, weight in weights.items():
            value = max(0.0, min(1.0, float(signals.get(name, 0.0))))
            score += weight * value
        return max(0.0, min(1.0, score))

    def compute_value_score(self, signals: Dict[str, float]) -> float:
        """Compute VALUE score — business potential of the lead."""
        return round(self._weighted_sum(signals, self.value_weights), 4)

    def compute_confidence_score(self, signals: Dict[str, float]) -> float:
        """Compute CONFIDENCE score — data quality / verification level."""
        return round(self._weighted_sum(signals, self.confidence_weights), 4)

    def compute_signal_score(self, signals: Dict[str, float]) -> float:
        """
        Backward-compatible composite signal score.
        Same as compute_scores() but returns only the final blended score.
        """
        _, _, final = self.compute_scores(signals)
        return final

    def compute_scores(self, signals: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Full two-layer scoring.

        Returns:
            (value_score, confidence_score, blended_signal_score)

        Formula:
            blended = value_score × (0.7 + 0.3 × confidence_score)
        """
        value = self.compute_value_score(signals)
        confidence = self.compute_confidence_score(signals)
        blended = value * (0.7 + 0.3 * confidence)
        blended = round(max(0.0, min(1.0, blended)), 4)
        return value, confidence, blended

    def get_weights(self) -> Dict[str, Dict[str, float]]:
        """Return current weight configuration (for inspection/debugging)."""
        return {
            "value": dict(self.value_weights),
            "confidence": dict(self.confidence_weights),
        }


# Module-level singleton
signal_scorer = SignalScorer()
