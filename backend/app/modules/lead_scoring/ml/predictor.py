"""
app/ml/predictor.py
────────────────────
ML scoring engine — v2.0 Multi-Signal Architecture.

Architecture:
  - ReplyModel:      LogisticRegression — predicts probability of email reply
  - ConversionModel: RandomForestClassifier — predicts probability of conversion
  - Both trained on a synthetic dataset (12 features) on first startup.
  - SignalScorer:    Weighted rule-based scoring from extracted signals
  - Explainer:       Human-readable explanation per lead

  final_score = 0.5 * ml_composite + 0.5 * signal_score
  ml_composite = 0.4 * reply_prob + 0.6 * conversion_prob
  enhanced_conversion = 0.5 * ml_conv + 0.2 * reply + 0.15 * is_dm + 0.15 * engagement

The dummy training provides a realistic feature distribution so the API works
out-of-the-box. Replace with real training data in production.
"""
import os
import random
import logging
from pathlib import Path
from typing import Tuple, Any, List, Dict

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from app.modules.lead_scoring.ml.features import extract_features, extract_signals
from app.modules.lead_scoring.ml.signal_scorer import signal_scorer
from app.modules.lead_scoring.ml.explainer import generate_explanation

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

REPLY_MODEL_PATH = MODEL_DIR / "reply_model_v2.pkl"
CONVERSION_MODEL_PATH = MODEL_DIR / "conversion_model_v2.pkl"
MODEL_VERSION = "v2.0"

# Number of features the models expect
NUM_FEATURES = 12


# ── Synthetic training data generation ───────────────────────────────────────

def _generate_training_data(n: int = 2000) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    random.seed(42)
    np.random.seed(42)

    X, y_reply, y_convert = [], [], []
    for _ in range(n):
        industry = random.randint(0, 9)
        company_size = random.randint(0, 7)
        title_score = round(random.uniform(0.1, 1.0), 2)
        has_linkedin = random.choice([0.0, 1.0])
        has_company = random.choice([0.0, 1.0])
        is_referral = random.choices([0.0, 1.0], weights=[0.8, 0.2])[0]
        # New features
        is_business_email = random.choices([0.0, 1.0], weights=[0.3, 0.7])[0]
        is_decision_maker = random.choices([0.0, 1.0], weights=[0.6, 0.4])[0]
        name_quality = round(random.uniform(0.2, 1.0), 2)
        engagement_score = round(random.uniform(0.1, 0.9), 2)
        email_domain_score = round(random.uniform(0.2, 0.9), 2)
        normalized_company_size = company_size / 7.0

        features = [
            industry, company_size, title_score, has_linkedin, has_company,
            is_referral, is_business_email, is_decision_maker, name_quality,
            engagement_score, email_domain_score, normalized_company_size,
        ]

        # Heuristic labels with noise — enriched with new signals
        reply_latent = (
            0.20 * title_score
            + 0.15 * has_linkedin
            + 0.10 * is_referral
            + 0.10 * has_company
            + 0.15 * is_business_email
            + 0.10 * is_decision_maker
            + 0.10 * name_quality
            + 0.10 * engagement_score
            + np.random.normal(0, 0.12)
        )
        convert_latent = (
            0.20 * title_score
            + 0.15 * (company_size / 7)
            + 0.10 * is_referral
            + 0.10 * has_linkedin
            + 0.15 * is_decision_maker
            + 0.10 * is_business_email
            + 0.10 * engagement_score
            + 0.10 * email_domain_score
            + np.random.normal(0, 0.12)
        )

        X.append(features)
        y_reply.append(1 if reply_latent > 0.40 else 0)
        y_convert.append(1 if convert_latent > 0.45 else 0)

    return np.array(X), np.array(y_reply), np.array(y_convert)


def _train_and_save_models() -> Tuple[Any, Any]:
    logger.info("Training ML v2.0 models with synthetic data (12 features)...")
    X, y_reply, y_convert = _generate_training_data()

    reply_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=500, random_state=42)),
    ])
    reply_pipeline.fit(X, y_reply)

    conversion_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RandomForestClassifier(n_estimators=100, random_state=42)),
    ])
    conversion_pipeline.fit(X, y_convert)

    joblib.dump(reply_pipeline, REPLY_MODEL_PATH)
    joblib.dump(conversion_pipeline, CONVERSION_MODEL_PATH)
    logger.info("v2.0 models saved to %s", MODEL_DIR)
    return reply_pipeline, conversion_pipeline


