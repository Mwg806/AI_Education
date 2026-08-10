"""V1 contracts for the four-mode career education Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel

CareerMode = Literal["CAREER", "PROJECT", "CODING", "GAOKAO"]


class CareerEducationOnboardingInput(StrictModel):
    target_job_id: Literal["JOB_PY_BACKEND"] = "JOB_PY_BACKEND"
    identity: Literal[
        "high_school_student",
        "vocational_student",
        "undergraduate",
        "career_switcher",
    ]
    education_stage: Literal[
        "high_school",
        "vocational",
        "undergraduate",
        "graduate",
        "other",
    ]
    programming_level: Literal["beginner", "basic", "project"]
    known_languages: list[str] = Field(default_factory=lambda: ["Python"], max_length=6)
    weekly_hours: int = Field(ge=2, le=40)
    learning_goal: Literal[
        "gaokao",
        "internship",
        "campus_recruitment",
        "career_change",
    ]
    target_period_weeks: int = Field(ge=4, le=52)

    @field_validator("known_languages")
    @classmethod
    def normalize_languages(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not cleaned:
            raise ValueError("至少填写一种已接触语言")
        return cleaned


class CareerModeSwitchInput(StrictModel):
    mode: CareerMode


class CareerChatInput(StrictModel):
    message: str = Field(min_length=2, max_length=2000)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        return value.strip()


class CareerProjectStartInput(StrictModel):
    project_id: str | None = Field(default=None, max_length=64)
    randomize: bool = False


class CareerProjectChatInput(StrictModel):
    message: str = Field(min_length=2, max_length=3000)
    session_id: str | None = Field(default=None, max_length=80)

    @field_validator("message")
    @classmethod
    def strip_project_message(cls, value: str) -> str:
        return value.strip()


class CareerProjectAnswerInput(StrictModel):
    development_plan: str = Field(min_length=20, max_length=12000)
    technology_selection: str = Field(min_length=10, max_length=8000)
    architecture_design: str = Field(min_length=10, max_length=8000)
    database_design: str = Field(min_length=10, max_length=8000)
    api_design: str = Field(min_length=10, max_length=8000)
    problem_solutions: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "development_plan",
        "technology_selection",
        "architecture_design",
        "database_design",
        "api_design",
    )
    @classmethod
    def strip_answer(cls, value: str) -> str:
        return value.strip()


class CareerCodingNextInput(StrictModel):
    category: Literal["python", "api", "backend", "sql", "debug"] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=3)
    language: Literal["python"] = "python"
    exclude_question_id: str | None = Field(default=None, max_length=80)
    selection_mode: Literal["recommended", "random", "selected"] = "recommended"
    question_id: str | None = Field(default=None, max_length=80)


class CareerCodingSubmissionInput(StrictModel):
    code: str = Field(min_length=1, max_length=12000)
    action: Literal["run", "submit"] = "submit"

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return value.rstrip()


class CareerSolutionRequestInput(StrictModel):
    confirm: Literal[True]


class GaokaoProgrammingNextInput(StrictModel):
    exclude_question_id: str | None = Field(default=None, max_length=96)


class GaokaoProgrammingSubmissionInput(StrictModel):
    answer: str = Field(min_length=1, max_length=12000)
    response_time_seconds: int = Field(default=60, ge=1, le=14400)

    @field_validator("answer")
    @classmethod
    def strip_gaokao_answer(cls, value: str) -> str:
        return value.strip()
