"""
app/core/config.py
──────────────────
Central settings loaded from environment variables via pydantic-settings.
All secrets MUST be provided via env vars — no hard-coded defaults for sensitive values.
"""
from functools import lru_cache
from typing import List

from dotenv import load_dotenv
load_dotenv(override=True)

from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str  # required — no default

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── OpenAI ───────────────────────────────────────────────────────────
    OPENAI_API_KEY: str  # required
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── SendGrid ─────────────────────────────────────────────────────────
    SENDGRID_API_KEY: str  # required
    SENDGRID_FROM_EMAIL: str  # required
    SENDGRID_FROM_NAME: str = "AI Growth OS"

    # ── Email Rate Limiting ───────────────────────────────────────────────
    EMAIL_RATE_LIMIT_PER_MINUTE: int = 10
    EMAIL_RATE_LIMIT_PER_DAY: int = 500

    # ── Scoring Engine ───────────────────────────────────────────────────
    MIN_SCORE_THRESHOLD: float = 0.5  # Leads below this are skipped in campaigns

    # Signal weights (env-configurable, auto-normalised by SignalScorer)
    WEIGHT_BUSINESS_EMAIL: float = 0.15
    WEIGHT_DECISION_MAKER: float = 0.25
    WEIGHT_NAME_QUALITY: float = 0.10
    WEIGHT_HAS_COMPANY: float = 0.10
    WEIGHT_TITLE_SCORE: float = 0.15
    WEIGHT_HAS_LINKEDIN: float = 0.05
    WEIGHT_ENGAGEMENT: float = 0.10
    WEIGHT_IS_REFERRAL: float = 0.05
    WEIGHT_EMAIL_DOMAIN: float = 0.05

    # ── Clerk Auth ───────────────────────────────────────────────────────
    # JWKS endpoint: https://clerk.com/docs/reference/backend-api/tag/JWKS
    # Format: https://<your-clerk-domain>/.well-known/jwks.json
    CLERK_JWKS_URL: str = ""  # required in production
    CLERK_SECRET_KEY: str = ""  # optional — used for server-side Clerk API calls

    # ── CORS ─────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — call this everywhere."""
    return Settings()
