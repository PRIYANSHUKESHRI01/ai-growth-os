"""
app/modules/lead_discovery/adapters/apollo_adapter.py
────────────────────────────────────────────────────
ApolloSourceAdapter — Connects to Apollo.io people search API.

Implements production-grade features:
- Redis-based deduplication
- Exponential backoff for 429/5xx errors
- Strict normalization
- Smart fallback to MockSourceAdapter
- Cost protection caps
- Structured observability logging
"""
from __future__ import annotations

import os
import time
import json
import uuid
import hashlib
import logging
from typing import Any
import redis
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.modules.lead_discovery.adapters.base_adapter import BaseSourceAdapter, AdapterConfig
from app.modules.lead_discovery.adapters.mock_adapter import MockSourceAdapter
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Fallback adapter instance
_MOCK_FALLBACK = MockSourceAdapter()

# Cost Protection Limits
MAX_PAGES_PER_JOB = 5  # Prevents runaway API usage
MAX_RESULTS_PER_JOB = 200

# Redis TTL for deduplication (1 hour)
DEDUPE_CACHE_TTL = 3600

def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

class ApolloSourceAdapter(BaseSourceAdapter):
    """
    Production-grade adapter for Apollo.io.
    """

    @property
    def source_name(self) -> str:
        return "apollo"

    @property
    def reliability_score(self) -> float:
        return 0.85

    @property
    def config(self) -> AdapterConfig:
        return AdapterConfig(
            requests_per_minute=50,
            max_results_per_call=MAX_RESULTS_PER_JOB,
            retry_attempts=3,
            retry_delay_seconds=2.0,
            timeout_seconds=15.0
        )

    def _get_api_key(self) -> str:
        key = os.environ.get("APOLLO_API_KEY") or getattr(get_settings(), "APOLLO_API_KEY", None)
        return key or ""

    def search(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        api_key = self._get_api_key()
        max_results = min(int(filters.get("max_results", 10)), self.config.max_results_per_call)

        # 1. Deduplication Optimization
        cache_key = self._generate_cache_key(filters)
        redis_client = get_redis_client()
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info("[Apollo] cache hit for query: %s", filters)
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("[Apollo] Redis cache read failed: %s", e)

        # 2. Main API Flow with Retry and Smart Fallback
        if not api_key:
            logger.error("[Apollo] Apollo API key not configured")
            raise ValueError("Apollo adapter unavailable: missing API key")

        logger.info("[Apollo] API call started")
        session = self._build_retry_session()
        url = "https://api.apollo.io/v1/mixed_people/search"
        payload = self._build_payload(filters, api_key)
        
        all_results = []
        page = 1

        try:
            while len(all_results) < max_results and page <= MAX_PAGES_PER_JOB:
                payload["page"] = page
                per_page = min(100, max_results - len(all_results))
                payload["per_page"] = per_page

                start_time = time.monotonic()
                response = session.post(url, json=payload, timeout=self.config.timeout_seconds)
                elapsed = time.monotonic() - start_time

                if response.status_code == 400:
                    logger.error("[Apollo] 400 Bad Request: %s", response.text)
                    break # Don't retry 400
                
                response.raise_for_status()
                data = response.json()
                
                people = data.get("people", [])
                cnt = len(people)
                
                logger.info("[Apollo] fetched=%d page=%d expected=%d total_time=%.2fs", cnt, page, per_page, elapsed)
                
                all_results.extend(people)

                if cnt < per_page:
                    break # No more results available
                
                page += 1
                
                # Basic rate limit pacing if multiple pages
                if page <= MAX_PAGES_PER_JOB:
                    time.sleep(1.0)
                
            # Truncate strictly to max_results just in case
            all_results = all_results[:max_results]

            # Cache successful results
            if all_results:
                try:
                    redis_client.setex(cache_key, DEDUPE_CACHE_TTL, json.dumps(all_results))
                except Exception as e:
                    logger.warning("[Apollo] Redis cache write failed: %s", e)
            else:
                logger.warning("[Apollo] Zero results returned from Apollo. Falling back to mock to ensure pipeline flow.")
                return self._execute_fallback(filters)

            return all_results

        except Exception as e:
            logger.error("[Apollo] API failed -> fallback triggered. Error: %s", e)
            return self._execute_fallback(filters)

    def _execute_fallback(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Smart fallback: delegates to mock adapter but flags source appropriately."""
        logger.warning("WARNING: Apollo failed, using mock fallback")
        mock_results = _MOCK_FALLBACK.search(filters)
        for r in mock_results:
            r["_custom_source"] = "apollo_mock_fallback"
        return mock_results

    def _build_payload(self, filters: dict[str, Any], api_key: str) -> dict[str, Any]:
        """Convert standard ICP filters to Apollo POST body."""
        payload: dict[str, Any] = {
            "api_key": api_key,
            "page": 1,
            "per_page": 10
        }
        
        # Industry -> q_keywords
        industry = filters.get("industry")
        if industry:
            if isinstance(industry, list):
                payload["q_keywords"] = " ".join(industry)
            else:
                payload["q_keywords"] = str(industry)

        # Titles -> person_titles
        titles = filters.get("title_keywords")
        if titles and isinstance(titles, list):
            payload["person_titles"] = titles

        # Size -> organization_num_employees_ranges
        size = filters.get("company_size")
        if size:
            if isinstance(size, str):
                payload["organization_num_employees_ranges"] = [size]
            elif isinstance(size, list):
                payload["organization_num_employees_ranges"] = size

        return payload

    def _build_retry_session(self) -> requests.Session:
        """Configure exponential backoff for 429 and 5xx."""
        session = requests.Session()
        retry = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_delay_seconds,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        # Ensure correct headers
        session.headers.update({
            "Cache-Control": "no-cache",
            "Content-Type": "application/json"
        })
        return session

    def _generate_cache_key(self, filters: dict[str, Any]) -> str:
        """Creates a stable Redis cache key based on search filters."""
        stable_str = json.dumps(filters, sort_keys=True)
        h = hashlib.sha256(stable_str.encode()).hexdigest()
        return f"apollo:search:{h}"

    def parse_results(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strict normalization and mapping to RawLead format."""
        
        # If it's a fallback result, parse using mock adapter
        if raw and raw[0].get("_custom_source") == "apollo_mock_fallback":
            parsed = _MOCK_FALLBACK.parse_results(raw)
            # Override the source so it's transparent this was a fallback
            for p in parsed:
                p["source"] = "apollo_mock_fallback"
            return parsed

        parsed_results = []
        for r in raw:
            # Safely extract Apollo structure
            first_name = r.get("first_name") or ""
            last_name = r.get("last_name") or ""
            full_name = f"{first_name} {last_name}".strip()
            
            email = r.get("email") or ""
            # Normalization: clean email
            email = email.lower().strip() if email else None

            title = r.get("title") or ""
            # Normalization: Standardize title casing (Title Case)
            title = title.title().strip() if title else None

            org = r.get("organization") or {}
            company_name = org.get("name") or ""
            # Normalization: clean company name
            company_name = company_name.strip() if company_name else None
            domain = org.get("primary_domain") or ""

            linkedin_url = r.get("linkedin_url") or ""
            
            industry = org.get("industry") or ""
            location = r.get("city") or org.get("city") or ""
            phone = r.get("sanitized_phone") or ""

            source_url = f"https://app.apollo.io/#/people/{r.get('id')}" if r.get('id') else None

            parsed_results.append({
                "source": "apollo",
                "first_name": first_name or None,
                "last_name": last_name or None,
                "full_name": full_name or None,
                "email": email,
                "title": title,
                "company_name": company_name,
                "domain": domain or None,
                "linkedin_url": linkedin_url or None,
                "phone": phone or None,
                "industry": industry or None,
                "location": location or None,
                "source_url": source_url,
                "_raw": r,
            })
        
        return parsed_results
