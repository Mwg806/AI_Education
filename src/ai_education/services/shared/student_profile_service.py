"""Unified structured student profile service shared by every education agent."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC
from math import exp
from typing import Any

from ai_education.core.errors import DataConflictError
from ai_education.domain.multi_agent import (
    LearningEvent,
    LearningEventType,
    MasterySnapshot,
    UnifiedStudentProfile,
)
from ai_education.domain.protocols import utc_now
from ai_education.shared_learning_repository import SharedLearningRepository

ERROR_EVENTS = {
    LearningEventType.QUESTION_WRONG,
    LearningEventType.KNOWLEDGE_WEAK,
    LearningEventType.READING_ERROR,
    LearningEventType.GRAMMAR_ERROR,
    LearningEventType.WRITING_ERROR,
    LearningEventType.SPEAKING_ERROR,
}
CORRECT_EVENTS = {
    LearningEventType.QUESTION_CORRECT,
    LearningEventType.KNOWLEDGE_MASTERED,
}
SCORE_EVENTS = {LearningEventType.PROJECT_SCORE, LearningEventType.SKILL_SCORE}


class StudentProfileService:
    def __init__(self, repository: SharedLearningRepository) -> None:
        self.repository = repository
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_profile(self, user_id: str) -> UnifiedStudentProfile:
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            return self._load_or_create(user_id)

    async def get_subject_profile(self, user_id: str, subject: str) -> dict[str, Any]:
        profile = await self.get_profile(user_id)
        return {
            "subject": subject,
            "abilities": {
                key: value.model_dump(mode="json")
                for key, value in profile.subject_abilities.get(subject, {}).items()
            },
            "weak_points": [item for item in profile.weak_points if item.startswith(f"{subject}.")],
            "strengths": [item for item in profile.strengths if item.startswith(f"{subject}.")],
        }

    async def update_profile(self, user_id: str, updates: dict[str, Any]) -> UnifiedStudentProfile:
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            profile = self._load_or_create(user_id)
            payload = profile.model_dump(mode="python")
            self._deep_merge(payload, updates)
            payload["user_id"] = user_id
            payload["profile_version"] = profile.profile_version + 1
            payload["updated_at"] = utc_now()
            saved = UnifiedStudentProfile.model_validate(payload)
            self._save_versioned(saved, expected_version=profile.profile_version)
            return saved

    async def update_mastery(
        self,
        user_id: str,
        knowledge_point: str,
        score: float,
        *,
        subject: str = "general",
        confidence: float = 1.0,
        error_type: str | None = None,
    ) -> UnifiedStudentProfile:
        event = LearningEvent(
            event_type=(
                LearningEventType.QUESTION_CORRECT
                if score >= 0.6
                else LearningEventType.QUESTION_WRONG
            ),
            user_id=user_id,
            agent="supervisor",
            subject=subject,
            knowledge_point=knowledge_point,
            score=score,
            confidence=confidence,
            metadata={"error_type": error_type} if error_type else {},
        )
        return await self.apply_event(event)

    async def get_weak_points(self, user_id: str) -> list[str]:
        return list((await self.get_profile(user_id)).weak_points)

    async def apply_event(self, event: LearningEvent) -> UnifiedStudentProfile:
        lock = self._locks.setdefault(event.user_id, asyncio.Lock())
        async with lock:
            profile = self._load_or_create(event.user_id)
            payload = profile.model_dump(mode="python")
            subject = event.subject or "general"
            knowledge_point = event.knowledge_point
            if knowledge_point:
                full_key = (
                    knowledge_point
                    if knowledge_point.startswith(f"{subject}.")
                    else f"{subject}.{knowledge_point}"
                )
                current_raw = payload["knowledge_mastery"].get(full_key)
                current = (
                    MasterySnapshot.model_validate(current_raw)
                    if current_raw
                    else MasterySnapshot(knowledge_point=full_key, subject=subject)
                )
                independence_key = self._independence_key(event)
                if independence_key in current.evidence_keys:
                    return profile
                old = current.mastery
                target = self._target_score(event)
                reliability = self._reliability(event)
                difficulty = event.difficulty if event.difficulty is not None else 0.5
                elapsed_factor = self._elapsed_factor(current, event)
                difficulty_factor = 0.75 + 0.5 * difficulty
                rate = min(
                    0.24,
                    max(
                        0.025,
                        0.18 * event.confidence * reliability * difficulty_factor * elapsed_factor,
                    ),
                )
                mastery = round(max(0.02, min(0.98, old + rate * (target - old))), 4)
                is_error = event.event_type in ERROR_EVENTS or target < 0.5
                is_correct = event.event_type in CORRECT_EVENTS or (
                    event.event_type in SCORE_EVENTS and target >= 0.6
                )
                error_types = list(current.error_types)
                error_type = str(event.metadata.get("error_type") or event.event_type.value)
                if is_error and error_type not in error_types:
                    error_types.append(error_type)
                next_count = current.evidence_count + 1
                independent_count = current.independent_assessment_count + 1
                updated = current.model_copy(
                    update={
                        "mastery": mastery,
                        "evidence_count": next_count,
                        "independent_assessment_count": independent_count,
                        "evidence_keys": [*current.evidence_keys, independence_key][-40:],
                        "reliability_mean": round(
                            (current.reliability_mean * current.evidence_count + reliability)
                            / next_count,
                            4,
                        ),
                        "difficulty_mean": round(
                            (current.difficulty_mean * current.evidence_count + difficulty)
                            / next_count,
                            4,
                        ),
                        "correct_count": current.correct_count + int(is_correct and not is_error),
                        "error_count": current.error_count + int(is_error),
                        "confidence": round(
                            min(0.98, current.confidence + 0.08 * event.confidence * reliability),
                            4,
                        ),
                        "last_event_at": event.occurred_at,
                        "trend": (
                            "improving"
                            if mastery > old
                            else "declining"
                            if mastery < old
                            else "stable"
                        ),
                        "error_types": error_types[-8:],
                    }
                )
                payload["knowledge_mastery"][full_key] = updated.model_dump(mode="python")
                payload["subject_abilities"].setdefault(subject, {})[full_key] = updated.model_dump(
                    mode="python"
                )
                if is_error:
                    payload["recent_errors"] = [
                        {
                            "event_id": event.event_id,
                            "knowledge_point": full_key,
                            "event_type": event.event_type.value,
                            "score": event.score,
                            "source_reliability": reliability,
                            "independence_key": independence_key,
                            "occurred_at": event.occurred_at,
                        },
                        *payload["recent_errors"],
                    ][:20]
            snapshots = {
                key: MasterySnapshot.model_validate(value)
                for key, value in payload["knowledge_mastery"].items()
            }
            payload["weak_points"] = sorted(
                key
                for key, item in snapshots.items()
                if item.independent_assessment_count >= 3
                and item.error_count >= 3
                or (
                    item.independent_assessment_count >= 2
                    and item.mastery < 0.55
                    and item.confidence >= 0.3
                )
            )
            payload["strengths"] = sorted(
                key
                for key, item in snapshots.items()
                if item.independent_assessment_count >= 3
                and item.mastery >= 0.8
                and item.confidence >= 0.45
            )
            payload["profile_version"] = profile.profile_version + 1
            payload["updated_at"] = utc_now()
            saved = UnifiedStudentProfile.model_validate(payload)
            self._save_versioned(saved, expected_version=profile.profile_version)
            return saved

    def _load_or_create(self, user_id: str) -> UnifiedStudentProfile:
        payload = self.repository.load_profile(user_id)
        if payload:
            return UnifiedStudentProfile.model_validate(payload)
        basic: dict[str, Any] = {}
        persistence = self.repository.persistence
        if persistence:
            row = persistence.student_by_account(user_id)
            if row:
                basic = {
                    "student_id": row["student_id"],
                    "student_name": row["student_name"],
                    "grade": row["grade"],
                    "province_code": row["province_code"],
                    "target_exam_year": row["target_exam_year"],
                }
        profile = UnifiedStudentProfile(user_id=user_id, basic_profile=basic)
        self.repository.save_profile(profile.model_dump(mode="json"), expected_version=0)
        return profile

    def _save_versioned(self, profile: UnifiedStudentProfile, *, expected_version: int) -> None:
        if not self.repository.save_profile(
            profile.model_dump(mode="json"), expected_version=expected_version
        ):
            self.repository.invalidate_profile(profile.user_id)
            current = self._load_or_create(profile.user_id)
            raise DataConflictError(
                "统一学生画像已被其他请求更新，请重试",
                details={
                    "expected_version": expected_version,
                    "current_version": current.profile_version,
                },
            )

    @staticmethod
    def _independence_key(event: LearningEvent) -> str:
        metadata = event.metadata
        return str(
            metadata.get("assessment_independence_key")
            or event.session_id
            or metadata.get("source_item_id")
            or event.event_id
        )[:160]

    @staticmethod
    def _reliability(event: LearningEvent) -> float:
        raw = event.metadata.get("source_reliability", event.confidence)
        try:
            return max(0.2, min(1.0, float(raw)))
        except (TypeError, ValueError):
            return max(0.2, event.confidence)

    @staticmethod
    def _elapsed_factor(current: MasterySnapshot, event: LearningEvent) -> float:
        if current.last_event_at is None:
            return 1.0
        current_time = current.last_event_at
        event_time = event.occurred_at
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        days = max(0.0, (event_time - current_time).total_seconds() / 86_400)
        return 0.65 + 0.35 * (1 - exp(-days / 7.0))

    @staticmethod
    def _target_score(event: LearningEvent) -> float:
        if event.score is not None:
            return event.score
        if event.event_type in CORRECT_EVENTS:
            return 1.0
        if event.event_type in ERROR_EVENTS:
            return 0.0
        return 0.5

    @classmethod
    def _deep_merge(cls, target: dict[str, Any], updates: dict[str, Any]) -> None:
        for key, value in deepcopy(updates).items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                cls._deep_merge(target[key], value)
            elif key not in {"user_id", "profile_version", "updated_at"}:
                target[key] = value
