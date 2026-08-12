"""Typed contracts for the student programming growth Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel

LearningMode = Literal["beginner", "advanced"]
ProgrammingDirection = Literal[
    "computer_science_exploration",
    "artificial_intelligence",
    "data_science",
    "software_engineering",
    "algorithm_advanced",
]


class ProgrammingProfileInput(StrictModel):
    learning_mode: LearningMode = "beginner"
    target_direction: ProgrammingDirection = "computer_science_exploration"
    weekly_available_minutes: int = Field(default=120, ge=30, le=600)
    max_session_minutes: int = Field(default=40, ge=20, le=90)
    exam_period: bool = False
    programming_months: int = Field(default=0, ge=0, le=120)
    project_count: int = Field(default=0, ge=0, le=50)
    interests: list[str] = Field(default_factory=lambda: ["学习工具"])

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in values if item.strip()))
        if not cleaned or len(cleaned) > 8 or any(len(item) > 30 for item in cleaned):
            raise ValueError("兴趣方向应为 1—8 项，单项不超过 30 字")
        return cleaned


class ProgrammingDiagnosticAnswer(StrictModel):
    question_id: str = Field(min_length=1, max_length=96)
    selected_option: int = Field(ge=0, le=5)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ProgrammingDiagnosticSubmission(StrictModel):
    answers: list[ProgrammingDiagnosticAnswer] = Field(min_length=1, max_length=10)

    @field_validator("answers")
    @classmethod
    def answers_are_unique(
        cls, answers: list[ProgrammingDiagnosticAnswer]
    ) -> list[ProgrammingDiagnosticAnswer]:
        identifiers = [item.question_id for item in answers]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("同一道诊断题不能重复提交")
        return answers


class ProgrammingCodeReviewInput(StrictModel):
    code: str = Field(min_length=1, max_length=20_000)
    problem_statement: str = Field(min_length=5, max_length=2_000)
    expected_behavior: str = Field(default="", max_length=1_000)
    observed_problem: str = Field(default="", max_length=1_000)
    hint_level: int = Field(default=0, ge=0, le=5)
    review_stage: bool = False
    teacher_authorized: bool = False

    @field_validator("code", "problem_statement", "expected_behavior", "observed_problem")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ProgrammingProjectRecommendationInput(StrictModel):
    interest: str = Field(default="学习工具", min_length=1, max_length=60)
    available_weeks: int = Field(default=4, ge=2, le=12)
    use_for_portfolio: bool = False

    @field_validator("interest")
    @classmethod
    def strip_interest(cls, value: str) -> str:
        return value.strip()


class ProgrammingProjectHintInput(StrictModel):
    task_id: str = Field(min_length=1, max_length=128)
    observed_problem: str = Field(min_length=2, max_length=1_000)
    previous_hint_levels: list[int] = Field(default_factory=list, max_length=6)
    max_allowed_level: int = Field(default=3, ge=0, le=5)
    review_stage: bool = False
    teacher_authorized: bool = False

    @field_validator("previous_hint_levels")
    @classmethod
    def valid_hint_history(cls, values: list[int]) -> list[int]:
        if any(item < 0 or item > 5 for item in values):
            raise ValueError("提示等级必须在 H0—H5 之间")
        return values


class ProgrammingInterviewCreateInput(StrictModel):
    interview_type: Literal[
        "major_exploration", "comprehensive_evaluation", "project_presentation"
    ] = "project_presentation"
    focus: Literal["major_motivation", "project_experience", "technical_reasoning"] = (
        "project_experience"
    )
    available_minutes: int = Field(default=15, ge=5, le=45)


class ProgrammingInterviewAnswerInput(StrictModel):
    question_id: str = Field(min_length=1, max_length=96)
    answer_text: str = Field(min_length=5, max_length=4_000)

    @field_validator("answer_text")
    @classmethod
    def strip_answer(cls, value: str) -> str:
        return value.strip()


class CareerProgrammingProfileInput(StrictModel):
    target_level: Literal["intern", "junior"] = "intern"
    deadline_days: int = Field(default=90, ge=14, le=365)
    weekly_hours: int = Field(default=10, ge=2, le=40)
    current_identity: Literal["vocational_student", "undergraduate", "career_switcher"] = (
        "undergraduate"
    )
    python_experience: Literal["none", "basic", "project"] = "basic"
    project_experience: Literal["none", "low", "medium"] = "none"
    interview_experience: Literal["none", "some"] = "none"


class CareerDiagnosticSubmission(StrictModel):
    answers: list[ProgrammingDiagnosticAnswer] = Field(min_length=1, max_length=12)

    @field_validator("answers")
    @classmethod
    def answers_are_unique(
        cls, answers: list[ProgrammingDiagnosticAnswer]
    ) -> list[ProgrammingDiagnosticAnswer]:
        identifiers = [item.question_id for item in answers]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("同一道诊断题不能重复提交")
        return answers


class CareerCodingTaskInput(StrictModel):
    skill_id: str | None = Field(default=None, max_length=96)
    difficulty: int | None = Field(default=None, ge=1, le=3)


class CareerCodeSubmissionInput(StrictModel):
    code: str = Field(min_length=1, max_length=12_000)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return value.rstrip()


class CareerHintInput(StrictModel):
    submission_id: str | None = Field(default=None, max_length=96)
