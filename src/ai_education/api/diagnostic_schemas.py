"""Strict API schemas for quick diagnostic sessions."""

from pydantic import Field, model_validator

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel


class DiagnosticCreateInput(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    grade: Grade
    subject: Subject
    curriculum_version: str = Field(min_length=1, max_length=200)
    chapter_id: str | None = Field(default=None, min_length=1, max_length=300)
    chapter_ids: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_chapter_scope(self) -> "DiagnosticCreateInput":
        selected = self.chapter_ids or ([self.chapter_id] if self.chapter_id else [])
        if not selected:
            raise ValueError("必须选择至少 1 个诊断章节")
        deduplicated = list(dict.fromkeys(selected))
        if len(deduplicated) != len(selected):
            raise ValueError("诊断章节不能重复选择")
        if "__all_chapters__" in deduplicated and len(deduplicated) > 1:
            raise ValueError("整本书范围不能与具体章节同时选择")
        object.__setattr__(self, "chapter_ids", deduplicated)
        object.__setattr__(self, "chapter_id", deduplicated[0])
        return self


class DiagnosticAnswerInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    selected_option: int = Field(ge=0, le=3)
    response_time_seconds: int = Field(ge=0, le=1800)
    confidence: float = Field(default=0.5, ge=0, le=1)


class DiagnosticSubmissionInput(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    responses: list[DiagnosticAnswerInput] = Field(min_length=10, max_length=10)
