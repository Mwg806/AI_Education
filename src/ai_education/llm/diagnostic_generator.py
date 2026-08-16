"""Structured gpt-5.5 generation for ten-item quick diagnostics."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.diagnostic import QUICK_DIAGNOSTIC_PROMPT

DiagnosticDimension = Literal[
    "prerequisite",
    "concept",
    "basic_application",
    "integrated_application",
    "transfer",
]


class DiagnosticQuestionDraft(StrictModel):
    slot_id: str = Field(min_length=3, max_length=32)
    knowledge_focus: str = Field(min_length=1, max_length=160)
    scope_id: str = Field(min_length=1, max_length=300)
    scope_label: str = Field(min_length=1, max_length=160)
    source_chunk_id: str = Field(min_length=3, max_length=180)
    source_excerpt: str = Field(min_length=8, max_length=500)
    dimension: DiagnosticDimension
    difficulty: float = Field(ge=0.2, le=0.85)
    prompt: str = Field(min_length=5, max_length=2_000)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=1, max_length=1_500)
    expected_seconds: int = Field(ge=20, le=900)

    @field_validator("options")
    @classmethod
    def options_must_be_unique(cls, options: list[str]) -> list[str]:
        if len({item.strip() for item in options}) != 4:
            raise ValueError("诊断题四个选项必须互不相同")
        return options


class DiagnosticQuestionSet(StrictModel):
    questions: list[DiagnosticQuestionDraft] = Field(min_length=10, max_length=10)

    @field_validator("questions")
    @classmethod
    def dimensions_must_be_balanced(
        cls, questions: list[DiagnosticQuestionDraft]
    ) -> list[DiagnosticQuestionDraft]:
        dimensions = {dimension: 0 for dimension in DiagnosticDimension.__args__}
        for question in questions:
            dimensions[question.dimension] += 1
        if any(count != 2 for count in dimensions.values()):
            raise ValueError("五个诊断维度必须各包含两题")
        slot_ids = [question.slot_id for question in questions]
        if len(set(slot_ids)) != 10:
            raise ValueError("十道诊断题必须分别对应十个唯一命题槽位")
        return questions


class StructuredDiagnosticGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            QUICK_DIAGNOSTIC_PROMPT
            | model.with_structured_output(DiagnosticQuestionSet, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, context: dict[str, Any]) -> DiagnosticQuestionSet | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(context)
