"""Read validated, chapter-searchable quick-diagnostic shards from private OSS.

Online requests read only compact structured JSON shards.  Raw licensed DOCX/PDF
objects are handled by the offline builder and are never parsed on a student
request.  The last verified shard is cached on disk so a transient OSS outage can
still fall back safely without accepting unverified content.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from ai_education.config import PROJECT_ROOT, Settings

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = "1.0"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_SHARD_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_SHARD_BYTES = 192 * 1024 * 1024
MAX_QUESTIONS_PER_SUBJECT = 10_000


class OssObjectReader(Protocol):
    def get_bytes(self, key: str, *, max_bytes: int) -> bytes: ...


class AlibabaCloudOssObjectReader:
    """Minimal OSS V2 reader using rotating ECS RAM-role credentials."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint: str,
        ecs_role_name: str,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint = endpoint
        self.ecs_role_name = ecs_role_name
        self._client: Any | None = None
        self._oss: Any | None = None

    def _ensure_client(self) -> tuple[Any, Any]:
        if self._client is not None and self._oss is not None:
            return self._client, self._oss
        try:
            import alibabacloud_oss_v2 as oss
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise RuntimeError("未安装 alibabacloud-oss-v2，无法读取 OSS 诊断题库") from exc

        if self.ecs_role_name:
            try:
                from alibabacloud_credentials.client import Client as CredentialClient
                from alibabacloud_credentials.models import Config as CredentialConfig
            except ImportError as exc:  # pragma: no cover - deployment dependency guard
                raise RuntimeError("未安装 alibabacloud-credentials") from exc
            credential_client = CredentialClient(
                CredentialConfig(type="ecs_ram_role", role_name=self.ecs_role_name)
            )

            def credentials() -> Any:
                credential = credential_client.get_credential()
                return oss.credentials.Credentials(
                    access_key_id=credential.access_key_id,
                    access_key_secret=credential.access_key_secret,
                    security_token=credential.security_token,
                )

            provider = oss.credentials.CredentialsProviderFunc(func=credentials)
        else:
            provider = oss.credentials.EnvironmentVariableCredentialsProvider()

        config = oss.config.load_default()
        config.credentials_provider = provider
        config.region = self.region
        if self.endpoint:
            config.endpoint = self.endpoint
        self._oss = oss
        self._client = oss.Client(config)
        return self._client, self._oss

    def get_bytes(self, key: str, *, max_bytes: int) -> bytes:
        client, oss = self._ensure_client()
        result = client.get_object(oss.GetObjectRequest(bucket=self.bucket, key=key))
        content_length = int(result.content_length or 0)
        if content_length > max_bytes:
            raise ValueError(f"OSS 对象超过允许大小：{content_length} > {max_bytes}")
        payload = bytearray()
        try:
            for chunk in result.body.iter_bytes():
                payload.extend(chunk)
                if len(payload) > max_bytes:
                    raise ValueError(f"OSS 对象读取超过允许大小：{max_bytes}")
        finally:
            close = getattr(result.body, "close", None)
            if callable(close):
                close()
        return bytes(payload)

    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> str:
        """Upload a processed build artifact; used only by the offline builder."""

        client, oss = self._ensure_client()
        result = client.put_object(
            oss.PutObjectRequest(
                bucket=self.bucket,
                key=key,
                body=payload,
                content_type=content_type,
            )
        )
        return str(result.etag or "")


