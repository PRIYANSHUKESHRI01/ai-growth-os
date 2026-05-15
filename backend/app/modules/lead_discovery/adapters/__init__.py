"""
app/adapters/__init__.py
─────────────────────────
Source adapter registry.
Register adapters here so callers can look them up by name.
"""
from app.modules.lead_discovery.adapters.base_adapter import BaseSourceAdapter
from app.modules.lead_discovery.adapters.mock_adapter import MockSourceAdapter
from app.modules.lead_discovery.adapters.apollo_adapter import ApolloSourceAdapter

# ── Adapter Registry ──────────────────────────────────────────────────────────
_ADAPTER_REGISTRY: dict[str, type[BaseSourceAdapter]] = {
    "mock": MockSourceAdapter,
    "apollo": ApolloSourceAdapter,
    # Future adapters:
    # "linkedin_sales_nav": LinkedInSalesNavAdapter,
    # "hunter":             HunterAdapter,
}


def get_adapter(source_name: str) -> BaseSourceAdapter:
    """
    Return an instantiated adapter for the given source name.
    Raises ValueError for unknown sources.
    """
    cls = _ADAPTER_REGISTRY.get(source_name)
    if cls is None:
        raise ValueError(
            f"Unknown source adapter '{source_name}'. "
            f"Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return cls()


def list_adapters() -> list[str]:
    return list(_ADAPTER_REGISTRY.keys())


__all__ = ["BaseSourceAdapter", "MockSourceAdapter", "get_adapter", "list_adapters"]
