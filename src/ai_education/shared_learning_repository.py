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
        self.collaboration_memories: dict[str, dict[str, Any]] = {}
        self.collaboration_sessions: set[str] = set()
        self.collaboration_messages: dict[str, dict[str, Any]] = {}

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
            if payload.get("actor_type", "student") == "student":
                self.persistence.save_agent_orchestration_run(payload)
            else:
                self.persistence.save_actor_orchestration_run(payload)

    def load_run(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        payload = self.runs.get(run_id)
        if payload is None and self.persistence:
            if user_id.startswith("teacher:"):
                payload = self.persistence.load_actor_orchestration_run(
                    run_id, "teacher", user_id.split(":", 1)[1]
                )
            else:
                payload = self.persistence.load_agent_orchestration_run(run_id, user_id)
            if payload:
                self.runs[run_id] = deepcopy(payload)
        if not payload or payload["user_id"] != user_id:
            return None
        return deepcopy(payload)

    def save_trace(self, payload: dict[str, Any]) -> None:
        self.traces[payload["trace_record_id"]] = deepcopy(payload)
        if self.persistence:
            if payload.get("actor_type", "student") == "student":
                self.persistence.save_agent_execution_trace(payload)
            else:
                self.persistence.save_actor_execution_trace(payload)

    def list_pending_event_outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.persistence:
            return []
        return self.persistence.list_pending_learning_event_outbox(limit)

    def mark_event_processed(self, event_id: str) -> None:
        if self.persistence:
            self.persistence.mark_learning_event_outbox_processed(event_id)

    def mark_event_failed(self, event_id: str, error: str) -> None:
        if self.persistence:
            self.persistence.mark_learning_event_outbox_failed(event_id, error)

    def load_collaboration_memory(self, user_id: str) -> dict[str, Any] | None:
        payload = self.collaboration_memories.get(user_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_collaboration_memory(user_id)
            if payload:
                self.collaboration_memories[user_id] = deepcopy(payload)
        return deepcopy(payload) if payload else None

    def save_collaboration_memory(self, payload: dict[str, Any]) -> bool:
        saved = self.persistence.save_collaboration_memory(payload) if self.persistence else True
        if saved:
            self.collaboration_memories[payload["user_id"]] = deepcopy(payload)
        return saved

    def ensure_collaboration_session(self, payload: dict[str, Any]) -> bool:
        session_id = payload["session_id"]
        if self.persistence:
            inserted = self.persistence.ensure_collaboration_session(payload)
        else:
            inserted = session_id not in self.collaboration_sessions
        self.collaboration_sessions.add(session_id)
        return inserted

    def save_collaboration_message(self, payload: dict[str, Any]) -> bool:
        message_id = payload["message_id"]
        if message_id in self.collaboration_messages:
            return False
        inserted = (
            self.persistence.save_collaboration_message(payload) if self.persistence else True
        )
        if inserted:
            self.collaboration_messages[message_id] = deepcopy(payload)
        return inserted

    def list_collaboration_messages(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_collaboration_messages(user_id, limit=limit)
        rows = [item for item in self.collaboration_messages.values() if item["user_id"] == user_id]
        return deepcopy(sorted(rows, key=lambda item: item["created_at"])[-limit:])
