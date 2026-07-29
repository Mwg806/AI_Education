"""Structured LangChain goal interpreter guarded by deterministic validation."""

from __future__ import annotations

from datetime import date
from typing import Any

from ai_education.domain.models import GoalParseResult
from ai_education.prompts.planner import GOAL_PARSE_PROMPT


class StructuredGoalInterpreter:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            GOAL_PARSE_PROMPT | model.with_structured_output(GoalParseResult)
            if model is not None
            else None
        )

    async def parse(
        self,
        goal_text: str,
        *,
        grade: str,
        exam_profile_id: str,
    ) -> GoalParseResult | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {
                "current_date": date.today().isoformat(),
                "grade": grade,
                "exam_profile_id": exam_profile_id,
                "goal_text": goal_text,
            }
        )
