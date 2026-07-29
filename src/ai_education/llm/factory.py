"""Create supported chat models strictly from process environment variables."""

from __future__ import annotations

import os
from typing import Any

from ai_education.config import Settings
from ai_education.core.errors import InputValidationError


def create_chat_model(settings: Settings) -> Any | None:
    if not settings.llm_enabled:
        return None
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        model = settings.llm_model or os.getenv("OPENAI_MODEL")
        if not model:
            raise InputValidationError("启用 LLM 时必须设置 AI_EDUCATION_LLM_MODEL")
        return ChatOpenAI(
            model=model,
            temperature=settings.llm_temperature,
            max_retries=settings.max_retries,
        )
    if settings.llm_provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise InputValidationError(
                "Anthropic 提供方需要安装 pyproject.toml 的 anthropic 可选依赖"
            ) from exc
        model = settings.llm_model or os.getenv("ANTHROPIC_MODEL")
        if not model:
            raise InputValidationError("启用 LLM 时必须设置 AI_EDUCATION_LLM_MODEL")
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        return ChatAnthropic(
            model=model,
            temperature=settings.llm_temperature,
            max_retries=settings.max_retries,
            api_key=api_key,
        )
    raise InputValidationError(f"不支持的 LLM 提供方：{settings.llm_provider}")
