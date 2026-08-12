"""Structured LLM boundary for natural career-skills conversations."""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.career_education import (
    CAREER_MENTOR_PROMPT,
    GAOKAO_PROGRAMMING_FEEDBACK_PROMPT,
    PROJECT_MENTOR_PROMPT,
)


class GeneratedCareerTask(StrictModel):
    task: str = Field(min_length=2, max_length=500)
    estimated_minutes: int = Field(ge=10, le=480)
    acceptance: str = Field(min_length=2, max_length=600)


class GeneratedCareerWeek(StrictModel):
    week: int = Field(ge=1, le=2)
    focus: str = Field(min_length=2, max_length=300)
    estimated_hours: int = Field(ge=1, le=40)


class GeneratedCareerReply(StrictModel):
    analysis: str = Field(min_length=2, max_length=1_500)
    answer: str = Field(min_length=5, max_length=8_000)
    task_breakdown: list[GeneratedCareerTask] = Field(default_factory=list, max_length=4)
    two_week_route: list[GeneratedCareerWeek] = Field(default_factory=list, max_length=2)
    recommended_mode: Literal["CAREER", "PROJECT", "CODING"] = "CAREER"
    follow_up_question: str = Field(default="", max_length=1_000)


class StructuredCareerMentorGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            CAREER_MENTOR_PROMPT
            | model.with_structured_output(GeneratedCareerReply, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, context: dict[str, Any]) -> GeneratedCareerReply | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {
                "target_job": json.dumps(context["target_job"], ensure_ascii=False),
                "learner_profile": json.dumps(
                    context["learner_profile"], ensure_ascii=False, default=str
                ),
                "skill_evidence": json.dumps(
                    context["skill_evidence"], ensure_ascii=False, default=str
                ),
                "recent_activity": json.dumps(
                    context["recent_activity"], ensure_ascii=False, default=str
                ),
                "conversation_history": json.dumps(
                    context["conversation_history"], ensure_ascii=False, default=str
                ),
                "user_message": context["user_message"],
            }
        )


class GeneratedProjectReply(StrictModel):
    answer: str = Field(min_length=5, max_length=8_000)
    guiding_questions: list[str] = Field(default_factory=list, max_length=4)
    suggested_actions: list[str] = Field(default_factory=list, max_length=4)
    follow_up_question: str = Field(default="", max_length=1_000)


class StructuredProjectMentorGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            PROJECT_MENTOR_PROMPT
            | model.with_structured_output(GeneratedProjectReply, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, context: dict[str, Any]) -> GeneratedProjectReply | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {
                "learner_profile": json.dumps(
                    context["learner_profile"], ensure_ascii=False, default=str
                ),
                "project_context": json.dumps(
                    context["project_context"], ensure_ascii=False, default=str
                ),
                "conversation_history": json.dumps(
                    context["conversation_history"], ensure_ascii=False, default=str
                ),
                "user_message": context["user_message"],
            }
        )


class GeneratedGaokaoProgrammingFeedback(StrictModel):
    score: float = Field(ge=0, le=100)
    diagnosis: str = Field(min_length=5, max_length=2000)
    strengths: list[str] = Field(default_factory=list, max_length=4)
    issues: list[str] = Field(default_factory=list, max_length=5)
    hints: list[str] = Field(default_factory=list, max_length=4)
    next_step: str = Field(min_length=2, max_length=600)


class StructuredGaokaoProgrammingGrader:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.structured_model = (
            model.with_structured_output(
                GeneratedGaokaoProgrammingFeedback,
                method="function_calling",
            )
            if model is not None
            else None
        )
        self.chain = (
            GAOKAO_PROGRAMMING_FEEDBACK_PROMPT | self.structured_model
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def grade(
        self,
        context: dict[str, Any],
        *,
        image_data_urls: list[str] | None = None,
    ) -> GeneratedGaokaoProgrammingFeedback | None:
        if self.chain is None:
            return None
        variables = {
            "question": json.dumps(context["question"], ensure_ascii=False, default=str),
            "max_score": context["max_score"],
            "standard_answer": context["standard_answer"],
            "official_analysis": context["official_analysis"],
            "student_answer": context["student_answer"],
            "learner_profile": json.dumps(
                context["learner_profile"], ensure_ascii=False, default=str
            ),
        }
        if not image_data_urls:
            return await self.chain.ainvoke(variables)

        messages = GAOKAO_PROGRAMMING_FEEDBACK_PROMPT.format_messages(**variables)
        human_text = str(messages[-1].content)
        blocks: list[dict[str, Any]] = [{"type": "text", "text": human_text}]
        blocks.extend(
            {
                "type": "image_url",
                "image_url": {"url": data_url, "detail": "high"},
            }
            for data_url in image_data_urls[:3]
        )
        messages[-1] = HumanMessage(content=blocks)
        result = await self.structured_model.ainvoke(messages)
        if isinstance(result, GeneratedGaokaoProgrammingFeedback):
            return result
        return GeneratedGaokaoProgrammingFeedback.model_validate(
            json.loads(result) if isinstance(result, str) else result
        )
