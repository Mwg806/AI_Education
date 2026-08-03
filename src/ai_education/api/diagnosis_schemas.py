"""HTTP boundary schemas for the learning-state diagnosis agent."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ai_education.domain.diagnosis import AssessmentType
from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel


class LearningEvidenceInput(StrictModel):
    assessment_id: str = Field(min_length=1, max_length=128)
    assessment_type: AssessmentType
    question_id: str = Field(min_length=1, max_length=128)
    knowledge_tags: list[str] = Field(min_length=1, max_length=8)
    question_type: str = Field(min_length=1, max_length=80)
    ability_tags: list[str] = Field(default_factory=list, max_length=8)
    difficulty: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0)
    max_score: float = Field(gt=0.0)
    duration_seconds: int | None = Field(default=None, ge=1, le=14_400)
    hint_count: int = Field(default=0, ge=0, le=50)
    attempt_count: int = Field(default=1, ge=1, le=50)
    error_tags: list[str] = Field(default_factory=list, max_length=10)
    step_trace: str | None = Field(default=None, max_length=2_000)
    source_id: str | None = Field(default=None, max_length=256)
    occurred_at: datetime | None = None


class LearningDiagnosisRunInput(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    grade: Grade
    province_code: str = Field(default="43", min_length=2, max_length=12)
    subject: Subject = Subject.MATHEMATICS
    target_exam_year: int = Field(ge=2025, le=2040)
    curriculum_version: str | None = Field(default=None, max_length=128)
    diagnosis_request: str = Field(default="识别当前稳定薄弱点与下一步需要补充的证据", min_length=1, max_length=1_000)
    diagnosis_window: str = Field(default="recent_30_days", max_length=80)
    records: list[LearningEvidenceInput] = Field(min_length=1, max_length=200)
    idempotency_key: str | None = Field(default=None, max_length=256)


class TeacherReviewInput(StrictModel):
    diagnosis_id: str = Field(min_length=1, max_length=128)
    student_id: str = Field(min_length=1, max_length=128)
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: Literal["confirm", "correct", "request_more_evidence"]
    comment: str = Field(min_length=1, max_length=2_000)
    corrections: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=256)
