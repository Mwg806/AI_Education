"""Structured model boundary for evidence-grounded English reading tasks."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.english_learning import ENGLISH_READING_TRAINING_PROMPT

ReadingSkill = Literal[
    "DETAIL_LOCATION",
    "MAIN_IDEA",
    "INFERENCE",
    "AUTHOR_ATTITUDE",
    "WORD_MEANING_IN_CONTEXT",
    "REFERENCE_RESOLUTION",
    "TEXT_STRUCTURE",
    "SEVEN_OF_FIVE_COHESION",
]


class GeneratedEnglishQuestion(StrictModel):
    stem: str = Field(min_length=5, max_length=800)
    skill: ReadingSkill
    options: list[str] = Field(min_length=4, max_length=7)
    correct_option: int = Field(ge=0, le=6)
    evidence_quote: str = Field(min_length=3, max_length=1_500)
    reasoning: str = Field(min_length=5, max_length=1_500)
    distractor_mechanisms: list[str] = Field(min_length=4, max_length=7)

    @model_validator(mode="after")
    def validate_options(self) -> GeneratedEnglishQuestion:
        if len({item.strip().lower() for item in self.options}) != len(self.options):
            raise ValueError("题目选项必须互不相同")
        if self.correct_option >= len(self.options):
            raise ValueError("正确选项超出选项范围")
        if len(self.distractor_mechanisms) != len(self.options):
            raise ValueError("每个选项都必须有质量标记")
        return self


class GeneratedEnglishTraining(StrictModel):
    display_text: str = Field(min_length=40, max_length=15_000)
    questions: list[GeneratedEnglishQuestion] = Field(min_length=3, max_length=6)

    @field_validator("questions")
    @classmethod
    def require_skill_coverage(
        cls, questions: list[GeneratedEnglishQuestion]
    ) -> list[GeneratedEnglishQuestion]:
        skills = {item.skill for item in questions}
        if len(questions) >= 4 and skills != {"SEVEN_OF_FIVE_COHESION"} and len(skills) < 2:
            raise ValueError("阅读训练至少覆盖两种能力")
        return questions


class StructuredEnglishTrainingGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            ENGLISH_READING_TRAINING_PROMPT
            | model.with_structured_output(
                GeneratedEnglishTraining,
                method="function_calling",
            )
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, context: dict[str, Any]) -> GeneratedEnglishTraining | None:
        if self.chain is None:
            return None
        return await self.chain.ainvoke(
            {
                **context,
                "exam_profile": json.dumps(
                    context["exam_profile"], ensure_ascii=False, default=str
                ),
                "knowledge_references": json.dumps(
                    context["knowledge_references"], ensure_ascii=False, default=str
                ),
            }
        )
