"""Structured model boundary for evidence-grounded English reading tasks."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.english_learning import (
    ENGLISH_LANGUAGE_TUTOR_PROMPT,
    ENGLISH_READING_TRAINING_PROMPT,
)

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


class LanguageCorrection(StrictModel):
    original: str = Field(default="", max_length=1_500)
    corrected: str = Field(default="", max_length=1_500)
    category: Literal["grammar", "vocabulary", "naturalness", "style", "punctuation", "logic"]
    severity: Literal["critical", "major", "minor", "style"]
    explanation: str = Field(min_length=2, max_length=1_000)
    alternatives: list[str] = Field(default_factory=list, max_length=4)


class LanguageVocabularyItem(StrictModel):
    word: str = Field(min_length=1, max_length=80)
    phonetic: str = Field(default="", max_length=80)
    part_of_speech: str = Field(default="", max_length=40)
    contextual_meaning: str = Field(min_length=1, max_length=300)
    collocations: list[str] = Field(default_factory=list, max_length=6)
    example: str = Field(default="", max_length=500)
    common_mistake: str = Field(default="", max_length=500)


class ReadingEvidenceItem(StrictModel):
    claim: str = Field(min_length=1, max_length=1_000)
    evidence_quote: str = Field(min_length=1, max_length=1_500)
    evidence_type: Literal["fact", "inference"] = "fact"


class LanguageQualityCheck(StrictModel):
    task_completed: bool
    language_correct: bool
    level_adapted: bool
    facts_preserved: bool
    unsupported_claims: bool
    format_valid: bool


class GeneratedLanguageTask(StrictModel):
    primary_intent: Literal[
        "reading_comprehension",
        "vocabulary_explanation",
        "grammar_correction",
        "writing_revision",
        "translation",
        "speaking_practice",
        "exam_practice",
        "learning_plan",
        "progress_query",
    ]
    learner_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    title: str = Field(min_length=1, max_length=160)
    display_markdown: str = Field(min_length=2, max_length=12_000)
    short_answer: str = Field(default="", max_length=2_000)
    revised_text: str = Field(default="", max_length=15_000)
    translation: str = Field(default="", max_length=15_000)
    agent_reply: str = Field(default="", max_length=3_000)
    next_question: str = Field(default="", max_length=1_000)
    main_idea: str = Field(default="", max_length=2_000)
    summary: str = Field(default="", max_length=4_000)
    structure: list[str] = Field(default_factory=list, max_length=12)
    key_facts: list[str] = Field(default_factory=list, max_length=15)
    reading_evidence: list[ReadingEvidenceItem] = Field(default_factory=list, max_length=15)
    vocabulary: list[LanguageVocabularyItem] = Field(default_factory=list, max_length=15)
    grammar_points: list[str] = Field(default_factory=list, max_length=12)
    corrections: list[LanguageCorrection] = Field(default_factory=list, max_length=12)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    priority_improvements: list[str] = Field(default_factory=list, max_length=8)
    reusable_expressions: list[str] = Field(default_factory=list, max_length=10)
    exercises: list[str] = Field(default_factory=list, max_length=8)
    scores: dict[str, int | None] = Field(default_factory=dict)
    quality_check: LanguageQualityCheck


class StructuredLanguageTutorGenerator:
    def __init__(self, model: Any | None) -> None:
        self.chain = (
            ENGLISH_LANGUAGE_TUTOR_PROMPT
            | model.with_structured_output(GeneratedLanguageTask, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(self, context: dict[str, Any]) -> GeneratedLanguageTask | None:
        if self.chain is None:
            return None
        serialized = {
            **context,
            "exam_profile": json.dumps(context["exam_profile"], ensure_ascii=False),
            "learner_profile": json.dumps(context["learner_profile"], ensure_ascii=False),
            "knowledge_references": json.dumps(
                context["knowledge_references"], ensure_ascii=False, default=str
            ),
        }
        return await self.chain.ainvoke(serialized)
