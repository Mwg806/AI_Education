"""Durable private-state repository for English reading and language learning."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import MySQLPersistence


class EnglishLearningRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.analyses: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.mastery: dict[tuple[str, str], dict[str, Any]] = {}
        self.reviews: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, dict[str, Any]] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, payload: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(payload)

    def save_analysis(self, payload: dict[str, Any]) -> None:
        self.analyses[payload["analysis_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_english_analysis(payload)

    def list_analyses(self, student_id: str, *, limit: int = 6) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_english_analyses(student_id, limit=limit)
        rows = [item for item in self.analyses.values() if item["student_id"] == student_id]
        return deepcopy(sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit])

    def save_session(self, payload: dict[str, Any]) -> None:
        self.sessions[payload["session_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_english_session(payload)

    def get_session(self, session_id: str, *, student_id: str) -> dict[str, Any]:
        payload = self.sessions.get(session_id)
        if payload is None and self.persistence:
            payload = self.persistence.load_english_session(session_id, student_id)
            if payload:
                self.sessions[session_id] = deepcopy(payload)
        if not payload or payload["student_id"] != student_id:
            raise InputValidationError("英语训练不存在或无权访问")
        return deepcopy(payload)

    def list_sessions(self, student_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_english_sessions(student_id, limit=limit)
        rows = [item for item in self.sessions.values() if item["student_id"] == student_id]
        return deepcopy(sorted(rows, key=lambda item: item["updated_at"], reverse=True)[:limit])

    def list_mastery_states(self, student_id: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_english_mastery_states(student_id)
        return deepcopy(
            [payload for (owner, _), payload in self.mastery.items() if owner == student_id]
        )

    def list_reviews(self, student_id: str, *, status: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_english_reviews(student_id, status=status)
        rows = [
            item
            for item in self.reviews.values()
            if item["student_id"] == student_id and item["status"] == status
        ]
        return deepcopy(sorted(rows, key=lambda item: item["due_at"]))

    def save_attempt_bundle(
        self,
        session: dict[str, Any],
        attempt: dict[str, Any],
        states: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> None:
        self.sessions[session["session_id"]] = deepcopy(session)
        self.attempts[attempt["attempt_id"]] = deepcopy(attempt)
        for state in states:
            self.mastery[(state["student_id"], state["skill_id"])] = deepcopy(state)
        for review in reviews:
            self.reviews[review["review_id"]] = deepcopy(review)
        if self.persistence:
            self.persistence.save_english_attempt_bundle(session, attempt, states, reviews)

    def complete_review(
        self, student_id: str, review_id: str, result: str
    ) -> dict[str, Any] | None:
        if self.persistence:
            return self.persistence.complete_english_review(student_id, review_id, result)
        review = self.reviews.get(review_id)
        if not review or review["student_id"] != student_id or review["status"] != "pending":
            return None
        review = {**review, "status": "completed", "result": result}
        self.reviews[review_id] = review
        return deepcopy(review)
