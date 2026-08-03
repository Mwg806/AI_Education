"""Structured LLM explanations for validated learning plans."""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.planner import PLAN_EXPLANATION_PROMPT


class PlanTaskNarrative(StrictModel):
    task_id: str
    rationale: str = Field(min_length=1, max_length=1_200)


class PlanNarrative(StrictModel):
    student: str = Field(min_length=1, max_length=5_000)
    teacher: str = Field(min_length=1, max_length=6_000)
    strategy: str = Field(min_length=1, max_length=2_000)
    task_rationales: list[PlanTaskNarrative] = Field(default_factory=list)


class StructuredPlanNarrator:
    """Explain, but never mutate, the deterministic and validated plan."""

    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            PLAN_EXPLANATION_PROMPT
            | model.with_structured_output(PlanNarrative, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def explain(self, plan_context: dict[str, Any]) -> PlanNarrative | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {"plan_context": json.dumps(plan_context, ensure_ascii=False, default=str)}
        )
