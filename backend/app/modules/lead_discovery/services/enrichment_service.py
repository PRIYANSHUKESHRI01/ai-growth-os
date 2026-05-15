"""
app/services/enrichment_service.py
────────────────────────────────────
Waterfall enrichment logic with circuit breaker and field provenance.

Architecture:
  1. Iterate providers in priority order (WATERFALL_CHAIN)
  2. For each provider: check availability (circuit breaker via Redis)
  3. Merge enrichment results (later providers only fill gaps)
  4. Track field-level provenance for every key field
  5. Compute enrichment coverage and mark status

Enterprise Features integrated:
  #4 — Source reliability absorbed from adapter (already in lead_data)
  #5 — Field provenance (email_source, email_field_confidence, etc.)
  Architecture Add-on #1 — Circuit breaker (3 failures → Redis lock)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.modules.lead_discovery.providers import get_waterfall_chain
from app.modules.lead_discovery.providers.base_provider import ENRICHABLE_FIELDS, CRITICAL_FIELDS
from app.core.logging import get_logger

logger = get_logger(__name__)

_CIRCUIT_BREAK_TTL_SECONDS = 300  # 5 minutes
_CIRCUIT_BREAK_THRESHOLD = 3      # failures before breaking

# Keys that should only be set if not already present (gap-fill logic)
_GAP_FILL_KEYS = ENRICHABLE_FIELDS | {
    "email_source", "email_field_confidence",
    "company_source", "company_field_confidence",
    "name_source", "name_field_confidence",
}


class EnrichmentService:
    """
    Executes waterfall enrichment on a single lead dict.
    Stateless per-lead — the DB writes happen in the Celery task layer.
    """

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client

    # ── Public API ─────────────────────────────────────────────────────────────

    def enrich(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """
        Run all available providers in waterfall order.

        Returns:
            Enriched lead dict (merged from all providers + original data).
            Includes a '_enrichment_meta' key with provider chain details.
        """
        providers = get_waterfall_chain()
        result = dict(lead_data)  # copy, never mutate the original
        provider_chain: list[dict] = []
        all_critical_filled = False

        for provider in providers:
            # ── Circuit breaker check ────────────────────────────────────────
            if not provider.is_available(self._redis):
                provider_chain.append({
                    "provider": provider.provider_name,
                    "status": "circuit_broken",
                    "fields_added": [],
                })
                continue

            missing_before = provider.missing_critical_fields(result)

            try:
                updates = provider.enrich(result)
                fields_added = self._merge_updates(result, updates)

                # Record failure metrics reset
                self._reset_failure_count(provider.provider_name)

                coverage = provider.enrichment_coverage(result)
                provider_chain.append({
                    "provider": provider.provider_name,
                    "status": "success",
                    "fields_added": fields_added,
                    "coverage": coverage,
                })
                logger.info(
                    "[EnrichmentService] Provider '%s' ran | fields_added=%d | coverage=%.2f",
                    provider.provider_name, len(fields_added), coverage,
                )

            except Exception as exc:
                logger.error(
                    "[EnrichmentService] Provider '%s' failed: %s",
                    provider.provider_name, exc,
                )
                self._record_failure(provider.provider_name)
                provider_chain.append({
                    "provider": provider.provider_name,
                    "status": "error",
                    "error": str(exc),
                    "fields_added": [],
                })
                continue

            # Check if all critical fields are now filled
            missing_now = provider.missing_critical_fields(result)
            if not missing_now:
                all_critical_filled = True
                logger.info(
                    "[EnrichmentService] All critical fields filled after '%s' — stopping waterfall.",
                    provider.provider_name,
                )
                break

        # ── Determine enrichment status ────────────────────────────────────────
        final_coverage = self._compute_final_coverage(result)
        if final_coverage >= 0.75:
            enrichment_status = "ENRICHED"
        elif final_coverage >= 0.40:
            enrichment_status = "PARTIAL"
        else:
            enrichment_status = "FAILED"

        result["enrichment_status"] = enrichment_status
        result["_enrichment_meta"] = {
            "provider_chain": provider_chain,
            "all_critical_filled": all_critical_filled,
            "final_coverage": final_coverage,
        }

        return result

    # ── Batch API ─────────────────────────────────────────────────────────────

    def enrich_batch(
        self, leads: list[dict[str, Any]], batch_size: int = 50
    ) -> list[dict[str, Any]]:
        """
        Architecture Add-on #3 — Chunked batch processing.
        Processes leads in configurable batch_size to control memory.
        """
        results = []
        for i in range(0, len(leads), batch_size):
            chunk = leads[i : i + batch_size]
            logger.info(
                "[EnrichmentService] Processing batch %d–%d of %d",
                i + 1, min(i + batch_size, len(leads)), len(leads),
            )
            for lead in chunk:
                results.append(self.enrich(lead))
        return results

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _merge_updates(self, result: dict, updates: dict) -> list[str]:
        """
        Merge enrichment updates into result — gap-fill only.
        Returns list of field names that were actually added/updated.
        """
        added = []
        for key, value in updates.items():
            if value is None or value == "":
                continue
            # For gap-fill keys: only set if missing
            if key in _GAP_FILL_KEYS and result.get(key):
                continue
            # Provenance override keys (always update if provider provides them)
            result[key] = value
            added.append(key)
        return added

    def _compute_final_coverage(self, lead: dict) -> float:
        filled = sum(1 for f in ENRICHABLE_FIELDS if lead.get(f))
        return round(filled / len(ENRICHABLE_FIELDS), 3)

    # ── Circuit Breaker Helpers ───────────────────────────────────────────────

    def _record_failure(self, provider_name: str) -> None:
        if not self._redis:
            return
        try:
            fail_key = f"provider_fail:{provider_name}"
            count = self._redis.incr(fail_key)
            self._redis.expire(fail_key, _CIRCUIT_BREAK_TTL_SECONDS)
            if count >= _CIRCUIT_BREAK_THRESHOLD:
                circuit_key = f"circuit_break:{provider_name}"
                self._redis.setex(circuit_key, _CIRCUIT_BREAK_TTL_SECONDS, "1")
                logger.warning(
                    "[CircuitBreaker] Provider '%s' OPENED after %d failures. "
                    "Auto-reopens in %ds.",
                    provider_name, count, _CIRCUIT_BREAK_TTL_SECONDS,
                )
        except Exception:
            pass  # Redis failure must not crash enrichment

    def _reset_failure_count(self, provider_name: str) -> None:
        if not self._redis:
            return
        try:
            self._redis.delete(f"provider_fail:{provider_name}")
        except Exception:
            pass
