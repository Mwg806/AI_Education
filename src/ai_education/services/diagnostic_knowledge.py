"""Source-grounded retrieval for planner quick-diagnostic generation."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KNOWLEDGE_INDEX = PROJECT_ROOT / "Knowledge" / "91_indexes" / "knowledge.db"

SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "chinese": ("chinese",),
    "mathematics": ("mathematics",),
    "foreign_language": ("english", "foreign_language"),
    "physics": ("physics",),
    "chemistry": ("chemistry",),
    "biology": ("biology",),
    "history": ("history",),
    "geography": ("geography",),
    "ideology_politics": ("politics", "ideology_politics"),
    "technology": ("information_technology", "general_technology", "technology"),
}

GROUNDING_DOCUMENT_TYPES = (
    "CURRICULUM_STANDARD",
    "KNOWLEDGE_TAXONOMY",
    "EVALUATION_FRAMEWORK",
)


def _query_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    cleaned = re.sub(
        r"(?:选择性)?必修(?:第?[一二三四五六七八九十0-9]+)?(?:册)?|"
        r"第[一二三四五六七八九十0-9]+(?:章|单元|节)|教材|全册",
        " ",
        text,
    )
    for sequence in re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9_]+", cleaned.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", sequence) and len(sequence) > 1:
            tokens.append(sequence)
            tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        else:
            tokens.append(sequence)
    return list(dict.fromkeys(token for token in tokens if token.strip()))


class DiagnosticKnowledgeRetriever:
    """Retrieve authoritative, chapter-associated evidence from the local FTS index."""

    def __init__(self, index_path: Path = DEFAULT_KNOWLEDGE_INDEX) -> None:
        self.index_path = index_path

    @property
    def available(self) -> bool:
        return self.index_path.exists()

    def retrieve(
        self,
        *,
        subject: str,
        scope_units: list[dict[str, str]],
        max_sources: int = 12,
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "status": "unavailable",
                "sources": [],
                "missing_scope_ids": [item["id"] for item in scope_units],
                "reason": "本地权威知识库索引不存在",
            }

        aliases = SUBJECT_ALIASES.get(subject, (subject,))
        sources: list[dict[str, Any]] = []
        missing_scope_ids: list[str] = []
        per_scope_limit = max(2, min(4, max_sources // max(len(scope_units), 1)))
        for scope in scope_units:
            rows = self._search_scope(
                label=scope["label"],
                aliases=aliases,
                limit=per_scope_limit,
            )
            if not rows:
                missing_scope_ids.append(scope["id"])
                continue
            for row in rows:
                content = self._compact_content(str(row["content"]))
                if len(content) < 40:
                    continue
                sources.append(
                    {
                        "source_id": str(row["chunk_id"]),
                        "scope_id": scope["id"],
                        "scope_label": scope["label"],
                        "title": str(row["title"]),
                        "document_type": str(row["document_type"]),
                        "authority_level": str(row["authority_level"]),
                        "page_start": row["page_start"],
                        "page_end": row["page_end"],
                        "source_url": row["source_url"],
                        "content": content[:2_200],
                    }
                )

        covered = {item["scope_id"] for item in sources}
        missing_scope_ids = [
            item["id"]
            for item in scope_units
            if item["id"] not in covered or item["id"] in missing_scope_ids
        ]
        status = "ready" if sources and not missing_scope_ids else "insufficient"
        return {
            "status": status,
            "sources": sources[:max_sources],
            "missing_scope_ids": missing_scope_ids,
            "reason": (
                ""
                if status == "ready"
                else "所选章节没有检索到足够的课程标准或知识分类依据"
            ),
        }

    def _search_scope(
        self,
        *,
        label: str,
        aliases: tuple[str, ...],
        limit: int,
    ) -> list[sqlite3.Row]:
        tokens = _query_tokens(label)
        if not tokens:
            return []
        match = " OR ".join(
            f'"{token.replace(chr(34), "")}"' for token in tokens[:32]
        )
        subject_placeholders = ",".join("?" for _ in aliases)
        type_placeholders = ",".join("?" for _ in GROUNDING_DOCUMENT_TYPES)
        sql = f"""
            SELECT c.*, bm25(chunks_fts, 0.0, 2.2, 1.2, 0.5) AS rank
            FROM chunks_fts
            JOIN chunks AS c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
              AND c.subject IN ({subject_placeholders})
              AND c.document_type IN ({type_placeholders})
              AND c.authority_level IN ('A', 'B')
            ORDER BY
              CASE c.document_type
                WHEN 'CURRICULUM_STANDARD' THEN 0
                WHEN 'KNOWLEDGE_TAXONOMY' THEN 1
                ELSE 2
              END,
              rank ASC,
              c.page_start ASC
            LIMIT ?
        """
        parameters: list[Any] = [
            match,
            *aliases,
            *GROUNDING_DOCUMENT_TYPES,
            limit,
        ]
        connection = sqlite3.connect(self.index_path)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(sql, parameters).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            connection.close()

    @staticmethod
    def _compact_content(content: str) -> str:
        lines = [" ".join(line.split()) for line in content.splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def prompt_sources(retrieval: dict[str, Any]) -> str:
        payload = [
            {
                "source_id": item["source_id"],
                "scope_id": item["scope_id"],
                "scope_label": item["scope_label"],
                "title": item["title"],
                "document_type": item["document_type"],
                "authority_level": item["authority_level"],
                "page_start": item["page_start"],
                "page_end": item["page_end"],
                "content": item["content"],
            }
            for item in retrieval.get("sources", [])
        ]
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def public_sources(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                key: item.get(key)
                for key in (
                    "source_id",
                    "scope_id",
                    "scope_label",
                    "title",
                    "document_type",
                    "authority_level",
                    "page_start",
                    "page_end",
                    "source_url",
                )
            }
            for item in retrieval.get("sources", [])
        ]
