"""Base ATS adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from push_data_manager.adapters.schema import NormalizedCandidate, RawApplication


class AtsUnavailable(Exception):
    """Raised when an ATS is unreachable or returns an HTTP error."""


class AtsAdapter(ABC):
    source: ClassVar[str]

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @abstractmethod
    def fetch_since(self, since: datetime) -> list[RawApplication]:
        """Fetch applications updated after `since`.

        Converts `since` to the ATS-specific format.
        Raises AtsUnavailable on HTTP/network error.
        """
        ...

    @abstractmethod
    def normalize(self, raw: RawApplication) -> NormalizedCandidate:
        """Normalize a raw application to the internal schema.

        Raises NormalizationError if the record is not translatable.
        """
        ...
