"""
app/services/verification_service.py
──────────────────────────────────────
Verification layer for enriched leads.

Checks:
  1. Email format (RFC-5322-like regex)
  2. Domain existence (non-free email provider heuristic)
  3. Company/domain match (fuzzy)
  4. Composite confidence scores: identity, email, company

Enterprise Feature #4 — Source reliability feeds into confidence calculation.
Enterprise Feature #5 — Field-level provenance informs per-field confidence.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

_FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "icloud.com", "live.com", "msn.com",
    "protonmail.com", "mail.com", "yandex.com",
})

_DISPOSABLE_PATTERNS = re.compile(
    r"(mailinator|guerrillamail|throwam|yopmail|10minutemail|tempmail)",
    re.IGNORECASE,
)

# Source reliability influence weight in confidence calculation
_SOURCE_RELIABILITY_WEIGHT = 0.15


class VerificationService:
    """
    Stateless service — can be instantiated per request/task with no DB.
    All methods return confidence floats in [0.0, 1.0].
    """

    # ── Email Verification ─────────────────────────────────────────────────────

    def validate_email_format(self, email: str) -> tuple[bool, str]:
        """
        Returns (is_valid, reason).
        Just format + heuristic checks — no DNS lookup (keeping non-blocking).
        """
        if not email or not isinstance(email, str):
            return False, "missing"

        email = email.strip().lower()

        if not _EMAIL_REGEX.match(email):
            return False, "invalid_format"

        domain = email.split("@")[-1]

        if _DISPOSABLE_PATTERNS.search(domain):
            return False, "disposable"

        # Basic domain structure check
        if not re.search(r"\.[a-zA-Z]{2,}$", domain):
            return False, "invalid_tld"

        return True, "ok"

    def is_business_email(self, email: str) -> bool:
        """Returns True if email domain is NOT a known free provider."""
        if not email:
            return False
        domain = email.strip().lower().split("@")[-1]
        return domain not in _FREE_EMAIL_DOMAINS

    def compute_email_confidence(
        self,
        email: str | None,
        field_confidence: float | None = None,
        source_reliability: float | None = None,
    ) -> float:
        """
        Email confidence = format_score × business_bonus × field_confidence × source_weight.
        """
        if not email:
            return 0.0

        is_valid, _ = self.validate_email_format(email)
        base = 0.85 if is_valid else 0.20
        business_bonus = 1.10 if self.is_business_email(email) else 1.0
        score = min(base * business_bonus, 1.0)

        # Blend in field-level confidence from enrichment provider (#5)
        if field_confidence is not None:
            score = 0.70 * score + 0.30 * field_confidence

        # Blend in source reliability (#4)
        if source_reliability is not None:
            score = (1 - _SOURCE_RELIABILITY_WEIGHT) * score + _SOURCE_RELIABILITY_WEIGHT * source_reliability

        return round(min(score, 1.0), 4)

    # ── Company Verification ──────────────────────────────────────────────────

    def compute_company_confidence(
        self,
        company_name: str | None,
        domain: str | None,
        field_confidence: float | None = None,
        source_reliability: float | None = None,
    ) -> float:
        """
        Company confidence based on: presence, name/domain match, provenance.
        """
        if not company_name:
            return 0.0

        base = 0.60  # Just having a company name gives baseline

        # Domain/name rough match boost
        if domain and company_name:
            company_slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
            domain_slug = re.sub(r"[^a-z0-9]", "", domain.lower().split(".")[0])
            if company_slug and domain_slug and (
                company_slug[:6] in domain_slug or domain_slug[:6] in company_slug
            ):
                base = 0.85

        if field_confidence is not None:
            base = 0.70 * base + 0.30 * field_confidence
        if source_reliability is not None:
            base = (1 - _SOURCE_RELIABILITY_WEIGHT) * base + _SOURCE_RELIABILITY_WEIGHT * source_reliability

        return round(min(base, 1.0), 4)

    # ── Identity Verification ─────────────────────────────────────────────────

    def compute_identity_confidence(
        self,
        first_name: str | None,
        last_name: str | None,
        linkedin_url: str | None,
        name_field_confidence: float | None = None,
        source_reliability: float | None = None,
    ) -> float:
        """
        Identity confidence = weighted combination of name completeness + LinkedIn presence.
        """
        score = 0.0

        if first_name and last_name:
            score += 0.50
        elif first_name or last_name:
            score += 0.25

        if linkedin_url and "linkedin.com/in/" in linkedin_url:
            score += 0.40

        if name_field_confidence is not None:
            score = 0.70 * score + 0.30 * name_field_confidence

        if source_reliability is not None:
            score = (1 - _SOURCE_RELIABILITY_WEIGHT) * score + _SOURCE_RELIABILITY_WEIGHT * source_reliability

        return round(min(score, 1.0), 4)

    # ── Combined Lead Verification ────────────────────────────────────────────

    def verify_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """
        Run all verification checks and return a results dict containing:
          - verification_status: "VERIFIED" | "INVALID" | "UNVERIFIED"
          - identity_confidence: float
          - email_confidence: float
          - company_confidence: float
          - email_valid: bool
          - is_business_email: bool
          - rejection_reason: str | None
        """
        email = lead_data.get("email")
        source_reliability = lead_data.get("source_reliability_score")

        # Email checks
        email_valid, email_reason = self.validate_email_format(email) if email else (False, "missing")
        business_email = self.is_business_email(email) if email else False

        if not email_valid and email_reason not in ("ok",):
            return {
                "verification_status": "INVALID",
                "rejection_reason": f"email_{email_reason}",
                "identity_confidence": 0.0,
                "email_confidence": 0.0,
                "company_confidence": 0.0,
                "email_valid": False,
                "is_business_email": False,
            }

        email_conf = self.compute_email_confidence(
            email,
            field_confidence=lead_data.get("email_field_confidence"),
            source_reliability=source_reliability,
        )
        company_conf = self.compute_company_confidence(
            lead_data.get("company_name"),
            lead_data.get("domain"),
            field_confidence=lead_data.get("company_field_confidence"),
            source_reliability=source_reliability,
        )
        identity_conf = self.compute_identity_confidence(
            lead_data.get("first_name"),
            lead_data.get("last_name"),
            lead_data.get("linkedin_url"),
            name_field_confidence=lead_data.get("name_field_confidence"),
            source_reliability=source_reliability,
        )

        # Determine overall verification status
        avg_conf = (email_conf + company_conf + identity_conf) / 3
        if avg_conf >= 0.60 and email_valid:
            status = "VERIFIED"
        elif avg_conf >= 0.30:
            status = "UNVERIFIED"
        else:
            status = "INVALID"

        return {
            "verification_status": status,
            "rejection_reason": None,
            "identity_confidence": identity_conf,
            "email_confidence": email_conf,
            "company_confidence": company_conf,
            "email_valid": email_valid,
            "is_business_email": business_email,
        }
