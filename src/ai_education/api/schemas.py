"""API-specific request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ai_education.domain.enums import ActorType
from ai_education.domain.protocols import StrictModel


class OnboardingCreate(StrictModel):
    student_id: str


class OnboardingAnswers(StrictModel):
    answers: dict[str, Any]


class ExamProfileConfirmation(StrictModel):
    exam_profile_id: str


class PlannerInvocation(StrictModel):
    student_id: str
    payload: dict[str, Any]
    actor_type: ActorType = ActorType.STUDENT
    actor_id: str | None = None
    idempotency_key: str | None = None
    data_version: str = "v0"


class LearningEventInput(StrictModel):
    student_id: str
    event: dict[str, Any]
    idempotency_key: str | None = None


class ExamResultInput(StrictModel):
    student_id: str
    exam_result: dict[str, Any]
    idempotency_key: str | None = None


class DailyUpdateInput(StrictModel):
    student_id: str
    metrics: dict[str, float | int | bool] = Field(default_factory=dict)
    plan_id: str | None = None
    idempotency_key: str | None = None


class ReplanInput(StrictModel):
    student_id: str
    level: str | None = None
    reason: str
    metrics: dict[str, float | int | bool] = Field(default_factory=dict)
    idempotency_key: str | None = None


class PlanConfirmation(StrictModel):
    student_id: str
    expected_version: int = Field(ge=1)
    idempotency_key: str | None = None
