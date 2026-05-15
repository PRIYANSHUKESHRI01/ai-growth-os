"""
app/providers/__init__.py
──────────────────────────
Enrichment provider registry + waterfall chain definition.

The waterfall order determines which provider is tried first.
If the primary fails or returns incomplete data, the next provider
in the chain is attempted automatically.
"""
from app.modules.lead_discovery.providers.base_provider import BaseEnrichmentProvider
from app.modules.lead_discovery.providers.mock_provider import MockPrimaryProvider, MockFallbackProvider

# ── Provider Registry ─────────────────────────────────────────────────────────
_PROVIDER_REGISTRY: dict[str, type[BaseEnrichmentProvider]] = {
    "mock_primary":  MockPrimaryProvider,
    "mock_fallback": MockFallbackProvider,
    # Future:
    # "clearbit":    ClearbitProvider,
    # "hunter":      HunterProvider,
    # "apollo":      ApolloProvider,
    # "pdl":         PeopleDataLabsProvider,
}

# ── Waterfall Chain (ordered: most trusted → least trusted) ───────────────────
WATERFALL_CHAIN: list[str] = [
    "mock_primary",
    "mock_fallback",
]


def get_provider(name: str) -> BaseEnrichmentProvider:
    cls = _PROVIDER_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown enrichment provider '{name}'. "
            f"Available: {list(_PROVIDER_REGISTRY.keys())}"
        )
    return cls()


def get_waterfall_chain() -> list[BaseEnrichmentProvider]:
    """Return instantiated providers in waterfall order."""
    return [get_provider(name) for name in WATERFALL_CHAIN]


__all__ = [
    "BaseEnrichmentProvider",
    "MockPrimaryProvider",
    "MockFallbackProvider",
    "get_provider",
    "get_waterfall_chain",
    "WATERFALL_CHAIN",
]
