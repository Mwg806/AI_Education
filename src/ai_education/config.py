"""Environment-backed application settings without secret persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_temperature: float
    max_retries: int
    policy_cache_ttl_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            llm_enabled=_as_bool(os.getenv("AI_EDUCATION_LLM_ENABLED")),
            llm_provider=os.getenv("AI_EDUCATION_LLM_PROVIDER", "openai"),
            llm_model=os.getenv("AI_EDUCATION_LLM_MODEL", ""),
            llm_temperature=float(os.getenv("AI_EDUCATION_LLM_TEMPERATURE", "0")),
            max_retries=min(max(int(os.getenv("AI_EDUCATION_MAX_RETRIES", "3")), 1), 3),
            policy_cache_ttl_seconds=int(
                os.getenv("AI_EDUCATION_POLICY_CACHE_TTL_SECONDS", "86400")
            ),
        )
