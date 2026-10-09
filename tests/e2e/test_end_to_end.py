"""E2E test: runs against the full Docker Compose stack.

Executed inside the 'e2e' container with access to:
- push_data_manager via HTTP
- talent_pool via gRPC
- event_logger DB via SQLite (read-only)
- ATS Alpha fixture via mounted volume
- Redis directly
"""
import json
import os
import sqlite3
import time

import grpc
import pytest
import redis
import requests

from klaaryo_contracts import talent_pool_pb2, talent_pool_pb2_grpc

PDM_URL = os.environ.get("PUSH_DATA_MANAGER_URL", "http://push_data_manager:8000")
TP_TARGET = os.environ.get("TALENT_POOL_GRPC_TARGET", "talent_pool:50051")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
EL_DB_PATH = os.environ.get("EVENT_LOGGER_DB_PATH", "/data/event_logger/db.sqlite3")
ATS_ALPHA_DATA_DIR = os.environ.get("ATS_ALPHA_DATA_DIR", "/data/ats_alpha")


def wait_for_service(url: str, timeout: int = 60) -> None:
    """Poll a URL until it responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(url, timeout=2)
            return
        except requests.ConnectionError:
            time.sleep(1)
    raise TimeoutError(f"Service at {url} not ready after {timeout}s")


def wait_for_grpc(target: str, timeout: int = 60) -> None:
    """Poll gRPC server until ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            channel = grpc.insecure_channel(target)
            stub = talent_pool_pb2_grpc.TalentPoolStub(channel)
            stub.ListCandidates(
                talent_pool_pb2.ListCandidatesRequest(limit=1),
                timeout=2,
            )
            channel.close()
            return
        except grpc.RpcError:
            time.sleep(1)
    raise TimeoutError(f"gRPC at {target} not ready after {timeout}s")


def get_event_count(db_path: str, event_type: str = "", ats_source: str = "") -> int:
    """Query event_logger SQLite DB directly."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    query = "SELECT COUNT(*) FROM event_logger_processedevent WHERE 1=1"
    params = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if ats_source:
        query += " AND ats_source = ?"
        params.append(ats_source)
    result = conn.execute(query, params).fetchone()[0]
    conn.close()
    return result


def list_candidates_grpc(ats_source: str = "") -> list:
    channel = grpc.insecure_channel(TP_TARGET)
    stub = talent_pool_pb2_grpc.TalentPoolStub(channel)
    resp = stub.ListCandidates(
        talent_pool_pb2.ListCandidatesRequest(ats_source=ats_source, limit=200),
        timeout=10,
    )
    channel.close()
    return list(resp.candidates)


@pytest.fixture(scope="module", autouse=True)
def wait_for_services():
    """Wait for all services to be ready."""
    wait_for_service(f"{PDM_URL}/api/v1/sync/alpha/status")
    wait_for_grpc(TP_TARGET)
    # Give event_logger time to connect to Redis
    time.sleep(3)


def test_end_to_end():
    """Single function with ordered steps, as specified."""

    # --- Step 1: Sync Alpha ---
    resp = requests.post(f"{PDM_URL}/api/v1/sync/alpha", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pulled"] == 13  # 14 records but alpha-1014 is out of 7-day window
    assert data["pushed"] == 7
    assert data["skipped"] == 6
    expected_skip_reasons = {
        "underage": 1,
        "missing_email": 1,
        "missing_phone": 1,
        "invalid_birth_date": 1,
        "unknown_status": 1,
        "invalid_email": 1,
    }
    assert data["skipped_reasons"] == expected_skip_reasons

    # Wait for events to propagate through outbox relay -> Redis -> event_logger
    time.sleep(3)

    # Verify via gRPC
    candidates = list_candidates_grpc(ats_source="alpha")
    assert len(candidates) == 7

    # Verify events
    created_events = get_event_count(EL_DB_PATH, event_type="candidate.created", ats_source="alpha")
    assert created_events == 7

    # --- Step 2: Sync Beta ---
    resp = requests.post(f"{PDM_URL}/api/v1/sync/beta", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pulled"] == 13
    assert data["pushed"] == 7
    assert data["skipped"] == 6

    time.sleep(3)

    candidates_beta = list_candidates_grpc(ats_source="beta")
    assert len(candidates_beta) == 7

    created_beta = get_event_count(EL_DB_PATH, event_type="candidate.created", ats_source="beta")
    assert created_beta == 7

    # --- Step 3: Second sync Alpha (idempotent, overlap) ---
    events_before = get_event_count(EL_DB_PATH, ats_source="alpha")
    resp = requests.post(f"{PDM_URL}/api/v1/sync/alpha", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    # With overlap, some records are re-pulled but no new events
    assert data["created"] == 0
    assert data["updated"] == 0

    time.sleep(2)
    events_after = get_event_count(EL_DB_PATH, ats_source="alpha")
    assert events_after == events_before  # no new events

    # --- Step 4: Modify alpha-1004 and sync ---
    # Modify fixture directly
    fixture_path = os.path.join(ATS_ALPHA_DATA_DIR, "applications.json")
    with open(fixture_path) as f:
        records = json.load(f)

    for r in records:
        if r["id"] == "alpha-1004":
            r["application_status"] = "HIRED"
            r["phone_number"] = "+39 999 8887766"
            break

    with open(fixture_path, "w") as f:
        json.dump(records, f, indent=2)

    resp = requests.post(f"{PDM_URL}/api/v1/sync/alpha", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] >= 1

    time.sleep(3)

    updated_events = get_event_count(EL_DB_PATH, event_type="candidate.updated", ats_source="alpha")
    assert updated_events >= 1

    # --- Step 5: Duplicate event via XADD ---
    # Get the last event from event_logger DB
    conn = sqlite3.connect(f"file:{EL_DB_PATH}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT payload_json FROM event_logger_processedevent ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if row:
        total_before = get_event_count(EL_DB_PATH)
        # Publish duplicate directly to Redis
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        payload = json.loads(row[0])
        r.xadd(payload["event_type"], {"payload": json.dumps(payload)})

        time.sleep(3)
        total_after = get_event_count(EL_DB_PATH)
        assert total_after == total_before  # duplicate was skipped
