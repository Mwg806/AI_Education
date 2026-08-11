"""Repository adapter for unified profiles, events and orchestration audit records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.mysql_persistence import MySQLPersistence


class SharedLearningRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.profiles: dict[str, dict[str, Any]] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}
        self.traces: dict[str, dict[str, Any]] = {}

    def load_profile(self, user_id: str) -> dict[str, Any] | None:
        payload = self.profiles.get(user_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_unified_student_profile(user_id)
            if payload:
                self.profiles[user_id] = deepcopy(payload)
        return deepcopy(payload) if payload else None

    def invalidate_profile(self, user_id: str) -> None:
        self.profiles.pop(user_id, None)

    def save_profile(
        self,
        payload: dict[str, Any],
        *,
        expected_version: int | None = None,
    ) -> bool:
        user_id = payload["user_id"]
        current = self.profiles.get(user_id)
        if current is not None and expected_version is not None:
            current_version = int(current.get("profile_version", 0))
            if expected_version == 0 or current_version != expected_version:
                return False
        if self.persistence and not self.persistence.save_unified_student_profile(
            payload, expected_version=expected_version
        ):
            return False
        self.profiles[user_id] = deepcopy(payload)
        return True

    def save_event(self, payload: dict[str, Any]) -> bool:
        event_id = payload["event_id"]
        if event_id in self.events:
            return False
        inserted = (
            self.persistence.save_unified_learning_event(payload) if self.persistence else True
        )
        if inserted:
            self.events[event_id] = deepcopy(payload)
        return inserted

    def list_events(
        self,
        user_id: str,
        *,
        limit: int = 100,
        knowledge_point: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_unified_learning_events(
                user_id, limit=limit, knowledge_point=knowledge_point
            )
        rows = [item for item in self.events.values() if item["user_id"] == user_id]
        if knowledge_point:
            rows = [item for item in rows if item.get("knowledge_point") == knowledge_point]
        return deepcopy(sorted(rows, key=lambda item: item["occurred_at"], reverse=True)[:limit])

    def save_run(self, payload: dict[str, Any]) -> None:
        self.runs[payload["run_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_agent_orchestration_run(payload)

    def load_run(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        payload = self.runs.get(run_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_agent_orchestration_run(run_id, user_id)
            if payload:
                self.runs[run_id] = deepcopy(payload)
        if not payload or payload["user_id"] != user_id:
            return None
        return deepcopy(payload)

    def save_trace(self, payload: dict[str, Any]) -> None:
        self.traces[payload["trace_record_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_agent_execution_trace(payload)
