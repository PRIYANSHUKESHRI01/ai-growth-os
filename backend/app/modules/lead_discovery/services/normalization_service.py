"""
app/services/normalization_service.py
───────────────────────────────────────
Normalises enriched lead data into the canonical schema and prepares
the Automation 1 handoff payload.

Responsibilities:
  1. Title-case names, strip whitespace, format phone
  2. Extract domain from email if missing
  3. Generate composite dedupe hash (email + domain + normalized_name)
  4. Convert EnrichedLead into LeadCreate for Automation 1 insertion

Architecture Add-on #6 — Composite Dedup (SHA256 on email+domain+name).
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# E.164-ish phone normalisation
_PHONE_STRIP = re.compile(r"[^+\d]")
_DOMAIN_FROM_EMAIL = re.compile(r"@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$")


class NormalizationService:

    # ── Field Normalisation ────────────────────────────────────────────────────

    def normalize_name(self, name: str | None) -> str | None:
        if not name:
            return None
        return re.sub(r"\s+", " ", name.strip()).title()

    def normalize_email(self, email: str | None) -> str | None:
        return email.strip().lower() if email else None

    def normalize_phone(self, phone: str | None) -> str | None:
        if not phone:
            return None
        stripped = _PHONE_STRIP.sub("", phone)
        return f"+{stripped}" if stripped else None

    def normalize_domain(self, domain: str | None, email: str | None = None) -> str | None:
        if domain:
            return domain.strip().lower()
        if email:
            m = _DOMAIN_FROM_EMAIL.search(email)
            if m:
                return m.group(1).lower()
        return None

    def normalize_lead(self, raw: dict[str, Any]) -> dict[str, Any]:
        """
        Apply all normalisations to a raw enriched lead dict.
        Returns a new dict — does not mutate input.
        """
        email = self.normalize_email(raw.get("email"))
        domain = self.normalize_domain(raw.get("domain"), email)

        return {
            **raw,
            "first_name": self.normalize_name(raw.get("first_name")),
            "last_name":  self.normalize_name(raw.get("last_name")),
            "full_name":  self.normalize_name(raw.get("full_name")),
            "email":      email,
            "domain":     domain,
            "company_name": (raw.get("company_name") or "").strip().title() or None,
            "title":      (raw.get("title") or "").strip() or None,
            "industry":   (raw.get("industry") or "").strip() or None,
            "location":   (raw.get("location") or "").strip() or None,
            "phone":      self.normalize_phone(raw.get("phone")),
        }

    # ── Deduplication ─────────────────────────────────────────────────────────

    def generate_dedupe_hash(
        self,
        email: Optional[str],
        domain: Optional[str],
        full_name: Optional[str],
    ) -> str:
        """
        Architecture Add-on #6 — Composite dedup key.
        SHA256(normalised_email + domain + normalised_name).
        Returns hex digest (64 chars).
        """
        parts = [
            (email or "").lower().strip(),
            (domain or "").lower().strip(),
            (full_name or "").lower().strip(),
        ]
        raw_key = "|".join(parts)
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    # ── Automation 1 Handoff Schema ───────────────────────────────────────────

    def to_automation1_lead_create(self, enriched: dict[str, Any]) -> dict[str, Any]:
        """
        Convert normalised enriched lead into the schema expected by
        Automation 1's LeadRepository.create_many() — i.e., LeadCreate fields.

        Mapping:
          EnrichedLead.email           → Lead.email
          EnrichedLead.first_name      → Lead.first_name
          EnrichedLead.last_name       → Lead.last_name
          EnrichedLead.company_name    → Lead.company
          EnrichedLead.title           → Lead.title
          EnrichedLead.industry        → Lead.industry
          EnrichedLead.source          → Lead.source
          EnrichedLead.linkedin_url    → Lead.linkedin_url
        """
        return {
            "email":        enriched.get("email"),
            "first_name":   enriched.get("first_name"),
            "last_name":    enriched.get("last_name"),
            "company":      enriched.get("company_name"),
            "title":        enriched.get("title"),
            "industry":     enriched.get("industry"),
            "source":       f"discovery:{enriched.get('source', 'auto')}",
            "linkedin_url": enriched.get("linkedin_url"),
            "notes": (
                f"Auto-discovered via Automation 2. "
                f"identity_conf={enriched.get('identity_confidence', 0):.2f} "
                f"email_conf={enriched.get('email_confidence', 0):.2f} "
                f"company_conf={enriched.get('company_confidence', 0):.2f}"
            ),
        }
