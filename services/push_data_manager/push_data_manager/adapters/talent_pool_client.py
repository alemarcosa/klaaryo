"""gRPC client for the TalentPool service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from klaaryo_contracts import talent_pool_pb2, talent_pool_pb2_grpc
from push_data_manager.adapters.schema import (
    InternalStatus,
    NormalizedCandidate,
    NormalizationError,
    SkipReason,
)

_STATUS_TO_PROTO = {
    InternalStatus.NEW: talent_pool_pb2.INTERNAL_STATUS_NEW,
    InternalStatus.IN_REVIEW: talent_pool_pb2.INTERNAL_STATUS_IN_REVIEW,
    InternalStatus.REJECTED: talent_pool_pb2.INTERNAL_STATUS_REJECTED,
    InternalStatus.HIRED: talent_pool_pb2.INTERNAL_STATUS_HIRED,
}


class TalentPoolUnavailable(Exception):
    """Raised when the TalentPool gRPC service is unreachable."""


@dataclass(frozen=True)
class UpsertOutcome:
    candidate_pk: int
    created: bool
    changed_fields: list[str]


class TalentPoolClient:
    def __init__(self, target: str, timeout: float = 5.0) -> None:
        self._target = target
        self._timeout = timeout
        self._channel: grpc.Channel | None = None
        self._stub: talent_pool_pb2_grpc.TalentPoolStub | None = None

    def _ensure_channel(self) -> talent_pool_pb2_grpc.TalentPoolStub:
        if self._stub is None:
            self._channel = grpc.insecure_channel(self._target)
            self._stub = talent_pool_pb2_grpc.TalentPoolStub(self._channel)
        return self._stub

    def upsert(self, c: NormalizedCandidate) -> UpsertOutcome:
        stub = self._ensure_channel()

        ts = Timestamp()
        ts.FromDatetime(c.applied_at)

        msg = talent_pool_pb2.NormalizedCandidate(
            external_id=c.external_id,
            ats_source=c.ats_source,
            first_name=c.first_name,
            last_name=c.last_name,
            email=c.email,
            phone=c.phone,
            age=c.age,
            job_external_id=c.job_external_id,
            internal_status=_STATUS_TO_PROTO[c.internal_status],
            applied_at=ts,
        )

        try:
            result = stub.UpsertCandidate(msg, timeout=self._timeout)
        except grpc.RpcError as e:
            code = e.code()
            if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                raise TalentPoolUnavailable(f"TalentPool unavailable: {e.details()}") from e
            if code == grpc.StatusCode.INVALID_ARGUMENT:
                raise NormalizationError(
                    SkipReason.REJECTED_BY_TALENT_POOL,
                    e.details(),
                ) from e
            raise

        return UpsertOutcome(
            candidate_pk=result.candidate_pk,
            created=result.created,
            changed_fields=list(result.changed_fields),
        )
