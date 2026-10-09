"""Candidate manager: upsert logic with outbox event emission."""
from __future__ import annotations

from datetime import datetime, timezone

from django.db import transaction

from klaaryo_contracts.events import (
    CANDIDATE_CREATED,
    CANDIDATE_UPDATED,
    CandidateEvent,
)
from talent_pool.db_models.models import Candidate, OutboxEvent
from talent_pool.managers.dto import CandidateData, CandidateDTO, UpsertOutcome
from talent_pool.managers.exceptions import CandidateNotFound, InvalidCandidate

TRACKED_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "age",
    "job_external_id",
    "internal_status",
    "applied_at",
)


class CandidateManager:
    @transaction.atomic
    def upsert(self, data: CandidateData) -> UpsertOutcome:
        if not data.external_id or not data.ats_source:
            raise InvalidCandidate("external_id and ats_source are required")
        if not data.internal_status:
            raise InvalidCandidate("internal_status is required")

        obj = Candidate.objects.filter(
            ats_source=data.ats_source,
            external_id=data.external_id,
        ).first()

        if obj is None:
            obj = Candidate.objects.create(
                ats_source=data.ats_source,
                external_id=data.external_id,
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
                phone=data.phone,
                age=data.age,
                job_external_id=data.job_external_id,
                internal_status=data.internal_status,
                applied_at=data.applied_at,
            )
            self._enqueue(
                CANDIDATE_CREATED,
                obj.pk,
                data.ats_source,
                data.external_id,
                [],
            )
            return UpsertOutcome(candidate_pk=obj.pk, created=True, changed_fields=[])

        # Existing candidate: detect changes
        changed = sorted(
            f
            for f in TRACKED_FIELDS
            if getattr(obj, f) != getattr(data, f)
        )

        if changed:
            for f in changed:
                setattr(obj, f, getattr(data, f))
            obj.save(update_fields=list(changed) + ["updated_at"])
            self._enqueue(
                CANDIDATE_UPDATED,
                obj.pk,
                data.ats_source,
                data.external_id,
                changed,
            )

        return UpsertOutcome(
            candidate_pk=obj.pk,
            created=False,
            changed_fields=changed,
        )

    def get(self, pk: int) -> CandidateDTO:
        try:
            obj = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            raise CandidateNotFound(f"Candidate with pk={pk} not found")
        return self._to_dto(obj)

    def list(
        self,
        ats_source: str = "",
        internal_status: str = "",
        limit: int = 100,
    ) -> list[CandidateDTO]:
        qs = Candidate.objects.all()
        if ats_source:
            qs = qs.filter(ats_source=ats_source)
        if internal_status:
            qs = qs.filter(internal_status=internal_status)
        return [self._to_dto(obj) for obj in qs[:limit]]

    def _enqueue(
        self,
        event_type: str,
        candidate_pk: int,
        ats_source: str,
        external_id: str,
        changed_fields: list[str],
    ) -> None:
        event = CandidateEvent.new(
            event_type=event_type,
            candidate_pk=candidate_pk,
            ats_source=ats_source,
            external_id=external_id,
            changed_fields=changed_fields,
        )
        OutboxEvent.objects.create(
            event_id=event.event_id,
            topic=event.event_type,
            payload=event.to_dict(),
        )

    @staticmethod
    def _to_dto(obj: Candidate) -> CandidateDTO:
        return CandidateDTO(
            candidate_pk=obj.pk,
            external_id=obj.external_id,
            ats_source=obj.ats_source,
            first_name=obj.first_name,
            last_name=obj.last_name,
            email=obj.email,
            phone=obj.phone,
            age=obj.age,
            job_external_id=obj.job_external_id,
            internal_status=obj.internal_status,
            applied_at=obj.applied_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
