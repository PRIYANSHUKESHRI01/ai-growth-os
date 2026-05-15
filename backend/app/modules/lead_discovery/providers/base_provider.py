"""
app/providers/base_provider.py
───────────────────────────────
Abstract base class for all enrichment providers.

Enrichment providers are responsible for filling in missing fields
on a lead that came from a source adapter. They are executed in
waterfall order: if the primary provider fills all required fields,
fallback providers are skipped.

Circuit Breaker (Architecture Add-on #1):
  `is_available()` checks a Redis flag set by EnrichmentService when
  a provider fails 3+ consecutive times. Auto-clears after CIRCUIT_BREAK_TTL.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# Fields considered "critical" — if any are missing, waterfall continues
CRITICAL_FIELDS = {"email", "company_name", "first_name"}

# Enrichment fields that providers should attempt to fill
ENRICHABLE_FIELDS = {
    "email", "first_name", "last_name", "full_name", "title",
    "company_name", "domain", "linkedin_url", "phone", "industry", "location",
}


class BaseEnrichmentProvider(ABC):
    """
    Plugin interface for enrichment providers.

    Each provider implements `enrich(lead_data)` and returns a dict
    of field updates. The EnrichmentService merges results in waterfall order.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier, e.g. 'mock_primary', 'clearbit', 'hunter'."""
        ...

    @property
    def priority(self) -> int:
        """
        Lower number = higher priority in waterfall chain.
        Default: 50. Override in concrete providers.
        """
        return 50

    def is_available(self, redis_client: Any = None) -> bool:
        """
        Circuit breaker check (Architecture Add-on #1).
        Returns False if this provider has been circuit-broken in Redis.
        Falls back to True if Redis is unavailable (fail-open).
        """
        if redis_client is None:
            return True
        try:
            key = f"circuit_break:{self.provider_name}"
            broken = redis_client.get(key)
            if broken:
                logger.warning(
                    "[%s] Circuit breaker OPEN — skipping provider", self.provider_name
                )
                return False
            return True
        except Exception:
            logger.warning(
                "[%s] Redis unavailable for circuit check — fail-open", self.provider_name
            )
            return True

    def missing_critical_fields(self, lead: dict[str, Any]) -> set[str]:
        """Return critical fields that are empty/None in the lead dict."""
        return {
            f for f in CRITICAL_FIELDS
            if not lead.get(f)
        }

    def enrichment_coverage(self, result: dict[str, Any]) -> float:
        """
        Calculate what fraction of enrichable fields were filled.
        Used by EnrichmentService to compute enrichment_rate.
        """
        filled = sum(1 for f in ENRICHABLE_FIELDS if result.get(f))
        return round(filled / len(ENRICHABLE_FIELDS), 3)

    @abstractmethod
    def enrich(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a lead with additional data.

        Args:
            lead_data: Current lead fields (may be partially filled).

        Returns:
            Dict of field updates. Only include fields this provider
            can actually supply — do NOT return empty strings.
            Also include field-level provenance keys:
              email_source, email_field_confidence,
              company_source, company_field_confidence,
              name_source, name_field_confidence
        """
        ...
