"""Structured multimodal LangChain generation for homework tutoring."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from ai_education.domain.protocols import StrictModel
from ai_education.prompts.homework import (
    HOMEWORK_RESPONSE_TASK_V2,
    HOMEWORK_TUTOR_GLOBAL_SYSTEM_V2,
)


class VisibleTutoringContent(StrictModel):
    acknowledgement: str = Field(max_length=600)
    guidance: str = Field(max_length=4_000)
    question_to_student: str = Field(default="", max_length=600)
    warning: str = Field(default="", max_length=600)


class TutorCandidate(StrictModel):
    action: str
    student_visible_content: VisibleTutoringContent
    pedagogical_metadata: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    variant_package: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.8, ge=0, le=1)


class StructuredHomeworkTutor:
    def __init__(self, model: Any | None, *, provider: str = "openai") -> None:
        self.model = model
        self.provider = provider
        self.structured_model = (
            model.with_structured_output(TutorCandidate, method="function_calling")
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.structured_model is not None

    async def generate(
        self,
        payload: dict[str, Any],
        *,
        image_data_urls: list[str] | None = None,
    ) -> TutorCandidate | None:
        if self.structured_model is None:
            return None
        prompt = HOMEWORK_RESPONSE_TASK_V2.format(**payload)
        content: str | list[dict[str, Any]] = prompt
        if image_data_urls:
            blocks: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for data_url in image_data_urls[:3]:
                if self.provider == "anthropic":
                    header, encoded = data_url.split(",", 1)
                    media_type = header.split(";", 1)[0].split(":", 1)[1]
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded,
                            },
                        }
                    )
                else:
                    blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "auto"},
                        }
                    )
            content = blocks
        result = await self.structured_model.ainvoke(
            [
                SystemMessage(content=HOMEWORK_TUTOR_GLOBAL_SYSTEM_V2),
                HumanMessage(content=content),
            ]
        )
        if isinstance(result, TutorCandidate):
            return result
        return TutorCandidate.model_validate(
            json.loads(result) if isinstance(result, str) else result
        )
