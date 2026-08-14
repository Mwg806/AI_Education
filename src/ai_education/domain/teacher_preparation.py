"""Strict domain models for teacher-in-the-loop lesson preparation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel, utc_now


class LessonType(StrEnum):
    NEW_LESSON = "new_lesson"
    REVIEW = "review"
    THEMATIC_REVIEW = "thematic_review"
    LAB = "lab"
    PAPER_REVIEW = "paper_review"


class LessonPlanStatus(StrEnum):
    DRAFT = "draft"
    TEACHER_REVIEW = "teacher_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    EXECUTED = "executed"
    FEEDBACK_RECORDED = "feedback_recorded"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class TeachingContext(StrictModel):
    teacher_id: str = Field(min_length=1, max_length=64)
    classroom_id: int = Field(gt=0)
    grade: Grade
    subject: Subject
    lesson_type: LessonType
    topic: str = Field(min_length=2, max_length=200)
    lesson_request: str = Field(min_length=5, max_length=4_000)
    lesson_count: int = Field(default=1, ge=1, le=6)
    duration_minutes: int = Field(default=45, ge=20, le=240)
    buffer_minutes: int = Field(default=3, ge=2, le=20)
    teaching_stage: str = Field(default="日常教学", min_length=2, max_length=80)
    textbook_version: str = Field(default="教师指定教材", min_length=1, max_length=120)
    exam_year: int = Field(default=2027, ge=2025, le=2100)
    exam_blueprint_version: str = Field(min_length=1, max_length=128)
    curriculum_version: str = Field(default="2017_2020_revision", max_length=128)
    class_size: int = Field(default=0, ge=0, le=200)
    available_equipment: list[str] = Field(default_factory=list, max_length=20)
    diagnosis_summary: dict = Field(default_factory=dict)
    diagnosis_adapted: bool = False

    @field_validator("topic", "lesson_request", "teaching_stage", "textbook_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def reserve_classroom_buffer(self) -> TeachingContext:
        if self.buffer_minutes >= self.duration_minutes:
            raise ValueError("课堂缓冲时间必须小于总课时")
        return self


class TeachingResourceReference(StrictModel):
    resource_id: str = Field(min_length=1, max_length=96)
    subject: Subject
    title: str = Field(min_length=1, max_length=240)
    material_type: str = Field(min_length=1, max_length=240)
    source_organization: str = Field(min_length=1, max_length=300)
    source_location: str = Field(min_length=1, max_length=500)
    source_url: str = Field(default="", max_length=1_000)
    relative_path: str = Field(min_length=1, max_length=500)
    page_count: int = Field(ge=1)
    excerpt: str = Field(default="", max_length=8_000)
    copyright_status: Literal[
        "public_teaching_reference",
        "original_optimized_reference",
        "review_required",
    ] = "review_required"
    checksum_verified: bool = False


class LearningObjective(StrictModel):
    objective_id: str = Field(pattern=r"^obj_[1-9][0-9]*$")
    description: str = Field(min_length=4, max_length=500)
    priority: Literal["must", "recommended", "extension"] = "must"
    observable_behavior: str = Field(min_length=4, max_length=500)
    exam_ability_tags: list[str] = Field(min_length=1, max_length=8)
    source_ref_ids: list[str] = Field(default_factory=list, max_length=10)


class TeachingActivity(StrictModel):
    activity_id: str = Field(pattern=r"^act_[1-9][0-9]*$")
    stage: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(ge=1, le=120)
    objective_ids: list[str] = Field(min_length=1, max_length=10)
    teacher_action: str = Field(min_length=3, max_length=1_200)
    student_action: str = Field(min_length=3, max_length=1_200)
    organization: str = Field(min_length=1, max_length=160)
    expected_output: str = Field(min_length=2, max_length=600)
    assessment_method: str = Field(min_length=2, max_length=500)
    decision_rule: str = Field(default="按课堂证据决定补讲或继续", max_length=500)


class BoardPlan(StrictModel):
    board_plan_id: str = "board_1"
    layout: dict[str, str] = Field(min_length=1, max_length=6)
    timeline: list[str] = Field(min_length=1, max_length=20)
    persistent_content: list[str] = Field(min_length=1, max_length=20)
    slide_only_content: list[str] = Field(default_factory=list, max_length=20)
    compact_version: list[str] = Field(min_length=1, max_length=20)
    estimated_writing_minutes: int = Field(ge=1, le=30)


class AssessmentItem(StrictModel):
    question_id: str = Field(pattern=r"^q_(check|home)_[1-9][0-9]*$")
    objective_ids: list[str] = Field(min_length=1, max_length=10)
    purpose: Literal["in_class_check", "homework"] = "in_class_check"
    prompt: str = Field(min_length=4, max_length=2_000)
    answer_outline: str = Field(min_length=2, max_length=2_000)
    scoring_rubric: list[str] = Field(min_length=1, max_length=12)
    difficulty: float = Field(ge=0.1, le=0.95)
    knowledge_tags: list[str] = Field(min_length=1, max_length=10)
    ability_tags: list[str] = Field(min_length=1, max_length=10)
    common_error_tags: list[str] = Field(default_factory=list, max_length=10)
    decision_rule: str = Field(default="", max_length=500)


class DifferentiationLayer(StrictModel):
    layer_id: Literal["support", "core", "advanced"]
    target_profile: str = Field(min_length=2, max_length=300)
    task_adjustment: str = Field(min_length=3, max_length=800)
    scaffolds: list[str] = Field(default_factory=list, max_length=10)
    objective_ids: list[str] = Field(min_length=1, max_length=10)


class AlignmentRow(StrictModel):
    objective_id: str
    objective_description: str
    source_ref_ids: list[str] = Field(default_factory=list)
    ability_tags: list[str] = Field(default_factory=list)
    activity_ids: list[str] = Field(default_factory=list)
    board_evidence: list[str] = Field(default_factory=list)
    assessment_ids: list[str] = Field(default_factory=list)
    diagnosis_adaptation: str = "未使用班级学情"
    status: Literal["pass", "fail"] = "fail"


class QualityIssue(StrictModel):
    code: str = Field(min_length=1, max_length=96)
    severity: Literal["low", "medium", "high"]
    message: str = Field(min_length=2, max_length=1_000)
    component_id: str | None = Field(default=None, max_length=96)
    action: Literal["auto_revised", "teacher_review", "blocked"] = "teacher_review"


class LessonQualityReport(StrictModel):
    alignment_status: Literal["pass", "fail"]
    feasibility_status: Literal["pass", "fail"]
    resource_compliance_status: Literal["pass", "review_required", "fail"]
    estimated_activity_minutes: int = Field(ge=0)
    buffer_minutes: int = Field(ge=0)
    issues: list[QualityIssue] = Field(default_factory=list)
    teacher_review_required: bool = True
    publishable: bool = False


class LessonPlanVersion(StrictModel):
    lesson_plan_id: str = Field(default_factory=lambda: f"lesson_{uuid4().hex[:18]}")
    version: int = Field(default=1, ge=1)
    parent_version: int | None = Field(default=None, ge=1)
    status: LessonPlanStatus = LessonPlanStatus.TEACHER_REVIEW
    context: TeachingContext
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=5, max_length=3_000)
    key_points: list[str] = Field(min_length=1, max_length=20)
    difficult_points: list[str] = Field(min_length=1, max_length=20)
    objectives: list[LearningObjective] = Field(min_length=1, max_length=10)
    activities: list[TeachingActivity] = Field(min_length=1, max_length=20)
    resources: list[TeachingResourceReference] = Field(default_factory=list, max_length=12)
    board_plan: BoardPlan
    assessments: list[AssessmentItem] = Field(min_length=1, max_length=20)
    differentiation_plan: list[DifferentiationLayer] = Field(min_length=1, max_length=3)
    contingency_paths: list[str] = Field(default_factory=list, max_length=10)
    alignment_matrix: list[AlignmentRow] = Field(min_length=1, max_length=10)
    quality_report: LessonQualityReport
    locked_component_ids: list[str] = Field(default_factory=list, max_length=100)
    change_summary: list[str] = Field(default_factory=list, max_length=30)
    revision_prompt: str | None = Field(default=None, max_length=4_000)
    revision_component: (
        Literal["full", "objectives", "activities", "board", "assessments", "differentiation"]
        | None
    ) = None
    revision_locked_component_ids: list[str] = Field(default_factory=list, max_length=100)
    generation_mode: Literal["llm", "reference_template"]
    source_versions: dict[str, str] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)
    approved_by: str | None = Field(default=None, max_length=64)
    approved_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class PostLessonFeedback(StrictModel):
    feedback_id: str = Field(default_factory=lambda: f"feedback_{uuid4().hex[:18]}")
    lesson_plan_id: str = Field(min_length=1, max_length=96)
    lesson_version: int = Field(ge=1)
    teacher_id: str = Field(min_length=1, max_length=64)
    actual_duration_minutes: int = Field(ge=1, le=360)
    completed_activity_ids: list[str] = Field(default_factory=list, max_length=30)
    skipped_activity_ids: list[str] = Field(default_factory=list, max_length=30)
    class_check_accuracy: float | None = Field(default=None, ge=0, le=1)
    teacher_rating: int = Field(ge=1, le=5)
    effective_components: list[str] = Field(default_factory=list, max_length=30)
    issues: list[str] = Field(default_factory=list, max_length=30)
    teacher_notes: str = Field(default="", max_length=4_000)
    created_at: datetime = Field(default_factory=utc_now)
