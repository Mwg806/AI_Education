"""LLM boundary for diagnosis narratives; structured state stays deterministic."""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.learning_diagnosis import DIAGNOSIS_REPORT_PROMPT


class DiagnosisNarrative(StrictModel):
    student_summary: str = Field(min_length=120, max_length=5_000)
    teacher_summary: str = Field(min_length=100, max_length=6_000)
    evidence_boundary: str = Field(min_length=40, max_length=2_000)
    next_evidence_request: str = Field(min_length=40, max_length=2_000)


class StructuredDiagnosisReporter:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            DIAGNOSIS_REPORT_PROMPT
            | model.with_structured_output(DiagnosisNarrative, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, diagnosis_context: dict[str, Any]) -> DiagnosisNarrative | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke({
            "diagnosis_context": json.dumps(diagnosis_context, ensure_ascii=False, default=str)
        })
