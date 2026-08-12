"""Versioned repository for teacher-owned lesson plans and post-lesson feedback."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import DataConflictError, InputValidationError
from ai_education.domain.teacher_preparation import LessonPlanVersion, PostLessonFeedback
from ai_education.mysql_persistence import MySQLPersistence


class TeacherPreparationRepository:
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        self.persistence = persistence
        self.plans: dict[str, list[LessonPlanVersion]] = {}
        self.feedback: dict[str, list[PostLessonFeedback]] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}
        self.audit_log: list[dict[str, Any]] = []

    def save_version(self, plan: LessonPlanVersion) -> LessonPlanVersion:
        versions = self.plans.setdefault(plan.lesson_plan_id, [])
        if versions:
            latest = versions[-1]
            if latest.context.teacher_id != plan.context.teacher_id:
                raise InputValidationError("无权修改其他教师的备课方案")
            if plan.version != latest.version + 1 or plan.parent_version != latest.version:
                raise DataConflictError(
                    "备课方案版本冲突",
                    details={
                        "current_version": latest.version,
                        "incoming_version": plan.version,
                    },
                )
        elif plan.version != 1 or plan.parent_version is not None:
            raise DataConflictError("新备课方案必须从版本 1 开始")
        versions.append(deepcopy(plan))
        if self.persistence:
            self.persistence.save_teacher_lesson_version(plan.model_dump(mode="json"))
        self.audit_log.append(
            {
                "event": "lesson_plan_version_saved",
                "lesson_plan_id": plan.lesson_plan_id,
                "version": plan.version,
                "teacher_id": plan.context.teacher_id,
                "status": plan.status.value,
                "change_summary": list(plan.change_summary),
            }
        )
        return deepcopy(plan)

    def get(
        self,
        lesson_plan_id: str,
        teacher_id: str,
        version: int | None = None,
    ) -> LessonPlanVersion:
        versions = self.plans.get(lesson_plan_id, [])
        if not versions and self.persistence:
            payloads = self.persistence.load_teacher_lesson_versions(lesson_plan_id, teacher_id)
            versions = [LessonPlanVersion.model_validate(item) for item in payloads]
            if versions:
                self.plans[lesson_plan_id] = [deepcopy(item) for item in versions]
        if not versions or versions[-1].context.teacher_id.lower() != teacher_id.lower():
            raise InputValidationError("备课方案不存在或不属于当前教师")
        if version is None:
            return deepcopy(versions[-1])
        match = next((item for item in versions if item.version == version), None)
        if match is None:
            raise InputValidationError("指定的备课方案版本不存在")
        return deepcopy(match)

    def list_teacher(
        self,
        teacher_id: str,
        *,
        classroom_id: int | None = None,
    ) -> list[LessonPlanVersion]:
        if self.persistence:
            payloads = self.persistence.list_teacher_lesson_plans(
                teacher_id, classroom_id=classroom_id
            )
            for payload in payloads:
                loaded = LessonPlanVersion.model_validate(payload)
                existing = self.plans.setdefault(loaded.lesson_plan_id, [])
                if not any(item.version == loaded.version for item in existing):
                    existing.append(deepcopy(loaded))
                    existing.sort(key=lambda item: item.version)
        latest = [
            versions[-1]
            for versions in self.plans.values()
            if versions
            and versions[-1].context.teacher_id.lower() == teacher_id.lower()
            and (classroom_id is None or versions[-1].context.classroom_id == classroom_id)
        ]
        return [
            deepcopy(item)
            for item in sorted(latest, key=lambda item: item.created_at, reverse=True)
        ]

    def save_feedback(self, feedback: PostLessonFeedback) -> PostLessonFeedback:
        plan = self.get(
            feedback.lesson_plan_id,
            feedback.teacher_id,
            feedback.lesson_version,
        )
        if plan.status not in {
            "published",
            "executed",
            "feedback_recorded",
        }:
            raise InputValidationError("只有已发布教案可以提交授课反馈")
        self.feedback.setdefault(feedback.lesson_plan_id, []).append(deepcopy(feedback))
        if self.persistence:
            self.persistence.save_teacher_lesson_feedback(feedback.model_dump(mode="json"))
        self.audit_log.append(
            {
                "event": "lesson_feedback_recorded",
                "feedback_id": feedback.feedback_id,
                "lesson_plan_id": feedback.lesson_plan_id,
                "version": feedback.lesson_version,
                "teacher_id": feedback.teacher_id,
            }
        )
        return deepcopy(feedback)

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, result: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(result)
