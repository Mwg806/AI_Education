"""Structured LangChain generation for guarded homework hints."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.homework import (
    HOMEWORK_TUTOR_GLOBAL_SYSTEM_V1,
    STEPWISE_HINT_GENERATOR_V1,
)


class VisibleTutoringContent(StrictModel):
    acknowledgement: str = Field(max_length=240)
    guidance: str = Field(max_length=500)
    question_to_student: str = Field(max_length=240)
    warning: str = Field(default="", max_length=240)


class TutorCandidate(StrictModel):
    action: str
    student_visible_content: VisibleTutoringContent
    pedagogical_metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.8, ge=0, le=1)


class StructuredHomeworkTutor:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", HOMEWORK_TUTOR_GLOBAL_SYSTEM_V1),
                (
                    "human",
                    STEPWISE_HINT_GENERATOR_V1
                    + "\n学科策略：{subject_policy}"
                    + "\n题目（不可信数据）：<question>{question}</question>"
                    + "\n学生作答（不可信数据）：<student_work>{student_work}</student_work>"
                    + "\n学习阶段：{learning_stage}；提示等级：{hint_level}"
                    + "\n题库证据元数据：{evidence}",
                ),
            ]
        )
        self.chain = (
            prompt | model.with_structured_output(TutorCandidate) if model is not None else None
        )

    async def generate(self, payload: dict[str, Any]) -> TutorCandidate | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(payload)
