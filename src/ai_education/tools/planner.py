"""Typed LangChain tools backed by deterministic planner services."""

from __future__ import annotations

from datetime import date
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ai_education.domain.enums import AdjustmentLevel, Grade, Subject
from ai_education.domain.models import DailyAvailability, PracticeEvent
from ai_education.services.goal import GoalService
from ai_education.services.knowledge import KnowledgeService
from ai_education.services.plan import PlanService
from ai_education.services.policy import ExamPolicyService
from ai_education.services.practice import PracticeService
from ai_education.services.time_profile import TimeProfileService


class PolicyResolveInput(BaseModel):
    province_code: str
    school_entry_year: int
    expected_gaokao_year: int


class GoalParseInput(BaseModel):
    text: str
    deadline: date | None = None


class FeasibilityInput(BaseModel):
    time_sufficiency: float = Field(ge=0, le=1)
    foundation_match: float = Field(ge=0, le=1)
    historical_improvement: float = Field(ge=0, le=1)
    target_increment_reasonableness: float = Field(ge=0, le=1)
    execution_stability: float = Field(ge=0, le=1)
    resource_availability: float = Field(ge=0, le=1)


class KnowledgeBuildInput(BaseModel):
    student_id: str
    subject: Subject
    evidence_items: list[dict[str, Any]]
    prerequisite_edges: list[dict[str, Any]] = []


class TimeBuildInput(BaseModel):
    student_id: str
    grade: Grade
    daily_capacity: list[DailyAvailability]
    subjects: list[Subject]
    subject_factors: dict[str, dict[str, float]] = {}
    max_focus_minutes: int = 45


class ReplanInput(BaseModel):
    plan_id: str
    level: AdjustmentLevel
    reason: str


FINAL_TOOL_MANIFEST: tuple[str, ...] = (
    "user_identity_resolve",
    "student_profile_query",
    "data_authorization_collect",
    "exam_policy_resolve",
    "exam_policy_validate",
    "onboarding_question_select",
    "profile_consistency_check",
    "onboarding_completeness_evaluate",
    "onboarding_summary_generate",
    "goal_source_resolve",
    "goal_parse",
    "goal_clarification_generate",
    "goal_decompose",
    "goal_metric_map",
    "goal_feasibility_evaluate",
    "goal_conflict_detect",
    "goal_save_version",
    "learning_history_query",
    "exam_paper_evidence_extract",
    "knowledge_scope_resolve",
    "assessment_evidence_sufficiency_check",
    "assessment_mode_select",
    "assessment_blueprint_generate",
    "adaptive_item_select",
    "assessment_response_score",
    "mastery_infer",
    "practice_error_classify",
    "prerequisite_gap_detect",
    "exam_skill_profile_build",
    "knowledge_profile_build",
    "knowledge_profile_validate",
    "practice_event_ingest",
    "practice_event_normalize",
    "practice_event_deduplicate",
    "practice_data_clean",
    "practice_feature_extract",
    "practice_evidence_weight",
    "mastery_dynamic_update",
    "practice_trend_analyze",
    "exam_loss_attribution",
    "plan_execution_compare",
    "availability_collect",
    "school_calendar_merge",
    "time_conflict_detect",
    "learning_preference_infer",
    "learning_efficiency_infer",
    "subject_time_budget_allocate",
    "effective_capacity_estimate",
    "task_effort_estimate",
    "elastic_buffer_allocate",
    "time_profile_build",
    "availability_change_detect",
    "learning_path_build",
    "knowledge_priority_calculate",
    "stage_partition",
    "candidate_task_generate",
    "content_resource_match",
    "spaced_review_schedule",
    "timed_training_insert",
    "assessment_task_insert",
    "plan_schedule_optimize",
    "plan_validate",
    "plan_explanation_generate",
    "adjustment_trigger_evaluate",
    "plan_revise",
    "plan_publish",
    "plan_version_query",
)


class PlannerToolbox:
    """Expose key capabilities as LangChain tools and the complete capability manifest."""

    def __init__(
        self,
        policy: ExamPolicyService,
        goal: GoalService,
        knowledge: KnowledgeService,
        time_profile: TimeProfileService,
        practice: PracticeService,
        plan: PlanService,
    ) -> None:
        self.policy = policy
        self.goal = goal
        self.knowledge = knowledge
        self.time_profile = time_profile
        self.practice = practice
        self.plan = plan

    def as_langchain_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                name="exam_policy_resolve",
                description="按省份、入学年份和高考年份读取经配置的考试政策",
                args_schema=PolicyResolveInput,
                func=lambda province_code, school_entry_year, expected_gaokao_year: (
                    self.policy.resolve(
                        province_code, school_entry_year, expected_gaokao_year
                    ).model_dump(mode="json")
                ),
            ),
            StructuredTool.from_function(
                name="goal_parse",
                description="从自然语言目标提取科目、当前分、目标分和截止日期，不补写未知值",
                args_schema=GoalParseInput,
                func=lambda text, deadline=None: self.goal.parse(
                    text, explicit_deadline=deadline
                ).model_dump(mode="json"),
            ),
            StructuredTool.from_function(
                name="goal_feasibility_evaluate",
                description="按规格书固定权重评估目标可行性",
                args_schema=FeasibilityInput,
                func=lambda **kwargs: self.goal.feasibility(kwargs),
            ),
            StructuredTool.from_function(
                name="knowledge_profile_build",
                description="融合带来源和权重的证据形成知识点级画像",
                args_schema=KnowledgeBuildInput,
                func=lambda student_id, subject, evidence_items, prerequisite_edges=None: (
                    self.knowledge.build_profile(
                        student_id,
                        Subject(subject),
                        evidence_items,
                        prerequisite_edges=prerequisite_edges,
                    ).model_dump(mode="json")
                ),
            ),
            StructuredTool.from_function(
                name="time_profile_build",
                description="计算有效容量、学科预算与不可预排满的弹性缓冲",
                args_schema=TimeBuildInput,
                func=self._build_time_profile,
            ),
            StructuredTool.from_function(
                name="practice_event_ingest",
                description="去重、清洗练习事件并保守更新掌握度",
                args_schema=PracticeEvent,
                func=lambda **kwargs: self.practice.ingest(
                    PracticeEvent.model_validate(kwargs)
                ).model_dump(mode="json"),
            ),
            StructuredTool.from_function(
                name="plan_revise",
                description="按调整等级创建计划新版本，绝不覆盖已发布版本",
                args_schema=ReplanInput,
                func=lambda plan_id, level, reason: self.plan.revise(
                    plan_id, AdjustmentLevel(level), reason=reason
                ).model_dump(mode="json"),
            ),
        ]

    def capability_manifest(self) -> dict[str, str]:
        concrete = {tool.name for tool in self.as_langchain_tools()}
        return {
            name: "implemented" if name in concrete else "workflow_service"
            for name in FINAL_TOOL_MANIFEST
        }

    def _build_time_profile(
        self,
        student_id: str,
        grade: Grade,
        daily_capacity: list[DailyAvailability],
        subjects: list[Subject],
        subject_factors: dict[str, dict[str, float]] | None = None,
        max_focus_minutes: int = 45,
    ) -> dict[str, Any]:
        return self.time_profile.build(
            student_id,
            Grade(grade),
            [DailyAvailability.model_validate(item) for item in daily_capacity],
            [Subject(item) for item in subjects],
            subject_factors or {},
            max_focus_minutes=max_focus_minutes,
        ).model_dump(mode="json")
