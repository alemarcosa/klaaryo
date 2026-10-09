"""Manager-level exceptions."""
from __future__ import annotations

from push_data_manager.managers.dto import SyncReport


class UnknownAtsSource(Exception):
    """Raised when an unknown ATS source is requested."""


class SyncFailed(Exception):
    """Raised when a sync run fails due to infrastructure issues."""

    def __init__(self, partial_report: SyncReport, reason: str) -> None:
        self.partial_report = partial_report
        self.reason = reason
        super().__init__(reason)
