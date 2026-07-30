"""Deterministic pedagogy and answer-leakage guards."""

from __future__ import annotations

import json
import re
from typing import Any

from ai_education.domain.homework import GuardResult

FINAL_ANSWER_PATTERNS = (
    r"答案(?:为|是|：)",
    r"最终(?:答案|结果|选项)(?:为|是|：)",
    r"故选\s*[A-D]",
    r"完整(?:解答|解题过程|范文|代码)",
)


class HomeworkOutputGuard:
    def inspect(
        self,
        candidate: dict[str, Any],
        *,
        completed_attempt: bool,
        cumulative_budget: float,
    ) -> GuardResult:
        visible = candidate.get("student_visible_content", {})
        serialized = json.dumps(visible, ensure_ascii=False)
        risks: list[str] = []
        direct_hits = sum(
            bool(re.search(pattern, serialized, re.I)) for pattern in FINAL_ANSWER_PATTERNS
        )
        if direct_hits and not completed_attempt:
            risks.append("direct_final_answer")
        equation_chain = len(re.findall(r"(?:=|⇒|所以|因此)", serialized))
        if equation_chain >= 5 and not completed_attempt:
            risks.append("complete_reasoning_chain")
        if len(serialized) > 1600 and not completed_attempt:
            risks.append("copyable_long_form")
        if "answer_vault" in serialized or "solution_steps" in serialized:
            risks.append("internal_channel_exposure")
        if cumulative_budget >= 0.78:
            risks.append("cumulative_leakage_budget")
        risk = min(
            1.0,
            direct_hits * 0.45
            + max(equation_chain - 3, 0) * 0.08
            + (0.3 if "copyable_long_form" in risks else 0)
            + (0.8 if "internal_channel_exposure" in risks else 0)
            + (0.35 if "cumulative_leakage_budget" in risks else 0),
        )
        return GuardResult(passed=not risks, risk_score=round(risk, 3), risk_types=risks)

    def sanitize(self, candidate: dict[str, Any], risks: list[str]) -> dict[str, Any]:
        return {
            **candidate,
            "action": "request_student_attempt",
            "student_visible_content": {
                "acknowledgement": "我会继续帮助你，但不能替你直接完成作业。",
                "guidance": "请先写出你已经确认的一个条件、一个目标量或第一步思路。",
                "question_to_student": "你准备先处理哪一个已知条件？",
                "warning": "本轮提示已因答案泄露风险自动收敛。",
            },
            "guard_repair": {"risk_types": risks},
        }
