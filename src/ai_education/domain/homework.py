"""Strict domain models for the homework tutoring workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel, utc_now

InputMode = Literal["text", "question_image", "handwriting_image", "mixed"]
LearningStage = Literal[
    "unknown",
    "no_attempt",
    "partial_attempt",
    "completed_attempt",
    "revision",
    "variant_practice",
]
HomeworkStatus = Literal[
    "received",
    "waiting_for_confirmation",
    "question_ready",
    "guiding",
    "waiting_for_student",
    "verifying",
    "reviewing",
    "variant_training",
    "completed",
    "manual_review_required",
    "failed",
]


class QuestionBankEvidence(StrictModel):
    source_id: str
    relative_path: str
    title: str
    subject: Subject | None = None
    edition: Literal["A", "B", "unknown"] = "unknown"
    region: str = "全国新高考"
    content_role: str
    topic: str | None = None
    file_type: str
    file_size: int = Field(ge=0)
    confidence: float = Field(default=0.8, ge=0, le=1)
    secure_content_available: bool = False


class QuestionContext(StrictModel):
    question_id: str = Field(default_factory=lambda: f"q_{uuid4().hex[:16]}")
    session_id: str
    student_id: str
    exam_profile_id: str
    subject: Subject
    grade: Grade
    question_type: str = "unknown"
    source_type: str = "student_text"
    stem: str = Field(min_length=1, max_length=20_000)
    options: list[str] = Field(default_factory=list)
    materials: list[dict[str, Any]] = Field(default_factory=list)
    figures: list[dict[str, Any]] = Field(default_factory=list)
    sub_questions: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list, max_length=3)
    difficulty: float = Field(default=0.5, ge=0, le=1)
    gaokao_relevance: float = Field(default=0.7, ge=0, le=1)
    parse_confidence: float = Field(default=0.9, ge=0, le=1)
    uncertain_fields: list[str] = Field(default_factory=list)
    source_evidence: list[QuestionBankEvidence] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)


class StudentStep(StrictModel):
    step_id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:10]}")
    sequence: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=8_000)
    confidence: float = Field(default=1.0, ge=0, le=1)
    region: dict[str, Any] | None = None


class StudentWork(StrictModel):
    work_id: str = Field(default_factory=lambda: f"work_{uuid4().hex[:12]}")
    question_id: str
    student_id: str
    input_mode: InputMode = "text"
    raw_text: str = Field(default="", max_length=20_000)
    steps: list[StudentStep] = Field(default_factory=list)
    final_answer: str | None = Field(default=None, max_length=8_000)
    completion_status: Literal["empty", "partial", "completed", "revision"] = "empty"
    parse_confidence: float = Field(default=1.0, ge=0, le=1)
    submitted_at: datetime = Field(default_factory=utc_now)


class HintRuntime(StrictModel):
    current_level: int = Field(default=0, ge=0, le=6)
    max_level: int = Field(default=5, ge=1, le=6)
    released_hint_ids: list[str] = Field(default_factory=list)
    hint_dependency_score: float = Field(default=0, ge=0, le=1)
    student_attempt_count: int = Field(default=0, ge=0)
    last_student_progress: str = ""
    next_release_allowed: bool = True
    cumulative_leakage_budget: float = Field(default=0, ge=0, le=1)


class GuardResult(StrictModel):
    passed: bool
    risk_score: float = Field(ge=0, le=1)
    risk_types: list[str] = Field(default_factory=list)
    sanitized: bool = False


class HomeworkTurnRecord(StrictModel):
    turn_id: str = Field(default_factory=lambda: f"turn_{uuid4().hex[:14]}")
    session_id: str
    trace_id: str
    user_intent: str
    learning_stage: LearningStage
    assistant_action: str
    student_visible_content: dict[str, Any]
    hint_level_before: int = 0
    hint_level_after: int = 0
    guard_result: GuardResult
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class HomeworkSession(StrictModel):
    session_id: str = Field(default_factory=lambda: f"hw_session_{uuid4().hex[:14]}")
    student_id: str
    grade: Grade
    province_code: str
    target_exam_year: int = Field(ge=2024, le=2100)
    exam_profile_id: str
    subject_hint: Subject | None = None
    plan_task_id: str | None = None
    status: HomeworkStatus = "received"
    active_question: QuestionContext | None = None
    student_work: StudentWork | None = None
    hint_runtime: HintRuntime = Field(default_factory=HintRuntime)
    turns: list[HomeworkTurnRecord] = Field(default_factory=list)
    state_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AnswerVaultRecord(StrictModel):
    vault_id: str = Field(default_factory=lambda: f"vault_{uuid4().hex[:16]}")
    owner_student_id: str
    question_id: str
    variant_id: str | None = None
    final_answer: str
    solution_steps: list[str] = Field(default_factory=list)
    rubric_points: list[str] = Field(default_factory=list)
    release_policy: str = "after_student_submission"
    created_at: datetime = Field(default_factory=utc_now)


class HomeworkSessionCreate(StrictModel):
    student_id: str
    grade: Grade
    province_code: str
    target_exam_year: int
    plan_task_id: str | None = None
    subject_hint: Subject | None = None


class HomeworkTurnInput(StrictModel):
    session_id: str | None = None
    question_id: str | None = None
    normalized_stem: str | None = Field(default=None, max_length=20_000)
    message: str = Field(default="", max_length=20_000)
    question_text: str = Field(default="", max_length=20_000)
    student_work: str = Field(default="", max_length=20_000)
    intent: str = "request_hint"
    subject: Subject | None = None
    client_turn_id: str | None = None
    image_text: str = Field(default="", max_length=20_000)
    image_confidence: float | None = Field(default=None, ge=0, le=1)
    image_warnings: list[str] = Field(default_factory=list)


class VariantSubmission(StrictModel):
    student_id: str
    answer: str = Field(min_length=1, max_length=20_000)
    elapsed_seconds: int = Field(default=0, ge=0, le=14_400)
