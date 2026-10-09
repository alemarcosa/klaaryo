"""Fake ATS Beta - FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.store import ChangeTracker, init_data, load_records

tracker = ChangeTracker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_data()
    # Load once at startup to initialize hashes
    load_records(tracker)
    yield


app = FastAPI(title="Fake ATS Beta", lifespan=lifespan)


@app.get("/v2/candidates")
def list_candidates(updated_after: int | None = Query(default=None)):
    records = load_records(tracker)

    if updated_after is not None:
        records = [
            r for r in records
            if r.get("updated_timestamp", r["submitted_timestamp"]) > updated_after
        ]

    return records


@app.get("/v2/candidates/{candidate_uuid}")
def get_candidate(candidate_uuid: str):
    records = load_records(tracker)
    for r in records:
        if r["candidate_uuid"] == candidate_uuid:
            return r
    raise HTTPException(status_code=404, detail="Candidate not found")
