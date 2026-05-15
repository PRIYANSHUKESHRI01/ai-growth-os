"""
app/adapters/base_adapter.py
─────────────────────────────
Abstract base class for all source adapters.

Enterprise Feature #4 — Source Reliability Scoring:
  Every concrete adapter declares a `reliability_score` (0.0–1.0) that gets
  embedded in `EnrichedLead.source_reliability_score`. This score propagates
  into the final confidence calculation, so leads from high-trust sources
  receive boosted confidence.

Implementing a new adapter:
  1. Subclass BaseSourceAdapter
  2. Set `source_name` and `reliability_score`
  3. Implement `search(filters)` and `parse_results(raw)`
  4. Register in `app/adapters/__init__.py`
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdapterConfig:
    """Optional per-adapter rate-limit and retry config."""
    requests_per_minute: int = 60
    max_results_per_call: int = 100
    retry_attempts: int = 3
    retry_delay_seconds: float = 2.0
    timeout_seconds: float = 30.0


class BaseSourceAdapter(ABC):
    """
    Plugin interface for lead discovery source adapters.

    Each adapter is responsible for:
      1. Executing a search against its data source (API, scraper, DB, etc.)
      2. Parsing and returning results in the canonical raw-lead schema
    """

    # ── Concrete adapters MUST define these ───────────────────────────────────
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier, e.g. 'mock', 'apollo', 'linkedin_sales_nav'."""
        ...

    @property
    def reliability_score(self) -> float:
        """
        Enterprise Feature #4 — Source Reliability Score.
        Range: 0.0 (unreliable) to 1.0 (authoritative).
        Override in concrete adapters. Default: 0.5.
        """
        return 0.5

    @property
    def config(self) -> AdapterConfig:
        """Rate-limit and retry config. Override to customise."""
        return AdapterConfig()

    # ── Required interface ────────────────────────────────────────────────────

    @abstractmethod
    def search(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Execute a search against the data source.

        Args:
            filters: ICP filters dict — keys may include:
                     industry, title_keywords, company_size_min/max,
                     location, keywords, domain, max_results

        Returns:
            List of raw result dicts (source-specific schema).
        """
        ...

    @abstractmethod
    def parse_results(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Normalise raw source results into the canonical raw-lead schema.

        Canonical schema (all fields optional except 'source'):
            {
                "source":       str,   # e.g. "mock"
                "first_name":   str | None,
                "last_name":    str | None,
                "full_name":    str | None,
                "email":        str | None,
                "title":        str | None,
                "company_name": str | None,
                "domain":       str | None,
                "linkedin_url": str | None,
                "phone":        str | None,
                "industry":     str | None,
                "location":     str | None,
                "source_url":   str | None,
            }
        """
        ...

    # ── Convenience method (orchestrated by DiscoveryService) ─────────────────

    def discover(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """
        End-to-end: search → parse → attach reliability metadata.
        Called by DiscoveryService. Do NOT override unless necessary.
        """
        logger.info(
            "[%s] Starting discovery search | filters=%s | reliability=%.2f",
            self.source_name, filters, self.reliability_score,
        )
        start = time.monotonic()

        raw = self.search(filters)
        logger.info("[%s] Raw results: %d items", self.source_name, len(raw))

        parsed = self.parse_results(raw)

        # Stamp source provenance on every result
        for lead in parsed:
            lead["source"] = self.source_name
            lead["source_reliability_score"] = self.reliability_score

        elapsed = time.monotonic() - start
        logger.info(
            "[%s] Discovery complete | leads=%d | elapsed=%.2fs",
            self.source_name, len(parsed), elapsed,
        )
        return parsed
