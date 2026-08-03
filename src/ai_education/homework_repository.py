"""State, audit and answer-vault repository for homework tutoring.

The in-memory adapter is intentionally replaceable by PostgreSQL/Redis in production.
It still enforces student ownership, optimistic versions and idempotency locally.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import DataConflictError, InputValidationError
from ai_education.domain.homework import AnswerVaultRecord, HomeworkSession, HomeworkTurnRecord
from ai_education.domain.protocols import utc_now
from ai_education.mysql_persistence import MySQLPersistence


class HomeworkRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.sessions: dict[str, HomeworkSession] = {}
        self.question_sessions: dict[str, str] = {}
        self.variant_sessions: dict[str, str] = {}
        self.answer_vault: dict[str, AnswerVaultRecord] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}
        self.audit_log: list[dict[str, Any]] = []
        self.error_history: dict[tuple[str, str], list[str]] = {}

    def create_session(self, session: HomeworkSession) -> HomeworkSession:
        if session.session_id in self.sessions:
            raise DataConflictError("作业辅导会话 ID 已存在")
        self.sessions[session.session_id] = deepcopy(session)
        if self.persistence:
            self.persistence.save_homework_session(session.model_dump(mode="json"))
        return deepcopy(session)

    def get_session(self, session_id: str, *, student_id: str | None = None) -> HomeworkSession:
        session = self.sessions.get(session_id)
        if not session and self.persistence:
            payload = self.persistence.load_homework_session(session_id)
            if payload:
                session = HomeworkSession.model_validate(payload)
                self.sessions[session_id] = deepcopy(session)
        if not session:
            raise InputValidationError("未找到作业辅导会话", details={"session_id": session_id})
        if student_id and session.student_id != student_id:
            raise InputValidationError("无权访问其他学生的辅导会话")
        return deepcopy(session)

    def session_for_question(self, question_id: str) -> HomeworkSession:
        session_id = self.question_sessions.get(question_id)
        if not session_id and self.persistence:
            payload = self.persistence.load_homework_by_question(question_id)
            if payload:
                session = HomeworkSession.model_validate(payload)
                self.sessions[session.session_id] = deepcopy(session)
                self.question_sessions[question_id] = session.session_id
                return deepcopy(session)
        if not session_id:
            raise InputValidationError("未找到题目所属辅导会话")
        return self.get_session(session_id)

    def session_for_variant(self, variant_id: str) -> HomeworkSession:
        session_id = self.variant_sessions.get(variant_id)
        if not session_id and self.persistence:
            payload = self.persistence.load_homework_by_variant(variant_id)
            if payload:
                session = HomeworkSession.model_validate(payload)
                self.sessions[session.session_id] = deepcopy(session)
                self.variant_sessions[variant_id] = session.session_id
                return deepcopy(session)
        if not session_id:
            raise InputValidationError("未找到变式题所属辅导会话")
        return self.get_session(session_id)

    def register_variant(self, variant_id: str, session_id: str) -> None:
        if session_id not in self.sessions:
            raise InputValidationError("无法为不存在的会话登记变式题")
        self.variant_sessions[variant_id] = session_id
        if self.persistence:
            self.persistence.save_homework_variant(variant_id, session_id)

    def save_session(
        self,
        session: HomeworkSession,
        *,
        expected_version: int | None = None,
    ) -> HomeworkSession:
        current = self.sessions.get(session.session_id)
        if not current:
            raise InputValidationError("未找到作业辅导会话")
        if expected_version is not None and current.state_version != expected_version:
            raise DataConflictError(
                "作业辅导状态版本冲突",
                details={"expected": expected_version, "current": current.state_version},
            )
        saved = session.model_copy(
            update={"state_version": current.state_version + 1, "updated_at": utc_now()}
        )
        self.sessions[session.session_id] = deepcopy(saved)
        if saved.active_question:
            self.question_sessions[saved.active_question.question_id] = saved.session_id
        if self.persistence:
            self.persistence.save_homework_session(saved.model_dump(mode="json"))
        return deepcopy(saved)

    def append_turn(
        self,
        session: HomeworkSession,
        turn: HomeworkTurnRecord,
        *,
        expected_version: int,
    ) -> HomeworkSession:
        updated = session.model_copy(update={"turns": [*session.turns, turn]})
        return self.save_session(updated, expected_version=expected_version)

    def store_answer(self, record: AnswerVaultRecord) -> str:
        self.answer_vault[record.vault_id] = deepcopy(record)
        if self.persistence:
            self.persistence.save_answer_vault(
                record.owner_student_id, record.model_dump(mode="json")
            )
        if record.variant_id:
            self.variant_sessions[record.variant_id] = self.question_sessions.get(
                record.question_id, ""
            )
        return f"vault://answer/{record.vault_id}"

    def get_answer(self, vault_id: str, *, student_id: str) -> AnswerVaultRecord:
        normalized = vault_id.rsplit("/", 1)[-1]
        record = self.answer_vault.get(normalized)
        if not record and self.persistence:
            payload = self.persistence.load_answer_vault(normalized, student_id)
            if payload:
                record = AnswerVaultRecord.model_validate(payload)
                self.answer_vault[normalized] = deepcopy(record)
        if not record or record.owner_student_id != student_id:
            raise InputValidationError("答案保险库记录不存在或无权访问")
        return deepcopy(record)

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, result: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(result)

    def record_error(self, student_id: str, knowledge_id: str, error_type: str) -> int:
        key = (student_id, knowledge_id)
        history = self.error_history.setdefault(key, [])
        history.append(error_type)
        if len(history) > 10:
            del history[:-10]
        return sum(1 for item in history[-2:] if item == error_type)

    def audit(self, entry: dict[str, Any]) -> None:
        self.audit_log.append(deepcopy({**entry, "timestamp": utc_now().isoformat()}))
        if len(self.audit_log) > 10_000:
            self.audit_log = self.audit_log[-10_000:]