class StructuredOssQuickDiagnosticBank:
    """Load and validate private structured question shards with bounded caching."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint: str,
        ecs_role_name: str,
        prefix: str,
        cache_dir: Path,
        cache_ttl_seconds: int = 900,
        reader: OssObjectReader | None = None,
    ) -> None:
        if not bucket or not prefix:
            raise ValueError("OSS 题库必须配置 bucket 和 prefix")
        self.bucket = bucket
        self.prefix = prefix.strip(" /")
        self.cache_dir = cache_dir
        self.cache_ttl_seconds = max(30, cache_ttl_seconds)
        self.reader = reader or AlibabaCloudOssObjectReader(
            bucket=bucket,
            region=region,
            endpoint=endpoint,
            ecs_role_name=ecs_role_name,
        )
        self._manifest_cache: tuple[float, dict[str, Any]] | None = None
        self._memory_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> StructuredOssQuickDiagnosticBank | None:
        if not settings.oss_question_bank_enabled:
            return None
        raw_cache_dir = Path(settings.oss_cache_dir)
        cache_dir = raw_cache_dir if raw_cache_dir.is_absolute() else PROJECT_ROOT / raw_cache_dir
        return cls(
            bucket=settings.oss_bucket,
            region=settings.oss_region,
            endpoint=settings.oss_endpoint,
            ecs_role_name=settings.oss_ecs_role_name,
            prefix=settings.oss_question_prefix,
            cache_dir=cache_dir,
            cache_ttl_seconds=settings.oss_cache_ttl_seconds,
        )

    def questions(self, subject: str) -> list[dict[str, Any]]:
        cached = self._memory_cache.get(subject)
        if cached and time.monotonic() - cached[0] <= self.cache_ttl_seconds:
            return [dict(item) for item in cached[1]]

        manifest = self._manifest()
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("OSS 快速诊断题库清单版本不受支持")
        subjects = manifest.get("subjects")
        entry = subjects.get(subject) if isinstance(subjects, dict) else None
        if not isinstance(entry, dict):
            self._memory_cache[subject] = (time.monotonic(), [])
            return []
        object_key = str(entry.get("object_key") or "")
        expected_sha256 = str(entry.get("sha256") or "")
        if not object_key.startswith(f"{self.prefix}/subjects/"):
            raise ValueError("OSS 快速诊断题库分片路径越界")
        payload = self._load_object_with_cache(object_key, max_bytes=MAX_SHARD_BYTES)
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if len(expected_sha256) != 64 or actual_sha256 != expected_sha256:
            raise ValueError("OSS 快速诊断题库分片校验和不一致")
        decoded = self._decode_json(payload, allow_gzip=object_key.endswith(".gz"))
        questions = self._validate_subject_payload(subject, decoded)
        expected_count = int(entry.get("question_count") or 0)
        if expected_count != len(questions):
            raise ValueError("OSS 快速诊断题库分片题量与清单不一致")
        self._memory_cache[subject] = (time.monotonic(), questions)
        return [dict(item) for item in questions]

    def _manifest(self) -> dict[str, Any]:
        if (
            self._manifest_cache is not None
            and time.monotonic() - self._manifest_cache[0] <= self.cache_ttl_seconds
        ):
            return self._manifest_cache[1]
        manifest = self._load_json_object(
            f"{self.prefix}/manifest.json",
            max_bytes=MAX_MANIFEST_BYTES,
            allow_gzip=False,
        )
        self._manifest_cache = (time.monotonic(), manifest)
        return manifest

    def _load_json_object(self, key: str, *, max_bytes: int, allow_gzip: bool) -> dict[str, Any]:
        return self._decode_json(
            self._load_object_with_cache(key, max_bytes=max_bytes),
            allow_gzip=allow_gzip,
        )

    def _load_object_with_cache(self, key: str, *, max_bytes: int) -> bytes:
        cache_path = self._cache_path(key)
        try:
            payload = self.reader.get_bytes(key, max_bytes=max_bytes)
            self._write_cache(cache_path, payload)
            return payload
        except Exception as exc:
            if cache_path.is_file():
                payload = cache_path.read_bytes()
                if len(payload) <= max_bytes:
                    LOGGER.warning("OSS 题库读取失败，使用最近校验缓存：%s", exc)
                    return payload
            raise

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(f"{self.bucket}:{key}".encode()).hexdigest()
        suffix = ".json.gz" if key.endswith(".gz") else ".json"
        return self.cache_dir / f"{digest}{suffix}"

    @staticmethod
    def _write_cache(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        temporary.write_bytes(payload)
        temporary.chmod(0o600)
        temporary.replace(path)

    @staticmethod
    def _decode_json(payload: bytes, *, allow_gzip: bool) -> dict[str, Any]:
        if allow_gzip:
            with gzip.GzipFile(fileobj=BytesIO(payload), mode="rb") as archive:
                payload = archive.read(MAX_UNCOMPRESSED_SHARD_BYTES + 1)
            if len(payload) > MAX_UNCOMPRESSED_SHARD_BYTES:
                raise ValueError("OSS 快速诊断题库解压后超过允许大小")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("OSS 快速诊断题库对象必须是 JSON 对象")
        return decoded

    @staticmethod
    def _validate_subject_payload(subject: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if payload.get("schema_version") != SCHEMA_VERSION or payload.get("subject") != subject:
            raise ValueError("OSS 快速诊断题库分片学科或版本不一致")
        raw_questions = payload.get("questions")
        if not isinstance(raw_questions, list) or len(raw_questions) > MAX_QUESTIONS_PER_SUBJECT:
            raise ValueError("OSS 快速诊断题库分片题目结构无效")
        result: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for raw in raw_questions:
            if not isinstance(raw, dict):
                raise ValueError("OSS 快速诊断题目必须是对象")
            source_id = str(raw.get("source_question_id") or "")
            prompt = str(raw.get("prompt") or "").strip()
            options = raw.get("options")
            correct_option = raw.get("correct_option")
            if (
                not source_id
                or len(source_id) > 200
                or source_id in seen_ids
                or not prompt
                or len(prompt) > 6_000
                or not isinstance(options, list)
                or len(options) != 4
                or any(not str(option).strip() or len(str(option)) > 1_200 for option in options)
                or not isinstance(correct_option, int)
                or isinstance(correct_option, bool)
                or correct_option not in range(4)
            ):
                raise ValueError(f"OSS 快速诊断题目字段无效：{source_id or 'unknown'}")
            seen_ids.add(source_id)
            item = dict(raw)
            item["source_storage"] = "oss"
            item["source_kind"] = str(item.get("source_kind") or "licensed_practice")
            item["knowledge_tags"] = [
                str(tag) for tag in item.get("knowledge_tags", []) if str(tag).strip()
            ]
            item["search_text"] = str(
                item.get("search_text") or f"{item.get('knowledge_focus', '')} {item['prompt']}"
            )
            result.append(item)
        return result