# ── Scorer ───────────────────────────────────────────────────────────────────

class LeadScorer:
    """Singleton-style scorer — load once per worker process."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._reply_model, self._conversion_model = self._load_or_train()
        self._initialized = True

    @staticmethod
    def _load_or_train() -> Tuple[Any, Any]:
        if REPLY_MODEL_PATH.exists() and CONVERSION_MODEL_PATH.exists():
            logger.info("Loading existing v2.0 ML models from disk...")
            return (
                joblib.load(REPLY_MODEL_PATH),
                joblib.load(CONVERSION_MODEL_PATH),
            )
        return _train_and_save_models()

    def predict_reply_probability(self, lead) -> float:
        features = np.array([extract_features(lead)])
        prob: float = self._reply_model.predict_proba(features)[0][1]
        return round(float(prob), 4)

    def predict_conversion_probability(self, lead) -> float:
        features = np.array([extract_features(lead)])
        prob: float = self._conversion_model.predict_proba(features)[0][1]
        return round(float(prob), 4)

    @staticmethod
    def compute_ml_composite(reply_prob: float, conversion_prob: float) -> float:
        """ML composite score: 0.4 * reply + 0.6 * conversion."""
        return round(0.4 * reply_prob + 0.6 * conversion_prob, 4)

    @staticmethod
    def compute_final_score(ml_composite: float, signal_score: float) -> float:
        """Blended final score: 50% ML + 50% signal."""
        score = 0.5 * ml_composite + 0.5 * signal_score
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def compute_enhanced_conversion(
        ml_conversion: float,
        reply_prob: float,
        is_decision_maker: float,
        engagement_score: float,
    ) -> float:
        """
        Enhanced conversion = 0.5*ml_conv + 0.2*reply + 0.15*DM + 0.15*engagement
        """
        enhanced = (
            0.50 * ml_conversion
            + 0.20 * reply_prob
            + 0.15 * is_decision_maker
            + 0.15 * engagement_score
        )
        return round(max(0.0, min(1.0, enhanced)), 4)

    def score_lead(self, lead) -> Tuple[float, float, float, float, float, dict]:
        """
        Full two-layer scoring pipeline.

        Returns:
            (reply_prob, conversion_prob, final_score,
             value_score, confidence_score, explanation_dict)
        """
        # 1. Extract signals
        signals = extract_signals(lead)

        # 2. ML predictions
        ml_reply = self.predict_reply_probability(lead)
        ml_conversion = self.predict_conversion_probability(lead)

        # 3. Two-layer signal scoring
        value_score, confidence_score, sig_score = signal_scorer.compute_scores(signals)

        # 4. Enhanced conversion
        conversion_prob = self.compute_enhanced_conversion(
            ml_conversion, ml_reply,
            signals.get("is_decision_maker", 0.0),
            signals.get("engagement_score", 0.0),
        )

        # 5. Final blended score: 50% ML composite + 50% two-layer signal
        ml_composite = self.compute_ml_composite(ml_reply, conversion_prob)
        final = self.compute_final_score(ml_composite, sig_score)

        # 6. Explanation
        lead_data = lead if isinstance(lead, dict) else {
            "email": getattr(lead, "email", None),
            "first_name": getattr(lead, "first_name", None),
            "last_name": getattr(lead, "last_name", None),
            "company": getattr(lead, "company", None),
            "title": getattr(lead, "title", None),
        }
        explanation = generate_explanation(
            signals=signals,
            value_score=value_score,
            confidence_score=confidence_score,
            signal_score=sig_score,
            ml_reply=ml_reply,
            ml_conversion=conversion_prob,
            lead_data=lead_data,
        )

        return ml_reply, conversion_prob, final, value_score, confidence_score, explanation


# Module-level singleton
lead_scorer = LeadScorer()

