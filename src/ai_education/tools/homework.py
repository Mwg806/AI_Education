"""LangChain tools exposed by HomeworkTutoringAgent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ai_education.domain.enums import Subject
from ai_education.services.homework_guard import HomeworkOutputGuard
from ai_education.services.question_bank import QuestionBankService


class QuestionBankSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    subject: Subject | None = None
    province: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class LeakageGuardInput(BaseModel):
    candidate: dict[str, Any]
    completed_attempt: bool = False
    cumulative_budget: float = Field(default=0, ge=0, le=1)


HOMEWORK_TOOL_MANIFEST = (
    "student_profile_get",
    "exam_policy_resolve",
    "knowledge_graph_match",
    "rubric_get",
    "image_quality_assess",
    "document_layout_detect",
    "printed_text_ocr",
    "handwriting_ocr",
    "formula_recognize",
    "diagram_understand",
    "question_bank_search",
    "variant_validate",
    "answer_vault_store",
    "answer_vault_compare",
    "answer_leakage_guard",
    "knowledge_evidence_publish",
    "planner_adjustment_publish",
    "audit_log_write",
)


class HomeworkToolbox:
    def __init__(self, question_bank: QuestionBankService, guard: HomeworkOutputGuard) -> None:
        self.question_bank = question_bank
        self.guard = guard

    def as_langchain_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                name="question_bank_search",
                description="检索本地 2026 五三 A/B 版题库元数据；学生端不返回答案资料正文",
                args_schema=QuestionBankSearchInput,
                func=lambda query, subject=None, province=None, limit=5: [
                    item.model_dump(mode="json")
                    for item in self.question_bank.search(
                        query,
                        subject=Subject(subject) if subject else None,
                        province=province,
                        limit=limit,
                    )
                ],
            ),
            StructuredTool.from_function(
                name="answer_leakage_guard",
                description="在学生可见响应前检测最终答案、完整推导和内部通道泄露",
                args_schema=LeakageGuardInput,
                func=lambda candidate, completed_attempt=False, cumulative_budget=0: (
                    self.guard.inspect(
                        candidate,
                        completed_attempt=completed_attempt,
                        cumulative_budget=cumulative_budget,
                    ).model_dump(mode="json")
                ),
            ),
        ]

    def capability_manifest(self) -> dict[str, str]:
        implemented = {tool.name for tool in self.as_langchain_tools()}
        implemented.update(
            {"image_quality_assess", "printed_text_ocr", "answer_vault_store", "audit_log_write"}
        )
        return {
            name: "implemented" if name in implemented else "adapter_reserved"
            for name in HOMEWORK_TOOL_MANIFEST
        }
