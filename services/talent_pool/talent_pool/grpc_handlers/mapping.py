"""Proto <-> DTO mapping for the TalentPool gRPC service."""
from __future__ import annotations

from datetime import datetime, timezone

from google.protobuf.timestamp_pb2 import Timestamp

from klaaryo_contracts import talent_pool_pb2
from talent_pool.managers.dto import CandidateData, CandidateDTO

# Proto enum to internal string
_STATUS_FROM_PROTO = {
    talent_pool_pb2.INTERNAL_STATUS_NEW: "new",
    talent_pool_pb2.INTERNAL_STATUS_IN_REVIEW: "in_review",
    talent_pool_pb2.INTERNAL_STATUS_REJECTED: "rejected",
    talent_pool_pb2.INTERNAL_STATUS_HIRED: "hired",
}

# Internal string to proto enum
_STATUS_TO_PROTO = {v: k for k, v in _STATUS_FROM_PROTO.items()}


def _ts_to_datetime(ts: Timestamp) -> datetime:
    return ts.ToDatetime().replace(tzinfo=timezone.utc)


def _datetime_to_ts(dt: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


def proto_to_candidate_data(msg: talent_pool_pb2.NormalizedCandidate) -> CandidateData:
    status = _STATUS_FROM_PROTO.get(msg.internal_status)
    if status is None:
        raise ValueError(f"Unknown internal_status: {msg.internal_status}")
    return CandidateData(
        external_id=msg.external_id,
        ats_source=msg.ats_source,
        first_name=msg.first_name,
        last_name=msg.last_name,
        email=msg.email,
        phone=msg.phone,
        age=msg.age,
        job_external_id=msg.job_external_id,
        internal_status=status,
        applied_at=_ts_to_datetime(msg.applied_at),
    )


def candidate_dto_to_proto(dto: CandidateDTO) -> talent_pool_pb2.Candidate:
    data = talent_pool_pb2.NormalizedCandidate(
        external_id=dto.external_id,
        ats_source=dto.ats_source,
        first_name=dto.first_name,
        last_name=dto.last_name,
        email=dto.email,
        phone=dto.phone,
        age=dto.age,
        job_external_id=dto.job_external_id,
        internal_status=_STATUS_TO_PROTO.get(dto.internal_status, talent_pool_pb2.INTERNAL_STATUS_UNSPECIFIED),
        applied_at=_datetime_to_ts(dto.applied_at),
    )
    return talent_pool_pb2.Candidate(
        candidate_pk=dto.candidate_pk,
        data=data,
        created_at=_datetime_to_ts(dto.created_at),
        updated_at=_datetime_to_ts(dto.updated_at),
    )
