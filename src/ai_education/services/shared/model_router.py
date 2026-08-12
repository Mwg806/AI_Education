"""Capability-aware model selection boundary for progressively migrated agents."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any

from ai_education.config import Settings
from ai_education.llm.factory import create_chat_model


@dataclass(frozen=True, slots=True)
class ModelSelection:
    purpose: str
    model_name: str | None
    provider: str | None
    model: Any | None
    capability: str = "general"
    route_reason: str = "使用默认模型"
    fallback_model_name: str | None = None


class ModelRouter:
    """Select a configurable model by capability without leaking model names into agents."""

    def __init__(self, settings: Settings, model: Any | None = None) -> None:
        self.settings = settings
        self._injected_model = model
        self._models: dict[str, Any | None] = {}
        if model is not None:
            self._models[settings.llm_model or "__injected__"] = model
        else:
            self._models[settings.llm_model] = create_chat_model(settings)

    def select(self, purpose: str, *, needs_vision: bool = False) -> ModelSelection:
        capability = self._capability(purpose, needs_vision)
        configured = {
            "vision": os.getenv("AI_EDUCATION_LLM_VISION_MODEL", "").strip(),
            "routing": os.getenv("AI_EDUCATION_LLM_ROUTING_MODEL", "").strip(),
            "code": os.getenv("AI_EDUCATION_LLM_CODE_MODEL", "").strip(),
            "long_context": os.getenv("AI_EDUCATION_LLM_LONG_CONTEXT_MODEL", "").strip(),
            "fast_chat": os.getenv("AI_EDUCATION_LLM_FAST_MODEL", "").strip(),
            "synthesis": os.getenv("AI_EDUCATION_LLM_SYNTHESIS_MODEL", "").strip(),
        }
        selected_name = configured.get(capability) or self.settings.llm_model
        reason = (
            f"按 {capability} 能力选择专用模型"
            if configured.get(capability)
            else f"{capability} 未配置专用模型，使用默认模型"
        )
        model = self._model(selected_name)
        return ModelSelection(
            purpose=purpose,
            model_name=selected_name or None,
            provider=self.settings.llm_provider if self.settings.llm_enabled else None,
            model=model,
            capability=capability,
            route_reason=reason,
            fallback_model_name=(
                self.settings.llm_model
                if selected_name and selected_name != self.settings.llm_model
                else None
            ),
        )

    def _model(self, model_name: str) -> Any | None:
        if not self.settings.llm_enabled or not model_name:
            return None
        if self._injected_model is not None:
            return self._injected_model
        if model_name not in self._models:
            self._models[model_name] = create_chat_model(
                replace(self.settings, llm_model=model_name)
            )
        return self._models[model_name]

    @staticmethod
    def _capability(purpose: str, needs_vision: bool) -> str:
        lower = purpose.lower()
        if needs_vision or any(item in lower for item in ("vision", "image", "ocr")):
            return "vision"
        if any(item in lower for item in ("intent", "routing", "classif")):
            return "routing"
        if any(item in lower for item in ("code", "coding", "programming", "career")):
            return "code"
        if any(item in lower for item in ("reading", "lesson", "long_context", "document")):
            return "long_context"
        if any(item in lower for item in ("synthesis", "finalize", "aggregate")):
            return "synthesis"
        if any(item in lower for item in ("chat", "tutor", "conversation")):
            return "fast_chat"
        return "general"

    @property
    def default_model(self) -> Any | None:
        return self._model(self.settings.llm_model)
