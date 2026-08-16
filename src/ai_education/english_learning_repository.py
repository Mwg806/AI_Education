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
        self.learner_profiles: dict[str, dict[str, Any]] = {}
        self.learning_events: dict[str, dict[str, Any]] = {}
        self.vocabulary_items: dict[tuple[str, str], dict[str, Any]] = {}
        self.grammar_items: dict[tuple[str, str], dict[str, Any]] = {}
        self.writing_submissions: dict[str, dict[str, Any]] = {}
        self.speaking_sessions: dict[str, dict[str, Any]] = {}
        self.reading_progress: dict[tuple[str, str], dict[str, Any]] = {}
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

    def save_reading_progress(self, payload: dict[str, Any]) -> None:
        self.reading_progress[(payload["student_id"], payload["reading_id"])] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_english_reading_progress(payload)

    def load_reading_progress(
        self, student_id: str, reading_id: str
    ) -> dict[str, Any] | None:
        if self.persistence:
            return self.persistence.load_english_reading_progress(student_id, reading_id)
        payload = self.reading_progress.get((student_id, reading_id))
        return deepcopy(payload) if payload else None

    def list_reading_progress(self, student_id: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_english_reading_progress(student_id)
        return deepcopy(
            [
                payload
                for (owner, _), payload in self.reading_progress.items()
                if owner == student_id
            ]
        )

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

    def load_learner_profile(self, student_id: str) -> dict[str, Any] | None:
        if self.persistence:
            return self.persistence.load_english_learner_profile(student_id)
        payload = self.learner_profiles.get(student_id)
        return deepcopy(payload) if payload else None

    def save_learner_profile(self, payload: dict[str, Any]) -> None:
        self.learner_profiles[payload["student_id"]] = deepcopy(payload)
        if self.persistence:
            self.persistence.save_english_learner_profile(payload)

    def save_learning_task_bundle(
        self,
        event: dict[str, Any],
        vocabulary: list[dict[str, Any]],
        grammar: list[dict[str, Any]],
        writing: dict[str, Any] | None,
        speaking: dict[str, Any] | None,
        reviews: list[dict[str, Any]],
    ) -> None:
        self.learning_events[event["event_id"]] = deepcopy(event)
        for item in vocabulary:
            self.vocabulary_items[(item["student_id"], item["word_key"])] = deepcopy(item)
        for item in grammar:
            self.grammar_items[(item["student_id"], item["grammar_key"])] = deepcopy(item)
        if writing:
            self.writing_submissions[writing["submission_id"]] = deepcopy(writing)
        if speaking:
            self.speaking_sessions[speaking["speaking_session_id"]] = deepcopy(speaking)
        for review in reviews:
            self.reviews[review["review_id"]] = deepcopy(review)
        if self.persistence:
            self.persistence.save_english_learning_task_bundle(
                event, vocabulary, grammar, writing, speaking, reviews
            )

    def save_national_exam_attempt(self, payload: dict[str, Any]) -> None:
        if self.persistence:
            self.persistence.save_english_national_exam_attempt(payload)

    def learning_records(self, student_id: str, *, limit: int = 30) -> dict[str, Any]:
        if self.persistence:
            return self.persistence.load_english_learning_records(student_id, limit=limit)
        events = [
            item for item in self.learning_events.values() if item["student_id"] == student_id
        ]
        vocabulary = [
            item for (owner, _), item in self.vocabulary_items.items() if owner == student_id
        ]
        grammar = [item for (owner, _), item in self.grammar_items.items() if owner == student_id]
        writing = [
            item
            for item in self.writing_submissions.values()
            if item["student_id"] == student_id
        ]
        return {
            "events": deepcopy(
                sorted(events, key=lambda item: item["created_at"], reverse=True)[:limit]
            ),
            "vocabulary": deepcopy(
                sorted(vocabulary, key=lambda item: item["updated_at"], reverse=True)
            ),
            "grammar": deepcopy(sorted(grammar, key=lambda item: item["updated_at"], reverse=True)),
            "writing": deepcopy(
                sorted(writing, key=lambda item: item["created_at"], reverse=True)[:limit]
            ),
        }

    def delete_learning_record(self, student_id: str, record_type: str, record_id: str) -> bool:
        if self.persistence:
            return self.persistence.delete_english_learning_record(
                student_id, record_type, record_id
            )
        if record_type == "event":
            payload = self.learning_events.get(record_id)
            if payload and payload["student_id"] == student_id:
                del self.learning_events[record_id]
                return True
        if record_type == "vocabulary":
            key = (student_id, record_id.lower())
            if key in self.vocabulary_items:
                del self.vocabulary_items[key]
                return True
        return False
