"""Core education domain models from the national-I planning specification."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from ai_education.domain.enums import Grade, PlanStatus, Subject
from ai_education.domain.protocols import Evidence, StrictModel, utc_now


class ExamProfile(StrictModel):
    exam_profile_id: str
    exam_system: Literal["new_gaokao"] = "new_gaokao"
    national_paper_type: Literal["national_paper_i"] = "national_paper_i"
    province_code: str
    cohort_entry_year: int = Field(ge=2000, le=2100)
    exam_year: int = Field(ge=2000, le=2100)
    subject_model: str
    compulsory_subjects: list[Subject]
    first_choice_subjects: list[Subject]
    second_choice_subjects: list[Subject]
    elective_subjects: list[Subject] = Field(default_factory=list)
    selected_subjects: list[Subject] = Field(default_factory=list)
    score_rules: dict[str, str]
    official_exam_milestones: list[dict[str, Any]] = Field(default_factory=list)
    policy_version: str
    effective_date: date
    expires_at: date | None = None
    status: Literal["active", "expired", "manual_review_required"] = "active"
    route_basis_year: int | None = None
    source_urls: list[str] = Field(default_factory=list)
    requires_annual_reconfirmation: bool = False
    verification_note: str | None = None

    @property
    def is_current(self) -> bool:
        return self.status == "active" and (
            self.expires_at is None or self.expires_at >= date.today()
        )


class StudentAcademicProfile(StrictModel):
    student_id: str
    grade: Grade
    school_term: str
    province_code: str
    school_entry_year: int
    target_exam_year: int
    timezone: str = "Asia/Shanghai"
    school_type: str | None = None
    curriculum_versions: dict[str, str] = Field(default_factory=dict)
    exam_profile_id: str | None = None
    selected_subjects: list[Subject] = Field(default_factory=list)
    subject_selection_confirmed: bool = False
    subject_intentions: list[Subject] = Field(default_factory=list)
    foreign_language_type: str = "english"
    class_progress: dict[str, Any] = Field(default_factory=dict)
    current_level: dict[str, float] = Field(default_factory=dict)
    data_authorization_scopes: set[str] = Field(default_factory=set)
    profile_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_subject_selection(self) -> StudentAcademicProfile:
        if self.grade in {Grade.GRADE_11, Grade.GRADE_12} and not self.subject_selection_confirmed:
            raise ValueError("高二、高三必须确认正式选科")
        if (
            self.grade == Grade.GRADE_10
            and not self.subject_selection_confirmed
            and self.selected_subjects
        ):
            raise ValueError("高一未确认选科时应记录为 subject_intentions")
        return self


class GoalTarget(StrictModel):
    metric: str
    current_value: float | None = None
    target_value: float
    unit: str = "score"


class LearningGoal(StrictModel):
    goal_id: str = Field(default_factory=lambda: f"goal_{uuid4().hex[:12]}")
    student_id: str
    goal_type: str
    subject: Subject | None = None
    target: GoalTarget
    deadline: date
    priority: int = Field(default=1, ge=1, le=10)
    exam_context: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    source: str = "student"
    status: Literal["draft", "active", "completed", "cancelled"] = "draft"
    confidence: float = Field(default=1.0, ge=0, le=1)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def deadline_must_be_future(self) -> LearningGoal:
        if self.deadline < date.today():
            raise ValueError("目标截止日期不得早于当前日期")
        return self


class GoalParseResult(StrictModel):
    goal_type: str | None = None
    subject: Subject | None = None
    current_value: float | None = None
    target_value: float | None = None
    deadline: date | None = None
    deadline_event: str | None = None
    daily_time_limit_minutes: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    raw_text: str


class KnowledgeState(StrictModel):
    student_id: str
    subject: Subject
    knowledge_id: str
    mastery_probability: float = Field(ge=0, le=1)
    mastery_level: Literal["not_started", "emerging", "developing", "proficient", "mastered"]
    confidence: float = Field(ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    objective_evidence_count: int = Field(default=0, ge=0)
    self_report_evidence_count: int = Field(default=0, ge=0)
    credible_interval_low: float = Field(default=0, ge=0, le=1)
    credible_interval_high: float = Field(default=1, ge=0, le=1)
    calibration_bias: float | None = Field(default=None, ge=-1, le=1)
    last_practiced_at: datetime | None = None
    forgetting_risk: float = Field(default=0.5, ge=0, le=1)
    prerequisite_status: str = "unknown"
    error_tags: list[str] = Field(default_factory=list)
    model_version: str = "weighted_rule_v1"
    evidence: list[Evidence] = Field(default_factory=list)


class KnowledgeProfile(StrictModel):
    profile_id: str = Field(default_factory=lambda: f"kp_{uuid4().hex[:12]}")
    student_id: str
    profile_version: int = Field(default=1, ge=1)
    knowledge_states: list[KnowledgeState]
    question_type_states: list[dict[str, Any]] = Field(default_factory=list)
    exam_skill_states: list[dict[str, Any]] = Field(default_factory=list)
    priority_gaps: list[str] = Field(default_factory=list)
    prerequisite_gaps: list[dict[str, Any]] = Field(default_factory=list)
    assessment_quality: dict[str, float]
    assessment_mode: Literal["quick", "standard", "full", "paper_based"]
    generated_at: datetime = Field(default_factory=utc_now)


class DailyAvailability(StrictModel):
    weekday: int = Field(ge=1, le=7)
    available_minutes: int = Field(ge=0, le=720)
    preferred_period: Literal["morning", "noon", "evening", "flexible"] = "evening"
    energy_coefficient: float = Field(default=0.9, ge=0.3, le=1.2)


class TimeProfile(StrictModel):
    time_profile_id: str = Field(default_factory=lambda: f"tp_{uuid4().hex[:12]}")
    student_id: str
    weekly_natural_minutes: int = Field(ge=0)
    weekly_effective_minutes: int = Field(ge=0)
    recommended_scheduled_minutes: int = Field(ge=0)
    buffer_minutes: int = Field(ge=0)
    subject_budgets: dict[str, int]
    daily_capacity: list[DailyAvailability]
    efficiency_by_task_type: dict[str, float] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    max_focus_minutes: int = Field(default=45, ge=15, le=180)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_capacity(self) -> TimeProfile:
        if self.recommended_scheduled_minutes + self.buffer_minutes > self.weekly_effective_minutes:
            raise ValueError("排期时长与缓冲不得超过有效容量")
        if sum(self.subject_budgets.values()) > self.recommended_scheduled_minutes:
            raise ValueError("学科预算不得超过推荐排期时长")
        return self


class CompletionRule(StrictModel):
    minimum_item_count: int = Field(default=5, ge=0)
    minimum_accuracy: float = Field(default=0.7, ge=0, le=1)
    maximum_hint_dependency: float = Field(default=0.3, ge=0, le=1)


class PlanTask(StrictModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    plan_id: str
    stage_id: str
    subject: Subject
    task_type: str
    knowledge_ids: list[str]
    content_ids: list[str] = Field(default_factory=list)
    planned_start: datetime
    planned_duration_minutes: int = Field(ge=5, le=180)
    difficulty: float = Field(ge=0, le=1)
    exam_relevance: float = Field(ge=0, le=1)
    completion_rule: CompletionRule
    flexibility: Literal["fixed", "movable_within_day", "movable_within_week"] = (
        "movable_within_week"
    )
    status: Literal["scheduled", "in_progress", "completed", "skipped"] = "scheduled"
    rationale: str
    goal_ids: list[str]
    prerequisite_task_ids: list[str] = Field(default_factory=list)


class PlanStage(StrictModel):
    stage_id: str = Field(default_factory=lambda: f"stage_{uuid4().hex[:12]}")
    name: str
    start_date: date
    end_date: date
    objective: str
    completion_conditions: dict[str, Any]


class PlanValidation(StrictModel):
    valid: bool
    checks: dict[str, bool]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LearningPlan(StrictModel):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:12]}")
    student_id: str
    goal_ids: list[str]
    version: int = Field(default=1, ge=1)
    status: PlanStatus = PlanStatus.DRAFT
    plan_start: date
    plan_end: date
    exam_profile_id: str
    stages: list[PlanStage]
    tasks: list[PlanTask]
    weekly_capacity_minutes: int
    scheduled_minutes: int
    buffer_minutes: int
    subject_time_budgets: dict[str, int]
    generation_basis: dict[str, str]
    subject_goals: list[dict[str, Any]] = Field(default_factory=list)
    validation: PlanValidation | None = None
    explanations: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    supersedes_version: int | None = None

    @field_validator("tasks")
    @classmethod
    def task_ids_must_be_unique(cls, tasks: list[PlanTask]) -> list[PlanTask]:
        ids = [task.task_id for task in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("任务 ID 必须唯一")
        return tasks


class PracticeEvent(StrictModel):
    event_id: str
    student_id: str
    session_id: str
    task_id: str | None = None
    item_id: str
    subject: Subject
    knowledge_ids: list[str]
    event_type: str
    timestamp: datetime
    response: dict[str, Any]
    behavior: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class PracticeUpdate(StrictModel):
    event_id: str
    duplicate: bool = False
    valid: bool = True
    anomaly_tags: list[str] = Field(default_factory=list)
    effective_seconds: int = 0
    quality_score: float = Field(default=0, ge=0, le=1)
    evidence_weight: float = Field(default=0, ge=0, le=1)
    error_type: str | None = None
    mastery_updates: list[dict[str, Any]] = Field(default_factory=list)
    replan_check_required: bool = False


class OnboardingSession(StrictModel):
    onboarding_id: str = Field(default_factory=lambda: f"onboarding_{uuid4().hex[:12]}")
    student_id: str
    status: str = "ONBOARDING_STARTED"
    answers: dict[str, Any] = Field(default_factory=dict)
    confirmed_exam_profile_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    data_version: int = 1
