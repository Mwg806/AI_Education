"""Central model selection boundary for all progressively migrated agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_education.config import Settings
from ai_education.llm.factory import create_chat_model


@dataclass(frozen=True, slots=True)
class ModelSelection:
    purpose: str
    model_name: str | None
    provider: str | None
    model: Any | None


class ModelRouter:
    """Keep model selection outside business agents while retaining one-model compatibility."""

    def __init__(self, settings: Settings, model: Any | None = None) -> None:
        self.settings = settings
        self._model = create_chat_model(settings) if model is None else model

    def select(self, purpose: str, *, needs_vision: bool = False) -> ModelSelection:
        del needs_vision  # The current deployment has one multimodal-compatible model pool.
        return ModelSelection(
            purpose=purpose,
            model_name=self.settings.llm_model or None,
            provider=self.settings.llm_provider if self.settings.llm_enabled else None,
            model=self._model,
        )

    @property
    def default_model(self) -> Any | None:
        return self._model
