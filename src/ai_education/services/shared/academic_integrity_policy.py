"""Deterministic academic-integrity boundary for the collaboration workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AcademicIntegrityDecision:
    blocked: bool
    code: str
    message: str


class AcademicIntegrityPolicy:
    """Allow evaluation and hints while blocking copyable schoolwork completion."""

    _completion_patterns = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"(?:直接|只|就)?(?:给|告诉|发)(?:我)?.{0,24}(?:最终|完整|标准)?答案",
            r"(?:帮|替)(?:我)?(?:把)?(?:这|这份|全部)?(?:作业|题目|试卷|作文|报告)(?:写|做|完成|答)(?:完|了)?",
            r"(?:代写|代做|替写|替做)",
            r"(?:帮|替)(?:我)?(?:写|做|完成|回答|解决|解答|解).{0,24}(?:作业|题目|题|试卷|作文|报告|代码|问题)",
            r"生成(?:一份)?(?:可以|能)?直接(?:提交|上交)(?:的)?(?:作业|答案|作文|报告|代码)",
            r"(?:完整解答|完整解题过程|完整答案|完整作文|完整报告|可提交代码)",
            r"不要(?:解释|过程|思路)[，, ]*(?:只|直接)?(?:给|告诉)(?:我)?答案",
        )
    )
    _judgment_patterns = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"(?:判断|检查|批改|评估|分析)(?:一下)?(?:我)?(?:的)?(?:答案|作答|步骤|思路|代码|作文)",
            r"(?:我写的|我的作答|我的答案|以下是我的|这是我写的).*(?:对不对|哪里错|是否正确|帮我看)",
        )
    )

    def inspect(self, message: str) -> AcademicIntegrityDecision:
        normalized = " ".join(message.strip().split())
        asks_completion = any(pattern.search(normalized) for pattern in self._completion_patterns)
        asks_judgment = any(pattern.search(normalized) for pattern in self._judgment_patterns)
        if asks_completion:
            suffix = (
                "你已经提供了自己的作答，我可以继续判断哪里正确、哪里需要修改，"
                if asks_judgment
                else "请先提交你自己的答案、步骤或思路，我可以继续判断哪里正确、哪里需要修改，"
            )
            return AcademicIntegrityDecision(
                blocked=True,
                code="HOMEWORK_COMPLETION_PROHIBITED",
                message=(
                    "智能协作只能帮助你判断、诊断和理解，不能替你完成作业，也不能提供可直接提交的答案。"
                    + suffix
                    + "并给出不泄露最终答案的渐进提示。"
                ),
            )
        return AcademicIntegrityDecision(
            blocked=False,
            code="JUDGMENT_ASSISTANCE_ALLOWED",
            message="允许进行作答判断、错误诊断、思路解释和渐进提示。",
        )

    @staticmethod
    def execution_context() -> dict[str, object]:
        return {
            "mode": "judgment_only",
            "allowed": [
                "evaluate_student_attempt",
                "diagnose_misconception",
                "explain_concepts",
                "give_progressive_hint",
            ],
            "prohibited": [
                "provide_final_answer",
                "complete_homework",
                "write_submission_for_student",
            ],
            "student_attempt_required_before_specific_feedback": True,
        }
