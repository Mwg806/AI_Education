"""Private persistence boundary for the student programming growth Agent."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import MySQLPersistence


class ProgrammingLearningRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.profiles: dict[str, dict[str, Any]] = {}
        self.records: dict[str, dict[str, Any]] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.skill_states: dict[tuple[str, str], dict[str, Any]] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, payload: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(payload)

    def save_profile(self, payload: dict[str, Any]) -> None:
        self.profiles[payload["student_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_programming_profile(payload)

    def load_profile(self, student_id: str) -> dict[str, Any] | None:
        payload = self.profiles.get(student_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_programming_profile(student_id)
            if payload:
                self.profiles[student_id] = deepcopy(payload)
        return deepcopy(payload) if payload else None

    def save_record(self, payload: dict[str, Any]) -> None:
        self.records[payload["record_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_programming_record(payload)

    def load_record(
        self, record_id: str, *, student_id: str, record_type: str | None = None
    ) -> dict[str, Any]:
        payload = self.records.get(record_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_programming_record(record_id, student_id)
            if payload:
                self.records[record_id] = deepcopy(payload)
        if (
            not payload
            or payload["student_id"] != student_id
            or (record_type and payload["record_type"] != record_type)
        ):
            raise InputValidationError("编程学习记录不存在或无权访问")
        return deepcopy(payload)

    def list_records(
        self, student_id: str, *, record_type: str | None = None, limit: int = 12
    ) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_programming_records(
                student_id, record_type=record_type, limit=limit
            )
        rows = [
            item
            for item in self.records.values()
            if item["student_id"] == student_id
            and (record_type is None or item["record_type"] == record_type)
        ]
        return deepcopy(sorted(rows, key=lambda item: item["updated_at"], reverse=True)[:limit])

    def save_evidence_bundle(self, event: dict[str, Any], skill_state: dict[str, Any]) -> None:
        self.events[event["event_id"]] = deepcopy(event)
        key = (skill_state["student_id"], skill_state["skill_id"])
        self.skill_states[key] = deepcopy(skill_state)
        if self.persistence:
            self.persistence.save_programming_evidence_bundle(event, skill_state)

    def list_events(self, student_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_programming_events(student_id, limit=limit)
        rows = [item for item in self.events.values() if item["student_id"] == student_id]
        return deepcopy(sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit])

    def list_skill_states(self, student_id: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_programming_skill_states(student_id)
        rows = [payload for (owner, _), payload in self.skill_states.items() if owner == student_id]
        return deepcopy(sorted(rows, key=lambda item: item["skill_id"]))

    def get_skill_state(self, student_id: str, skill_id: str) -> dict[str, Any] | None:
        states = self.list_skill_states(student_id)
        return next((item for item in states if item["skill_id"] == skill_id), None)
