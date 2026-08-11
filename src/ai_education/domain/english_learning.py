"""Typed contracts for the National I English reading and language Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel

EnglishTrainingMode = Literal["reading_multiple_choice", "seven_of_five"]
EnglishTaskType = Literal[
    "reading_comprehension",
    "vocabulary_explanation",
    "grammar_correction",
    "writing_revision",
    "translation",
    "speaking_practice",
    "exam_practice",
    "learning_plan",
    "progress_query",
]
EnglishResponseMode = Literal[
    "quick",
    "teaching",
    "guided",
    "exam",
    "immersive",
    "correction",
]
EnglishLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class EnglishTextAnalysisInput(StrictModel):
    title: str = Field(default="自选英语材料", min_length=1, max_length=160)
    text: str = Field(min_length=80, max_length=15_000)

    @field_validator("title", "text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class EnglishTrainingCreateInput(EnglishTextAnalysisInput):
    mode: EnglishTrainingMode = "reading_multiple_choice"
    question_count: int = Field(default=4, ge=3, le=6)


class EnglishAnswerInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=96)
    selected_option: int = Field(ge=0, le=6)
    response_time_ms: int = Field(default=1_000, ge=100, le=3_600_000)
    hint_count: int = Field(default=0, ge=0, le=5)


class EnglishTrainingSubmissionInput(StrictModel):
    answers: list[EnglishAnswerInput] = Field(min_length=1, max_length=10)

    @field_validator("answers")
    @classmethod
    def answers_are_unique(cls, answers: list[EnglishAnswerInput]) -> list[EnglishAnswerInput]:
        ids = [item.question_id for item in answers]
        if len(ids) != len(set(ids)):
            raise ValueError("同一题不能重复提交")
        return answers


class EnglishReadingHintInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=96)
    level: int = Field(ge=1, le=4)


class EnglishReviewCompletionInput(StrictModel):
    result: Literal["remembered", "needs_review"]


class EnglishTaskInput(StrictModel):
    task_type: EnglishTaskType
    source_text: str = Field(default="", max_length=15_000)
    user_message: str = Field(default="", max_length=2_000)
    response_mode: EnglishResponseMode = "teaching"
    detail_level: Literal["brief", "medium", "detailed"] = "medium"
    revision_level: int = Field(default=2, ge=1, le=4)
    feedback_mode: Literal["instant", "delayed"] = "instant"
    scenario: str = Field(default="新高考英语口语表达", max_length=120)
    include_exercises: bool = True
    include_learning_record: bool = True
    exam_section: Literal[
        "reading",
        "seven_of_five",
        "cloze",
        "grammar_fill",
        "writing",
        "integrated",
    ] = "integrated"
    question_count: int = Field(default=5, ge=1, le=15)

    @field_validator("source_text", "user_message", "scenario")
    @classmethod
    def normalize_task_text(cls, value: str) -> str:
        return value.strip()


class EnglishLearnerProfileInput(StrictModel):
    self_reported_level: EnglishLevel = "B1"
    daily_minutes: int = Field(default=30, ge=10, le=180)
    preferred_mode: EnglishResponseMode = "teaching"
    explanation_depth: Literal["brief", "medium", "detailed"] = "medium"
    show_examples: bool = True
    show_exercises: bool = True
    learning_goals: list[str] = Field(default_factory=lambda: ["新高考全国Ⅰ卷英语"])

    @field_validator("learning_goals")
    @classmethod
    def goals_are_safe(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if not cleaned or len(cleaned) > 8 or any(len(item) > 80 for item in cleaned):
            raise ValueError("学习目标数量应为 1—8 项，单项不超过 80 字")
        return cleaned
