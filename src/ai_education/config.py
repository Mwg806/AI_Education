"""Environment-backed application settings without secret persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


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
    llm_timeout_seconds: float
    allow_rule_fallback: bool
    max_retries: int
    policy_cache_ttl_seconds: int
    mysql_enabled: bool
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_connect_timeout_seconds: int
    auth_session_hours: int
    phone_auth_enabled: bool
    aliyun_access_key_id: str
    aliyun_access_key_secret: str
    phone_auth_scheme_name: str
    phone_auth_sign_name: str
    phone_auth_template_code: str
    phone_auth_code_length: int
    phone_auth_code_ttl_seconds: int
    phone_auth_resend_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("AI_EDUCATION_LLM_PROVIDER", "openai").strip().lower()
        model = (os.getenv("AI_EDUCATION_LLM_MODEL") or os.getenv("OPENAI_MODEL", "")).strip()
        key_present = bool(
            os.getenv("OPENAI_API_KEY")
            if provider == "openai"
            else os.getenv("ANTHROPIC_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        )
        return cls(
            llm_enabled=_as_bool(
                os.getenv("AI_EDUCATION_LLM_ENABLED"),
                default=bool(model and key_present),
            ),
            llm_provider=provider,
            llm_model=model,
            llm_temperature=float(os.getenv("AI_EDUCATION_LLM_TEMPERATURE", "0.3")),
            llm_timeout_seconds=min(
                max(float(os.getenv("AI_EDUCATION_LLM_TIMEOUT_SECONDS", "90")), 10),
                180,
            ),
            allow_rule_fallback=_as_bool(
                os.getenv("AI_EDUCATION_ALLOW_RULE_FALLBACK"),
                default=False,
            ),
            max_retries=min(max(int(os.getenv("AI_EDUCATION_MAX_RETRIES", "3")), 1), 3),
            policy_cache_ttl_seconds=int(
                os.getenv("AI_EDUCATION_POLICY_CACHE_TTL_SECONDS", "86400")
            ),
            mysql_enabled=_as_bool(os.getenv("AI_EDUCATION_MYSQL_ENABLED"), default=False),
            mysql_host=os.getenv("AI_EDUCATION_MYSQL_HOST", "127.0.0.1").strip(),
            mysql_port=int(os.getenv("AI_EDUCATION_MYSQL_PORT", "3306")),
            mysql_user=os.getenv("AI_EDUCATION_MYSQL_USER", "root").strip(),
            mysql_password=os.getenv("AI_EDUCATION_MYSQL_PASSWORD", ""),
            mysql_database=os.getenv("AI_EDUCATION_MYSQL_DATABASE", "ai_education").strip(),
            mysql_connect_timeout_seconds=min(
                max(int(os.getenv("AI_EDUCATION_MYSQL_CONNECT_TIMEOUT_SECONDS", "5")), 1),
                30,
            ),
            auth_session_hours=min(
                max(int(os.getenv("AI_EDUCATION_AUTH_SESSION_HOURS", "168")), 1),
                24 * 90,
            ),
            phone_auth_enabled=_as_bool(
                os.getenv("AI_EDUCATION_PHONE_AUTH_ENABLED"), default=False
            ),
            aliyun_access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "").strip(),
            aliyun_access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "").strip(),
            phone_auth_scheme_name=os.getenv(
                "AI_EDUCATION_PHONE_AUTH_SCHEME_NAME", "问鹿用户认证"
            ).strip(),
            phone_auth_sign_name=os.getenv(
                "AI_EDUCATION_PHONE_AUTH_SIGN_NAME", "速通互联验证码"
            ).strip(),
            phone_auth_template_code=os.getenv(
                "AI_EDUCATION_PHONE_AUTH_TEMPLATE_CODE", "100001"
            ).strip(),
            phone_auth_code_length=min(
                max(int(os.getenv("AI_EDUCATION_PHONE_AUTH_CODE_LENGTH", "6")), 4), 8
            ),
            phone_auth_code_ttl_seconds=min(
                max(int(os.getenv("AI_EDUCATION_PHONE_AUTH_CODE_TTL_SECONDS", "300")), 60), 900
            ),
            phone_auth_resend_seconds=min(
                max(int(os.getenv("AI_EDUCATION_PHONE_AUTH_RESEND_SECONDS", "60")), 30), 300
            ),
        )
