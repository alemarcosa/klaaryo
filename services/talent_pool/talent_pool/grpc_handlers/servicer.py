"""gRPC servicer for the TalentPool service."""
from __future__ import annotations

import grpc

from klaaryo_contracts import talent_pool_pb2, talent_pool_pb2_grpc
from talent_pool.managers.candidate_manager import CandidateManager
from talent_pool.managers.exceptions import CandidateNotFound, InvalidCandidate
from talent_pool.grpc_handlers.mapping import (
    proto_to_candidate_data,
    candidate_dto_to_proto,
)


class TalentPoolServicer(talent_pool_pb2_grpc.TalentPoolServicer):
    def __init__(self, manager: CandidateManager) -> None:
        self._manager = manager

    def UpsertCandidate(self, request, context):
        try:
            data = proto_to_candidate_data(request)
        except (ValueError, TypeError) as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        try:
            outcome = self._manager.upsert(data)
        except InvalidCandidate as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        return talent_pool_pb2.UpsertResult(
            candidate_pk=outcome.candidate_pk,
            created=outcome.created,
            changed_fields=outcome.changed_fields,
        )

    def GetCandidate(self, request, context):
        try:
            dto = self._manager.get(request.candidate_pk)
        except CandidateNotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))
        return candidate_dto_to_proto(dto)

    def ListCandidates(self, request, context):
        # Map proto enum to internal status string
        from talent_pool.grpc_handlers.mapping import _STATUS_FROM_PROTO
        status = _STATUS_FROM_PROTO.get(request.internal_status, "")
        limit = request.limit if request.limit > 0 else 100

        dtos = self._manager.list(
            ats_source=request.ats_source,
            internal_status=status,
            limit=limit,
        )
        return talent_pool_pb2.ListCandidatesResponse(
            candidates=[candidate_dto_to_proto(d) for d in dtos],
        )
