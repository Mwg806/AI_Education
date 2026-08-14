"""Teacher-only request schemas for the lesson-preparation Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ai_education.domain.enums import Subject
from ai_education.domain.protocols import StrictModel
from ai_education.domain.teacher_preparation import LessonType


class LessonPlanCreateInput(StrictModel):
    classroom_id: int = Field(gt=0)
    subject: Subject
    lesson_type: LessonType = LessonType.NEW_LESSON
    topic: str = Field(min_length=2, max_length=200)
    lesson_request: str = Field(min_length=5, max_length=4_000)
    lesson_count: int = Field(default=1, ge=1, le=6)
    duration_minutes: int = Field(default=45, ge=20, le=240)
    teaching_stage: str = Field(default="日常教学", min_length=2, max_length=80)
    textbook_version: str = Field(default="教师指定教材", min_length=1, max_length=120)
    exam_year: int = Field(default=2027, ge=2025, le=2100)
    available_equipment: list[str] = Field(default_factory=list, max_length=20)
    homework_time_limit_minutes: int = Field(default=25, ge=5, le=180)
    idempotency_key: str | None = Field(default=None, max_length=160)

    @field_validator("topic", "lesson_request", "teaching_stage", "textbook_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("available_equipment")
    @classmethod
    def normalize_equipment(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


class LessonPlanRevisionInput(StrictModel):
    expected_version: int = Field(ge=1)
    component: Literal[
        "full", "objectives", "activities", "board", "assessments", "differentiation"
    ] = "full"
    revision_request: str = Field(min_length=3, max_length=4_000)
    locked_component_ids: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=160)

    @field_validator("revision_request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        return value.strip()


class LessonPlanRollbackInput(StrictModel):
    expected_version: int = Field(ge=1)
    target_version: int = Field(ge=1)
    idempotency_key: str | None = Field(default=None, max_length=160)


class LessonPlanTransitionInput(StrictModel):
    expected_version: int = Field(ge=1)
    note: str = Field(default="", max_length=1_000)
    idempotency_key: str | None = Field(default=None, max_length=160)


class PostLessonFeedbackInput(StrictModel):
    lesson_version: int = Field(ge=1)
    actual_duration_minutes: int = Field(ge=1, le=360)
    completed_activity_ids: list[str] = Field(default_factory=list, max_length=30)
    skipped_activity_ids: list[str] = Field(default_factory=list, max_length=30)
    class_check_accuracy: float | None = Field(default=None, ge=0, le=1)
    teacher_rating: int = Field(ge=1, le=5)
    effective_components: list[str] = Field(default_factory=list, max_length=30)
    issues: list[str] = Field(default_factory=list, max_length=30)
    teacher_notes: str = Field(default="", max_length=4_000)
    idempotency_key: str | None = Field(default=None, max_length=160)
