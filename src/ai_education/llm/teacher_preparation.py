"""Structured LLM boundary for source-grounded teacher lesson preparation."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.teacher_preparation import TEACHER_PREPARATION_PROMPT


class GeneratedObjective(StrictModel):
    description: str = Field(min_length=4, max_length=500)
    priority: Literal["must", "recommended", "extension"] = "must"
    observable_behavior: str = Field(min_length=4, max_length=500)
    exam_ability_tags: list[str] = Field(min_length=1, max_length=8)


class GeneratedActivity(StrictModel):
    stage: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(ge=1, le=120)
    objective_indexes: list[int] = Field(min_length=1, max_length=8)
    teacher_action: str = Field(min_length=3, max_length=1_200)
    student_action: str = Field(min_length=3, max_length=1_200)
    organization: str = Field(min_length=1, max_length=160)
    expected_output: str = Field(min_length=2, max_length=600)
    assessment_method: str = Field(min_length=2, max_length=500)
    decision_rule: str = Field(min_length=2, max_length=500)


class GeneratedBoard(StrictModel):
    layout: dict[str, str] = Field(min_length=1, max_length=6)
    timeline: list[str] = Field(min_length=1, max_length=20)
    persistent_content: list[str] = Field(min_length=1, max_length=20)
    slide_only_content: list[str] = Field(default_factory=list, max_length=20)
    compact_version: list[str] = Field(min_length=1, max_length=20)
    estimated_writing_minutes: int = Field(ge=1, le=30)


class GeneratedAssessment(StrictModel):
    objective_indexes: list[int] = Field(min_length=1, max_length=8)
    purpose: Literal["in_class_check", "homework"]
    prompt: str = Field(min_length=4, max_length=2_000)
    answer_outline: str = Field(min_length=2, max_length=2_000)
    scoring_rubric: list[str] = Field(min_length=1, max_length=12)
    difficulty: float = Field(ge=0.1, le=0.95)
    knowledge_tags: list[str] = Field(min_length=1, max_length=10)
    ability_tags: list[str] = Field(min_length=1, max_length=10)
    common_error_tags: list[str] = Field(default_factory=list, max_length=10)
    decision_rule: str = Field(default="", max_length=500)


class GeneratedDifferentiation(StrictModel):
    layer_id: Literal["support", "core", "advanced"]
    target_profile: str = Field(min_length=2, max_length=300)
    task_adjustment: str = Field(min_length=3, max_length=800)
    scaffolds: list[str] = Field(default_factory=list, max_length=10)
    objective_indexes: list[int] = Field(min_length=1, max_length=8)


class GeneratedLessonContent(StrictModel):
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=5, max_length=3_000)
    key_points: list[str] = Field(min_length=1, max_length=20)
    difficult_points: list[str] = Field(min_length=1, max_length=20)
    objectives: list[GeneratedObjective] = Field(min_length=2, max_length=8)
    activities: list[GeneratedActivity] = Field(min_length=3, max_length=16)
    board_plan: GeneratedBoard
    assessments: list[GeneratedAssessment] = Field(min_length=2, max_length=16)
    differentiation_plan: list[GeneratedDifferentiation] = Field(min_length=3, max_length=3)
    contingency_paths: list[str] = Field(min_length=1, max_length=10)

    @field_validator("differentiation_plan")
    @classmethod
    def require_all_layers(
        cls, layers: list[GeneratedDifferentiation]
    ) -> list[GeneratedDifferentiation]:
        if {item.layer_id for item in layers} != {"support", "core", "advanced"}:
            raise ValueError("必须同时生成支持、核心和拓展三层动态任务")
        return layers


class StructuredTeacherPreparationGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            TEACHER_PREPARATION_PROMPT
            | model.with_structured_output(GeneratedLessonContent, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(
        self,
        *,
        teaching_context: dict,
        diagnosis_summary: dict,
        resource_references: list[dict],
        revision_context: dict | None = None,
    ) -> GeneratedLessonContent | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {
                "teaching_context": json.dumps(teaching_context, ensure_ascii=False, default=str),
                "diagnosis_summary": json.dumps(diagnosis_summary, ensure_ascii=False, default=str),
                "resource_references": json.dumps(
                    resource_references, ensure_ascii=False, default=str
                ),
                "revision_context": json.dumps(
                    revision_context or {}, ensure_ascii=False, default=str
                ),
            }
        )
