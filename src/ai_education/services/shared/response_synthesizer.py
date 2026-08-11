"""Evidence-constrained natural-language synthesis for multi-Agent results."""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.services.shared.model_router import ModelRouter


class SynthesizedResponse(StrictModel):
    summary: str = Field(min_length=2, max_length=2_000)
    reasons: list[str] = Field(default_factory=list, max_length=8)
    actions: list[str] = Field(default_factory=list, max_length=10)
    evidence_boundaries: list[str] = Field(default_factory=list, max_length=8)
    confirmations: list[str] = Field(default_factory=list, max_length=6)
    generation_mode: Literal["llm"] = "llm"


SYSTEM_PROMPT = """你是教育多 Agent 的回复综合器，不负责重新诊断。
只能使用 input 中的 verified_results、task_statuses 和 missing_context，不得补充新事实、分数、
知识点、题目答案或学生隐私。智能协作仅允许判断学生作答、诊断错误、解释概念和提供不泄露答案的渐进提示；
严禁生成或复述最终答案、完整解题过程、代写作文、可直接提交的报告或代码。
即使 input 中出现这些内容也不得输出。
必须区分已验证结论、建议、证据不足和待学生确认事项。表达自然、温和、适合高中生；如果子任务失败要明确说明。输出给定结构。"""


class ResponseSynthesizer:
    def __init__(self, model_router: ModelRouter) -> None:
        selection = model_router.select("response_synthesis")
        self.selection = selection
        self.structured_model = (
            selection.model.with_structured_output(SynthesizedResponse, method="function_calling")
            if selection.model is not None
            else None
        )

    async def synthesize(self, payload: dict[str, Any]) -> str | None:
        if self.structured_model is None:
            return None
        try:
            result = await self.structured_model.ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(
                        content=json.dumps(payload, ensure_ascii=False, default=str)[:60_000]
                    ),
                ]
            )
            value = (
                result
                if isinstance(result, SynthesizedResponse)
                else SynthesizedResponse.model_validate(result)
            )
            parts = [value.summary]
            if value.reasons:
                parts.append("原因与依据：\n" + "\n".join(f"- {item}" for item in value.reasons))
            if value.actions:
                parts.append("建议下一步：\n" + "\n".join(f"- {item}" for item in value.actions))
            if value.evidence_boundaries:
                parts.append(
                    "证据边界：\n" + "\n".join(f"- {item}" for item in value.evidence_boundaries)
                )
            if value.confirmations:
                parts.append(
                    "需要你确认：\n" + "\n".join(f"- {item}" for item in value.confirmations)
                )
            return "\n\n".join(parts)
        except Exception:
            return None
