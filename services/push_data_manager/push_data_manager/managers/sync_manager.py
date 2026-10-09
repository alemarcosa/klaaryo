"""Sync manager: orchestrates the pull-normalize-push cycle."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from django.conf import settings

from push_data_manager.adapters.ats.base import AtsUnavailable
from push_data_manager.adapters.ats.registry import build_adapter as default_adapter_factory
from push_data_manager.adapters.ats.registry import UnknownAtsSource as AdapterUnknownAtsSource
from push_data_manager.adapters.schema import NormalizationError
from push_data_manager.adapters.talent_pool_client import (
    TalentPoolClient,
    TalentPoolUnavailable,
)
from push_data_manager.db_models.models import SyncRun
from push_data_manager.managers.candidate_rules import validate
from push_data_manager.managers.dto import SyncReport, SyncStatus
from push_data_manager.managers.exceptions import SyncFailed, UnknownAtsSource
from push_data_manager.utils.dates import to_iso_z

logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(
        self,
        adapter_factory: Callable = default_adapter_factory,
        talent_pool: TalentPoolClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._talent_pool = talent_pool or TalentPoolClient(
            target=settings.TALENT_POOL_GRPC_TARGET,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run(self, source: str) -> SyncReport:
        # Build adapter
        try:
            adapter = self._adapter_factory(source)
        except AdapterUnknownAtsSource as e:
            raise UnknownAtsSource(str(e)) from e

        # Determine cursor
        prev_run = (
            SyncRun.objects.filter(ats_source=source, status="success")
            .order_by("-finished_at")
            .first()
        )
        prev_cursor = prev_run.cursor if prev_run else None

        now = self._clock()
        if prev_cursor:
            since = prev_cursor
            query_since = since - timedelta(seconds=settings.SYNC_CURSOR_OVERLAP_SECONDS)
        else:
            since = now - timedelta(days=settings.SYNC_INITIAL_LOOKBACK_DAYS)
            query_since = since

        # Create run record
        run = SyncRun.objects.create(ats_source=source, since=query_since)

        # Fetch
        try:
            records = adapter.fetch_since(query_since)
        except AtsUnavailable as e:
            run.status = "failed"
            run.error = str(e)
            run.finished_at = self._clock()
            run.save()
            raise SyncFailed(
                partial_report=self._build_report(source, run, since, prev_cursor),
                reason=str(e),
            ) from e

        # Counters
        pulled = len(records)
        pushed = 0
        skipped = 0
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        skipped_reasons: dict[str, int] = {}
        skipped_details: list[dict] = []
        max_watermark = prev_cursor

        for raw in records:
            # Normalize
            try:
                candidate = adapter.normalize(raw)
                validate(candidate)
            except NormalizationError as e:
                skipped += 1
                reason_key = str(e.reason)
                skipped_reasons[reason_key] = skipped_reasons.get(reason_key, 0) + 1
                skipped_details.append({
                    "external_id": raw.external_id or "?",
                    "reason": reason_key,
                })
                logger.info(
                    "[SKIP] source=%s external_id=%s reason=%s detail=%s",
                    source, raw.external_id, e.reason, e.detail,
                )
                continue

            # Push to talent pool
            try:
                outcome = self._talent_pool.upsert(candidate)
            except NormalizationError as e:
                # Rejected by talent pool
                skipped += 1
                reason_key = str(e.reason)
                skipped_reasons[reason_key] = skipped_reasons.get(reason_key, 0) + 1
                skipped_details.append({
                    "external_id": raw.external_id or "?",
                    "reason": reason_key,
                })
                logger.info(
                    "[SKIP] source=%s external_id=%s reason=%s detail=%s",
                    source, raw.external_id, e.reason, e.detail,
                )
                continue
            except TalentPoolUnavailable as e:
                # Infrastructure failure: stop, don't advance cursor
                run.status = "failed"
                run.error = str(e)
                run.pulled = pulled
                run.pushed = pushed
                run.skipped = skipped
                run.created = created_count
                run.updated = updated_count
                run.unchanged = unchanged_count
                run.skipped_reasons = skipped_reasons
                run.skipped_details = skipped_details
                run.finished_at = self._clock()
                run.save()
                raise SyncFailed(
                    partial_report=self._build_report(source, run, since, prev_cursor),
                    reason=str(e),
                ) from e

            pushed += 1
            if outcome.created:
                created_count += 1
            elif outcome.changed_fields:
                updated_count += 1
            else:
                unchanged_count += 1

            # Track watermark
            if raw.watermark:
                if max_watermark is None or raw.watermark > max_watermark:
                    max_watermark = raw.watermark

        # Success
        new_cursor = max_watermark
        run.status = "success"
        run.cursor = new_cursor
        run.pulled = pulled
        run.pushed = pushed
        run.skipped = skipped
        run.created = created_count
        run.updated = updated_count
        run.unchanged = unchanged_count
        run.skipped_reasons = skipped_reasons
        run.skipped_details = skipped_details
        run.finished_at = self._clock()
        run.save()

        assert pulled == pushed + skipped, f"pulled={pulled} != pushed={pushed} + skipped={skipped}"

        return self._build_report(source, run, since, new_cursor)

    def status(self, source: str) -> SyncStatus:
        runs = SyncRun.objects.filter(ats_source=source)
        if not runs.exists():
            raise UnknownAtsSource(f"No sync runs for source: {source}")

        last_success = runs.filter(status="success").order_by("-finished_at").first()

        # Total pushed and skipped across ALL runs (including failed)
        from django.db.models import Sum
        totals = runs.aggregate(
            total_pushed=Sum("pushed"),
            total_skipped=Sum("skipped"),
        )

        return SyncStatus(
            ats_source=source,
            last_sync_at=to_iso_z(last_success.finished_at) if last_success and last_success.finished_at else None,
            total_pushed=totals["total_pushed"] or 0,
            total_skipped=totals["total_skipped"] or 0,
            cursor=to_iso_z(last_success.cursor) if last_success and last_success.cursor else None,
        )

    def _build_report(
        self, source: str, run: SyncRun, since: datetime, cursor: datetime | None,
    ) -> SyncReport:
        return SyncReport(
            ats_source=source,
            pulled=run.pulled,
            pushed=run.pushed,
            skipped=run.skipped,
            skipped_reasons=run.skipped_reasons or {},
            created=run.created,
            updated=run.updated,
            unchanged=run.unchanged,
            since=to_iso_z(since),
            cursor=to_iso_z(cursor) if cursor else "",
        )
