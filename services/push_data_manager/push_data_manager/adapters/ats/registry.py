"""Explicit registry of ATS adapters.

This is the ONLY place (besides the adapters themselves and settings)
where ATS names appear.
"""
from __future__ import annotations

from django.conf import settings

from push_data_manager.adapters.ats.alpha import AlphaAdapter
from push_data_manager.adapters.ats.base import AtsAdapter
from push_data_manager.adapters.ats.beta import BetaAdapter

_ADAPTERS: dict[str, type[AtsAdapter]] = {
    AlphaAdapter.source: AlphaAdapter,
    BetaAdapter.source: BetaAdapter,
}


class UnknownAtsSource(Exception):
    """Raised when an unknown ATS source is requested."""


def build_adapter(source: str) -> AtsAdapter:
    adapter_cls = _ADAPTERS.get(source)
    if adapter_cls is None:
        raise UnknownAtsSource(f"Unknown ATS source: {source}")

    ats_config = settings.ATS_SOURCES.get(source)
    if ats_config is None:
        raise UnknownAtsSource(f"ATS source '{source}' not configured in settings")

    return adapter_cls(
        base_url=ats_config["base_url"],
        timeout=settings.ATS_HTTP_TIMEOUT_SECONDS,
    )


def known_sources() -> list[str]:
    return list(_ADAPTERS.keys())
