"""Versioned in-memory repository for learning-state diagnosis."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.domain.diagnosis import (
    LearningEvidenceRecord,
    LearningStateDiagnosis,
    TeacherReview,
)
from ai_education.mysql_persistence import MySQLPersistence


class DiagnosisRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.evidence: dict[tuple[str, str], dict[str, LearningEvidenceRecord]] = {}
        self.states: dict[tuple[str, str], list[LearningStateDiagnosis]] = {}
        self.by_id: dict[str, LearningStateDiagnosis] = {}
        self.reviews: dict[str, list[TeacherReview]] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}
        self.audit_log: list[dict[str, Any]] = []

    def upsert_evidence(
        self, student_id: str, subject: str, records: list[LearningEvidenceRecord]
    ) -> tuple[list[LearningEvidenceRecord], int]:
        bucket = self.evidence.setdefault((student_id, subject), {})
        inserted: list[LearningEvidenceRecord] = []
        duplicate_count = 0
        for record in records:
            natural_key = (
                record.source_id
                or f"{record.assessment_id}:{record.question_id}:{record.occurred_at.isoformat()}"
            )
            if natural_key in bucket:
                duplicate_count += 1
                continue
            bucket[natural_key] = deepcopy(record)
            inserted.append(deepcopy(record))
        if self.persistence:
            self.persistence.save_learning_evidence(
                student_id, [record.model_dump(mode="json") for record in inserted]
            )
        return inserted, duplicate_count

    def list_evidence(self, student_id: str, subject: str) -> list[LearningEvidenceRecord]:
        bucket = self.evidence.get((student_id, subject))
        if bucket is None and self.persistence:
            records = [
                LearningEvidenceRecord.model_validate(item)
                for item in self.persistence.load_learning_evidence(student_id, subject)
            ]
            bucket = {
                item.source_id
                or f"{item.assessment_id}:{item.question_id}:{item.occurred_at.isoformat()}": item
                for item in records
            }
            self.evidence[(student_id, subject)] = bucket
        return [deepcopy(item) for item in (bucket or {}).values()]

    def latest_state(self, student_id: str, subject: str) -> LearningStateDiagnosis | None:
        versions = self.states.get((student_id, subject), [])
        if versions:
            return deepcopy(versions[-1])
        if self.persistence:
            payload = self.persistence.load_latest_diagnosis(student_id, subject)
            if payload:
                state = LearningStateDiagnosis.model_validate(payload)
                self.states.setdefault((student_id, subject), []).append(deepcopy(state))
                self.by_id[state.diagnosis_id] = deepcopy(state)
                return deepcopy(state)
        return None

    def save_state(self, state: LearningStateDiagnosis) -> LearningStateDiagnosis:
        key = (state.student_id, state.subject.value)
        versions = self.states.setdefault(key, [])
        saved = state.model_copy(
            update={
                "state_version": len(versions) + 1,
                "previous_version": versions[-1].state_version if versions else None,
            }
        )
        versions.append(deepcopy(saved))
        self.by_id[saved.diagnosis_id] = deepcopy(saved)
        if self.persistence:
            self.persistence.save_diagnosis(saved.model_dump(mode="json"))
        self.audit_log.append(
            {
                "event": "diagnosis_saved",
                "diagnosis_id": saved.diagnosis_id,
                "student_id": saved.student_id,
                "state_version": saved.state_version,
                "evidence_count": saved.evidence_gate.valid_evidence_count,
            }
        )
        return deepcopy(saved)

    def get_diagnosis(
        self, diagnosis_id: str, *, student_id: str | None = None
    ) -> LearningStateDiagnosis:
        state = self.by_id.get(diagnosis_id)
        if not state and self.persistence:
            payload = self.persistence.load_diagnosis(diagnosis_id)
            if payload:
                state = LearningStateDiagnosis.model_validate(payload)
                self.by_id[diagnosis_id] = deepcopy(state)
        if not state or (student_id and state.student_id != student_id):
            raise InputValidationError("未找到学情诊断，或无权访问该诊断")
        return deepcopy(state)

    def save_review(self, review: TeacherReview) -> TeacherReview:
        state = self.get_diagnosis(review.diagnosis_id, student_id=review.student_id)
        status = {
            "confirm": "confirmed",
            "correct": "corrected",
            "request_more_evidence": "pending",
        }[review.decision]
        updated = state.model_copy(update={"review_status": status})
        self.by_id[state.diagnosis_id] = deepcopy(updated)
        key = (state.student_id, state.subject.value)
        versions = self.states.get(key, [])
        if versions and versions[-1].diagnosis_id == state.diagnosis_id:
            versions[-1] = deepcopy(updated)
        self.reviews.setdefault(review.diagnosis_id, []).append(deepcopy(review))
        if self.persistence:
            self.persistence.save_diagnosis(updated.model_dump(mode="json"))
            self.persistence.save_teacher_review(review.model_dump(mode="json"))
        self.audit_log.append(
            {
                "event": "teacher_review",
                "diagnosis_id": review.diagnosis_id,
                "review_id": review.review_id,
                "decision": review.decision,
                "reviewer_id": review.reviewer_id,
            }
        )
        return deepcopy(review)

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, result: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(result)
