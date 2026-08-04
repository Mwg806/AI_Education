"""Typed contracts for the National I English reading and language Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel

EnglishTrainingMode = Literal["reading_multiple_choice", "seven_of_five"]


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


class EnglishReviewCompletionInput(StrictModel):
    result: Literal["remembered", "needs_review"]
