"""
app/adapters/mock_adapter.py
─────────────────────────────
MockSourceAdapter — deterministic test adapter for development and CI.

Generates realistic-looking leads based on ICP filters without
hitting any external API. Reliability score is low (0.4) — correct
because mock data should contribute less to confidence.

Structure allows future real adapters (Apollo, Hunter, LinkedIn SalesNav)
to plug in by subclassing BaseSourceAdapter.
"""
from __future__ import annotations

import random
import uuid
from typing import Any

from app.modules.lead_discovery.adapters.base_adapter import BaseSourceAdapter

# ── Seed data pools ───────────────────────────────────────────────────────────

_FIRST_NAMES = [
    "Alexandra", "Benjamin", "Catherine", "David", "Elena",
    "Francisco", "Grace", "Henry", "Isabella", "James",
    "Kavya", "Liam", "Morgan", "Nathan", "Olivia",
    "Patricia", "Quentin", "Rachel", "Samuel", "Teresa",
]

_LAST_NAMES = [
    "Anderson", "Brennan", "Chen", "Davis", "Evans",
    "Fischer", "Garcia", "Harris", "Ito", "Johnson",
    "Kumar", "Lee", "Martinez", "Nguyen", "O'Brien",
    "Patel", "Quinn", "Rodriguez", "Smith", "Taylor",
]

_TITLES_BY_SENIORITY = {
    "c_suite": ["CEO", "CTO", "COO", "CFO", "Chief Product Officer"],
    "vp":      ["VP of Sales", "VP of Engineering", "VP of Marketing", "VP of Product"],
    "director":["Director of Engineering", "Director of Sales", "Director of Ops"],
    "manager": ["Engineering Manager", "Sales Manager", "Product Manager"],
    "ic":      ["Senior Software Engineer", "Account Executive", "Growth Hacker"],
}

_INDUSTRIES = [
    "SaaS", "FinTech", "HealthTech", "E-Commerce", "EdTech",
    "Cybersecurity", "AI/ML", "DevTools", "MarTech", "LegalTech",
]

_COMPANY_SUFFIXES = [
    "Inc", "Corp", "Labs", "Solutions", "Ventures",
    "Technologies", "Systems", "Innovations", "Group", "Partners",
]

_DOMAINS = [
    "acme", "nexus", "vertex", "pinnacle", "apex",
    "zenith", "synapse", "catalyst", "ignition", "momentum",
]

_LOCATIONS = [
    "San Francisco, CA", "New York, NY", "Austin, TX",
    "Boston, MA", "Chicago, IL", "Seattle, WA",
    "London, UK", "Toronto, Canada", "Berlin, Germany",
]

_COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]


class MockSourceAdapter(BaseSourceAdapter):
    """
    Mock source adapter — generates synthetic leads for testing.

    Reliability: 0.4 (mock/synthetic data has inherently lower trust).
    In production, swap for ApolloAdapter (0.85) or LinkedInAdapter (0.90).
    """

    @property
    def source_name(self) -> str:
        return "mock"

    @property
    def reliability_score(self) -> float:
        return 0.4

    def search(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Generate leads matching the provided ICP filters.
        Supported filter keys:
          - max_results (int, default: 10)
          - industry (str | list[str])
          - title_keywords (list[str])
          - company_size (str | list[str])
          - seniority_level (str: c_suite | vp | director | manager | ic)
        """
        max_results: int = int(filters.get("max_results", 10))
        industry_filter = filters.get("industry")
        title_kws: list[str] = [k.lower() for k in filters.get("title_keywords", [])]
        seniority: str = filters.get("seniority_level", "")

        results = []
        for _ in range(max_results):
            first = random.choice(_FIRST_NAMES)
            last = random.choice(_LAST_NAMES)
            domain_slug = random.choice(_DOMAINS)
            company_suffix = random.choice(_COMPANY_SUFFIXES)
            company_name = f"{domain_slug.title()} {company_suffix}"
            domain = f"{domain_slug}.io"
            industry = (
                industry_filter if isinstance(industry_filter, str)
                else random.choice(industry_filter) if isinstance(industry_filter, list)
                else random.choice(_INDUSTRIES)
            )

            # Pick title pool
            if seniority and seniority in _TITLES_BY_SENIORITY:
                title_pool = _TITLES_BY_SENIORITY[seniority]
            elif title_kws:
                # Filter pool to titles containing any keyword
                title_pool = [
                    t for level in _TITLES_BY_SENIORITY.values()
                    for t in level
                    if any(kw in t.lower() for kw in title_kws)
                ] or list(_TITLES_BY_SENIORITY["vp"])
            else:
                title_pool = [
                    t for level in _TITLES_BY_SENIORITY.values() for t in level
                ]

            title = random.choice(title_pool)

            results.append({
                "_id":         str(uuid.uuid4()),
                "firstName":   first,
                "lastName":    last,
                "email":       f"{first.lower()}.{last.lower()}@{domain}",
                "jobTitle":    title,
                "companyName": company_name,
                "companyDomain": domain,
                "linkedInUrl": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{uuid.uuid4().hex[:6]}",
                "phone":       f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
                "industry":    industry,
                "location":    random.choice(_LOCATIONS),
                "companySize": random.choice(_COMPANY_SIZES),
                "sourceUrl":   f"https://mock-source.example.com/profile/{uuid.uuid4().hex[:12]}",
            })

        return results

    def parse_results(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map MockSourceAdapter-specific keys to the canonical raw-lead schema."""
        parsed = []
        for r in raw:
            first = r.get("firstName") or ""
            last = r.get("lastName") or ""
            parsed.append({
                "source":           self.source_name,
                "first_name":       first or None,
                "last_name":        last or None,
                "full_name":        f"{first} {last}".strip() or None,
                "email":            r.get("email"),
                "title":            r.get("jobTitle"),
                "company_name":     r.get("companyName"),
                "domain":           r.get("companyDomain"),
                "linkedin_url":     r.get("linkedInUrl"),
                "phone":            r.get("phone"),
                "industry":         r.get("industry"),
                "location":         r.get("location"),
                "source_url":       r.get("sourceUrl"),
                # Preserve extra fields for raw_payload
                "_raw":             r,
            })
        return parsed
