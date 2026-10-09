"""REST views for the push_data_manager.

These views import ONLY from push_data_manager.managers.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from push_data_manager.managers.sync_manager import SyncManager
from push_data_manager.managers.exceptions import UnknownAtsSource, SyncFailed


@csrf_exempt
@require_POST
def sync_view(request, ats_source: str) -> JsonResponse:
    manager = SyncManager()
    try:
        report = manager.run(ats_source)
    except UnknownAtsSource:
        return JsonResponse({"error": "unknown_ats_source"}, status=404)
    except SyncFailed as e:
        return JsonResponse(
            {"error": str(e.reason), "partial": asdict(e.partial_report)},
            status=502,
        )
    return JsonResponse(asdict(report))


@require_GET
def status_view(request, ats_source: str) -> JsonResponse:
    manager = SyncManager()
    try:
        status = manager.status(ats_source)
    except UnknownAtsSource:
        return JsonResponse({"error": "unknown_ats_source"}, status=404)
    return JsonResponse(asdict(status))
