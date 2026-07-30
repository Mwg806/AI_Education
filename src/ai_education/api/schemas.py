"""API-specific request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ai_education.domain.enums import ActorType, Subject
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


class OCRConfirmationInput(StrictModel):
    student_id: str
    confirmed_text: str = Field(min_length=1, max_length=20_000)
    student_work: str = Field(default="", max_length=20_000)
    subject: Subject | None = None
    idempotency_key: str | None = None


class HomeworkSubmissionInput(StrictModel):
    student_id: str
    answer: str = Field(min_length=1, max_length=20_000)
    idempotency_key: str | None = None


class HomeworkVariantRequest(StrictModel):
    student_id: str
    target_difficulty: float | None = Field(default=None, ge=0, le=1)
    idempotency_key: str | None = None


class QuestionBankSearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=2_000)
    subject: Subject | None = None
    province: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
