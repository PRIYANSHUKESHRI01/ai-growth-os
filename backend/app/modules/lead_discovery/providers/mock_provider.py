"""
app/providers/mock_provider.py
───────────────────────────────
Two mock enrichment providers for testing the waterfall system.

MockPrimaryProvider:
  - Simulates a high-quality enrichment API (like Clearbit/Apollo)
  - Fills ~80% of fields, high confidence
  - Occasionally leaves phone + location empty → activates fallback

MockFallbackProvider:
  - Simulates a secondary enrichment source (like Hunter/PDL)
  - Fills remaining gaps with lower confidence
  - Always succeeds (fallback must be resilient)

Enterprise Feature #5 — Field-Level Provenance:
  Both providers stamp *_source and *_field_confidence on every field they fill.
"""
from __future__ import annotations

import random
from typing import Any

from app.modules.lead_discovery.providers.base_provider import BaseEnrichmentProvider

_LOCATIONS = [
    "San Francisco, CA", "New York, NY", "Austin, TX",
    "Boston, MA", "Chicago, IL", "Seattle, WA",
    "London, UK", "Toronto, Canada", "Berlin, Germany",
]

_INDUSTRY_TO_DOMAIN_HINTS = {
    "SaaS": [".io", ".com"],
    "FinTech": [".com", ".finance"],
    "HealthTech": [".health", ".com"],
    "AI/ML": [".ai", ".io"],
}


class MockPrimaryProvider(BaseEnrichmentProvider):
    """
    Simulates a premium B2B enrichment API.

    Coverage: ~80% of fields
    Confidence range: 0.75–0.95
    Field-level provenance: stamped as 'mock_primary'
    """

    @property
    def provider_name(self) -> str:
        return "mock_primary"

    @property
    def priority(self) -> int:
        return 1  # Highest priority

    def enrich(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}

        # ── Email (fill if missing or validate existing) ───────────────────
        if not lead_data.get("email") and lead_data.get("first_name") and lead_data.get("domain"):
            first = lead_data["first_name"].lower()
            last = (lead_data.get("last_name") or "x").lower()
            domain = lead_data["domain"]
            updates["email"] = f"{first}.{last}@{domain}"
            # Enterprise Feature #5 — Field provenance
            updates["email_source"] = self.provider_name
            updates["email_field_confidence"] = round(random.uniform(0.78, 0.92), 3)
        elif lead_data.get("email"):
            updates["email_source"] = self.provider_name
            updates["email_field_confidence"] = round(random.uniform(0.82, 0.95), 3)

        # ── Company Name ──────────────────────────────────────────────────────
        if lead_data.get("company_name"):
            updates["company_source"] = self.provider_name
            updates["company_field_confidence"] = round(random.uniform(0.80, 0.95), 3)
        elif lead_data.get("domain"):
            # Infer company from domain slug
            slug = lead_data["domain"].split(".")[0].title()
            updates["company_name"] = f"{slug} Inc"
            updates["company_source"] = self.provider_name
            updates["company_field_confidence"] = round(random.uniform(0.65, 0.80), 3)

        # ── Full Name / First + Last ──────────────────────────────────────────
        if lead_data.get("first_name") or lead_data.get("last_name"):
            updates["name_source"] = self.provider_name
            updates["name_field_confidence"] = round(random.uniform(0.80, 0.95), 3)

        # ── LinkedIn URL ──────────────────────────────────────────────────────
        if not lead_data.get("linkedin_url"):
            first = (lead_data.get("first_name") or "user").lower()
            last = (lead_data.get("last_name") or "unknown").lower()
            updates["linkedin_url"] = f"https://linkedin.com/in/{first}-{last}"

        # ── Title ─────────────────────────────────────────────────────────────
        if not lead_data.get("title"):
            updates["title"] = random.choice(["VP of Sales", "Director of Growth", "Head of Partnerships"])

        # ── Industry ─────────────────────────────────────────────────────────
        if not lead_data.get("industry"):
            updates["industry"] = random.choice(["SaaS", "FinTech", "AI/ML"])

        # ── Domain ────────────────────────────────────────────────────────────
        if not lead_data.get("domain") and lead_data.get("email"):
            parts = lead_data["email"].split("@")
            if len(parts) == 2:
                updates["domain"] = parts[1]

        # ~20% chance: skip phone + location to test fallback
        if random.random() > 0.20:
            updates["phone"] = (
                lead_data.get("phone")
                or f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
            )
            updates["location"] = lead_data.get("location") or random.choice(_LOCATIONS)

        return updates


class MockFallbackProvider(BaseEnrichmentProvider):
    """
    Simulates a secondary enrichment source.

    Coverage: fills gaps left by primary (phone, location, partial email)
    Confidence range: 0.55–0.75 (lower than primary — expected)
    Field-level provenance: stamped as 'mock_fallback'
    """

    @property
    def provider_name(self) -> str:
        return "mock_fallback"

    @property
    def priority(self) -> int:
        return 2

    def enrich(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}

        # ── Fill phone if still missing ───────────────────────────────────────
        if not lead_data.get("phone"):
            updates["phone"] = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

        # ── Fill location if still missing ────────────────────────────────────
        if not lead_data.get("location"):
            updates["location"] = random.choice(_LOCATIONS)

        # ── Email provenance (lower confidence if fallback had to handle it) ──
        if not lead_data.get("email_source"):
            if lead_data.get("email"):
                updates["email_source"] = self.provider_name
                updates["email_field_confidence"] = round(random.uniform(0.55, 0.70), 3)

        # ── Company provenance ────────────────────────────────────────────────
        if not lead_data.get("company_source"):
            if lead_data.get("company_name"):
                updates["company_source"] = self.provider_name
                updates["company_field_confidence"] = round(random.uniform(0.55, 0.72), 3)

        # ── Name provenance ───────────────────────────────────────────────────
        if not lead_data.get("name_source"):
            if lead_data.get("first_name") or lead_data.get("last_name"):
                updates["name_source"] = self.provider_name
                updates["name_field_confidence"] = round(random.uniform(0.60, 0.75), 3)

        return updates
