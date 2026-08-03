"""Read-only retrieval for curriculum and subject knowledge used by homework tutoring."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ai_education.domain.enums import Subject

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "Knowledge" / "91_indexes" / "knowledge.db"


class HomeworkKnowledgeService:
    """Retrieve safe curriculum evidence without exposing answer-bank content."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH

    def search(self, query: str, *, subject: Subject, limit: int = 4) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        tokens = self._query_tokens(query)
        if not tokens:
            return []
        match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:24])
        sql = """
            SELECT
                c.chunk_id,
                c.document_id,
                c.title,
                c.content,
                c.document_type,
                c.source_url,
                c.page_start,
                c.page_end,
                c.authority_level,
                c.review_status,
                c.metadata_json,
                bm25(chunks_fts, 0.0, 2.0, 1.0, 0.4) AS rank
            FROM chunks_fts
            JOIN chunks AS c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
              AND (c.subject = ? OR c.subject = 'all')
            ORDER BY
                CASE c.document_type
                    WHEN 'KNOWLEDGE_TAXONOMY' THEN 0
                    WHEN 'CURRICULUM_STANDARD' THEN 1
                    WHEN 'TEXTBOOK_CHAPTER_CATALOG' THEN 2
                    ELSE 3
                END,
                rank ASC
            LIMIT ?
        """
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                sql,
                (match, subject.value, max(1, min(limit, 8))),
            ).fetchall()
        except sqlite3.Error:
            return []
        finally:
            connection.close()
        return [self._public_reference(dict(row), tokens) for row in rows]

    @staticmethod
    def _query_tokens(text: str) -> list[str]:
        tokens: list[str] = []
        for sequence in re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9_]+", text.lower()):
            if re.fullmatch(r"[\u3400-\u9fff]+", sequence) and len(sequence) > 1:
                tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
            else:
                tokens.append(sequence)
        return list(dict.fromkeys(token for token in tokens if token.strip()))

    @classmethod
    def _public_reference(cls, row: dict[str, Any], tokens: list[str]) -> dict[str, Any]:
        metadata = json.loads(row.pop("metadata_json") or "{}")
        content = cls._clean_content(str(row.pop("content", "")), tokens)
        return {
            "source_id": row["chunk_id"],
            "document_id": row["document_id"],
            "title": row["title"],
            "document_type": row["document_type"],
            "authority_level": row["authority_level"],
            "review_status": row["review_status"],
            "summary": content,
            "source_url": row["source_url"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "module_id": metadata.get("module_id"),
        }

    @staticmethod
    def _clean_content(content: str, tokens: list[str]) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        if not compact:
            return ""
        lowered = compact.lower()
        positions = [lowered.find(token) for token in tokens if lowered.find(token) >= 0]
        start = max(0, min(positions) - 80) if positions else 0
        excerpt = compact[start : start + 420]
        if start:
            excerpt = f"…{excerpt}"
        if start + 420 < len(compact):
            excerpt = f"{excerpt}…"
        return excerpt
