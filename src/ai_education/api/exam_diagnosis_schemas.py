"""HTTP contracts for traceable Gaokao diagnostic papers and grading."""

from __future__ import annotations

from pydantic import Field

from ai_education.domain.enums import Grade
from ai_education.domain.protocols import StrictModel


class ExamDiagnosticSessionCreate(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    paper_id: str = Field(min_length=1, max_length=128)
    grade: Grade = Grade.GRADE_12
    province_code: str = Field(default="43", min_length=2, max_length=12)
    target_exam_year: int = Field(ge=2025, le=2040)


class ExamObjectiveAnswer(StrictModel):
    question_id: str = Field(min_length=1, max_length=160)
    selected_option: str = Field(pattern=r"^[ABCD]$")
    duration_seconds: int | None = Field(default=None, ge=1, le=14_400)


class ExamDiagnosticSubmit(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    answers: list[ExamObjectiveAnswer] = Field(default_factory=list, max_length=40)
    question_durations: dict[str, int] = Field(default_factory=dict)
