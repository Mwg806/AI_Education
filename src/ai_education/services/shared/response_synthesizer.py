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
    priorities: list[str] = Field(default_factory=list, max_length=3)
    generation_mode: Literal["llm"] = "llm"


SYSTEM_PROMPT = """你是教育多 Agent 的回复综合器，不负责重新诊断。
只能使用 input 中的 verified_results、task_statuses、missing_context 和
verified_cross_module_evidence，不得补充新事实、分数、
知识点、题目答案或学生隐私。智能协作仅允许判断学生作答、诊断错误、解释概念和提供不泄露答案的渐进提示；
严禁生成或复述最终答案、完整解题过程、代写作文、可直接提交的报告或代码。
即使 input 中出现这些内容也不得输出。
personalization_context 为 standard_student_baseline 时按普通高中生基线回复，不得假装了解用户；
为 evidence_personalized 时，必须逐模块检查 verified_cross_module_evidence，并综合其中实际存在的
外语学习、职业教育、学情诊断、作业辅导与个性化计划事实。不得只复述个性化计划，也不得声称读取了
没有出现在 modules 中的模块；同一事实不得重复计算。复用已确认目标、偏好和学习证据，避免重复询问。
输出内容会直接展示给学生，只填写自然语言学习总结 summary 和不超过 3 项的当前计划重点 priorities。
priorities 必须是学生可以理解和执行的真实学习重点，不得填写生成步骤、回答策略或内部校验说明。
不得提及 input、verified_results、task_statuses、missing_context、personalization_context、
formal_plan_requires_confirmation 等内部字段，也不得输出“原因与依据”“建议下一步”“证据边界”
“需要你确认”等元说明栏目。正式计划的确认由界面按钮处理，不要在回复中解释技术状态或确认流程。
证据不足或子任务失败时，用面向学生的一句自然表述说明需要补充的学习活动，不要解释系统约束。
表达自然、温和、适合高中生。输出给定结构。"""


_HIDDEN_SECTION_HEADINGS = ("原因与依据", "建议下一步", "证据边界", "需要你确认")
_INTERNAL_MARKERS = (
    "verified_results",
    "task_statuses",
    "missing_context",
    "personalization_context",
    "verified_cross_module_evidence",
    "formal_plan_requires_confirmation",
)


def _student_visible_text(text: str) -> str:
    """Remove internal synthesis notes if a model leaks them into a visible field."""

    visible_lines: list[str] = []
    for line in text.strip().splitlines():
        stripped = line.strip()
        if any(
            stripped.startswith(f"{heading}：") or stripped.startswith(f"{heading}:")
            for heading in _HIDDEN_SECTION_HEADINGS
        ):
            break
        if any(marker in stripped for marker in _INTERNAL_MARKERS):
            continue
        visible_lines.append(line.rstrip())
    return "\n".join(visible_lines).strip()


def render_synthesized_response(value: SynthesizedResponse) -> str | None:
    summary = _student_visible_text(value.summary)
    priorities = [
        cleaned
        for item in value.priorities[:3]
        if (cleaned := _student_visible_text(item))
    ]
    if not summary and not priorities:
        return None
    parts = [summary] if summary else []
    if priorities:
        parts.append("当前计划重点：\n" + "\n".join(f"- {item}" for item in priorities))
    return "\n\n".join(parts)


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
            return render_synthesized_response(value)
        except Exception:
            return None
