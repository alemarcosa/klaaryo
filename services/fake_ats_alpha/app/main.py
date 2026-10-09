"""Fake ATS Alpha - FastAPI application."""
from __future__ import annotations

from datetime import datetime, timezone
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


app = FastAPI(title="Fake ATS Alpha", lifespan=lifespan)


@app.get("/api/applications")
def list_applications(since: str | None = Query(default=None)):
    records = load_records(tracker)

    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail=f"Invalid 'since' format: {since}")
        records = [
            r for r in records
            if datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) > since_dt
        ]

    return records


@app.get("/api/applications/{application_id}")
def get_application(application_id: str):
    records = load_records(tracker)
    for r in records:
        if r["id"] == application_id:
            return r
    raise HTTPException(status_code=404, detail="Application not found")
