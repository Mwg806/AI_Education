"""Strict API schemas for quick diagnostic sessions."""

from pydantic import Field

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel


class DiagnosticCreateInput(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    grade: Grade
    subject: Subject
    curriculum_version: str = Field(min_length=1, max_length=200)
    chapter_id: str = Field(min_length=1, max_length=300)


class DiagnosticAnswerInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    selected_option: int = Field(ge=0, le=3)
    response_time_seconds: int = Field(ge=0, le=1800)
    confidence: float = Field(default=0.5, ge=0, le=1)


class DiagnosticSubmissionInput(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    responses: list[DiagnosticAnswerInput] = Field(min_length=10, max_length=10)
