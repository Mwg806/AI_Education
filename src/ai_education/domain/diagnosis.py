"""Typed learning-state evidence and diagnosis contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel, utc_now


AssessmentType = Literal[
    "formal_exam", "mock_exam", "diagnostic", "homework", "practice",
    "teacher_evaluation", "agent_feedback",
]


class LearningEvidenceRecord(StrictModel):
    """One observable answer or teacher assessment; never a diagnosis by itself."""

    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid4().hex}")
    assessment_id: str = Field(min_length=1, max_length=128)
    assessment_type: AssessmentType
    question_id: str = Field(min_length=1, max_length=128)
    subject: Subject = Subject.MATHEMATICS
    knowledge_tags: list[str] = Field(min_length=1, max_length=8)
    question_type: str = Field(min_length=1, max_length=80)
    ability_tags: list[str] = Field(default_factory=list, max_length=8)
    difficulty: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0)
    max_score: float = Field(gt=0.0)
    duration_seconds: int | None = Field(default=None, ge=1, le=14_400)
    hint_count: int = Field(default=0, ge=0, le=50)
    attempt_count: int = Field(default=1, ge=1, le=50)
    error_tags: list[str] = Field(default_factory=list, max_length=10)
    step_trace: str | None = Field(default=None, max_length=2_000)
    source_id: str | None = Field(default=None, max_length=256)
    occurred_at: datetime = Field(default_factory=utc_now)
    source_reliability: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_flags: list[str] = Field(default_factory=list)
    evidence_weight: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("knowledge_tags", "ability_tags", "error_tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def score_must_fit_scale(self) -> LearningEvidenceRecord:
        if self.score > self.max_score:
            raise ValueError("score 不能高于 max_score")
        return self

    @property
    def normalized_score(self) -> float:
        return self.score / self.max_score


class DiagnosisContext(StrictModel):
    student_id: str = Field(min_length=1, max_length=128)
    grade: Grade
    province_code: str = Field(default="43", min_length=2, max_length=12)
    subject: Subject = Subject.MATHEMATICS
    target_exam_year: int = Field(ge=2025, le=2040)
    curriculum_version: str | None = Field(default=None, max_length=128)
    diagnosis_request: str = Field(default="识别当前稳定薄弱点与下一步需要补充的证据", min_length=1, max_length=1_000)
    diagnosis_window: str = Field(default="recent_30_days", max_length=80)


class DimensionState(StrictModel):
    dimension_id: str
    dimension_label: str
    mastery_probability: float = Field(ge=0.0, le=1.0)
    mastery_level: Literal["insufficient_evidence", "needs_support", "developing", "proficient", "strong"]
    confidence: float = Field(ge=0.0, le=1.0)
    credible_interval_low: float = Field(ge=0.0, le=1.0)
    credible_interval_high: float = Field(ge=0.0, le=1.0)
    valid_evidence_count: int = Field(ge=0)
    independent_assessment_count: int = Field(ge=0)
    question_type_count: int = Field(ge=0)
    trend: Literal["improving", "stable", "declining", "unknown"] = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)
    status_basis: str


class EvidenceGate(StrictModel):
    valid_evidence_count: int = Field(ge=0)
    rejected_evidence_count: int = Field(ge=0)
    independent_assessment_count: int = Field(ge=0)
    question_type_count: int = Field(ge=0)
    difficulty_band_count: int = Field(ge=0)
    coverage_score: float = Field(ge=0.0, le=1.0)
    consistency_score: float = Field(ge=0.0, le=1.0)
    sufficiency_level: Literal["insufficient", "preliminary", "stable"]
    allowed_conclusion: str
    missing_evidence: list[str] = Field(default_factory=list)


class ErrorPattern(StrictModel):
    pattern_id: str = Field(default_factory=lambda: f"pattern_{uuid4().hex}")
    label: str
    description: str
    occurrence_count: int = Field(ge=2)
    independent_assessment_count: int = Field(ge=2)
    knowledge_tags: list[str]
    evidence_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class CauseHypothesis(StrictModel):
    hypothesis_id: str = Field(default_factory=lambda: f"hyp_{uuid4().hex}")
    hypothesis: str
    support: list[str]
    counterevidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    verification_needed: str
    prohibited_personality_inference: bool = True


class DiagnosisNarrativeBundle(StrictModel):
    student_summary: str = ""
    teacher_summary: str = ""
    evidence_boundary: str = ""
    next_evidence_request: str = ""
    generation_mode: Literal["llm", "unavailable"] = "unavailable"


class LearningStateDiagnosis(StrictModel):
    diagnosis_id: str = Field(default_factory=lambda: f"diag_{uuid4().hex}")
    student_id: str
    subject: Subject
    state_version: int = Field(default=1, ge=1)
    blueprint_version: str
    schema_version: str = "1.0"
    diagnosis_status: Literal["insufficient_evidence", "preliminary", "stable", "review_required"]
    evidence_gate: EvidenceGate
    knowledge_states: list[DimensionState] = Field(default_factory=list)
    question_type_states: list[DimensionState] = Field(default_factory=list)
    ability_states: list[DimensionState] = Field(default_factory=list)
    observed_facts: list[str] = Field(default_factory=list)
    stable_error_patterns: list[ErrorPattern] = Field(default_factory=list)
    cause_hypotheses: list[CauseHypothesis] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    reassessment_spec: dict[str, object] = Field(default_factory=dict)
    narrative: DiagnosisNarrativeBundle = Field(default_factory=DiagnosisNarrativeBundle)
    review_status: Literal["not_required", "pending", "confirmed", "corrected"] = "not_required"
    previous_version: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TeacherReview(StrictModel):
    review_id: str = Field(default_factory=lambda: f"review_{uuid4().hex}")
    diagnosis_id: str
    student_id: str
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: Literal["confirm", "correct", "request_more_evidence"]
    comment: str = Field(min_length=1, max_length=2_000)
    corrections: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
