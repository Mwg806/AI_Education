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

        if not settings.llm_model:
            raise InputValidationError("启用 LLM 时必须设置 AI_EDUCATION_LLM_MODEL")
        if not os.getenv("OPENAI_API_KEY"):
            raise InputValidationError("启用 OpenAI-compatible LLM 时必须设置 OPENAI_API_KEY")
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_retries=settings.max_retries,
            timeout=settings.llm_timeout_seconds,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
    if settings.llm_provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise InputValidationError(
                "Anthropic 提供方需要安装 pyproject.toml 的 anthropic 可选依赖"
            ) from exc
        if not settings.llm_model:
            raise InputValidationError("启用 LLM 时必须设置 AI_EDUCATION_LLM_MODEL")
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise InputValidationError("启用 Anthropic-compatible LLM 时必须设置 API Key")
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_retries=settings.max_retries,
            api_key=api_key,
        )
    raise InputValidationError(f"不支持的 LLM 提供方：{settings.llm_provider}")
