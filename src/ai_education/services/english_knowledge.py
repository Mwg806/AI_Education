"""Read-only English curriculum retrieval with legacy subject-tag compatibility."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ai_education.services.homework_knowledge import DEFAULT_DB_PATH


class EnglishKnowledgeService:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        tokens = list(
            dict.fromkeys(re.findall(r"[\u3400-\u9fff]{2}|[A-Za-z][A-Za-z0-9_-]+", query.lower()))
        )
        if not tokens:
            tokens = ["英语", "阅读"]
        match = " OR ".join(f'"{item.replace(chr(34), "")}"' for item in tokens[:20])
        sql = """
            SELECT c.chunk_id, c.document_id, c.title, c.content, c.document_type,
                   c.source_url, c.page_start, c.page_end, c.authority_level,
                   c.review_status, c.metadata_json,
                   bm25(chunks_fts, 0.0, 2.0, 1.0, 0.4) AS rank
            FROM chunks_fts JOIN chunks c ON c.chunk_id=chunks_fts.chunk_id
            WHERE chunks_fts MATCH ? AND c.subject IN ('english','foreign_language')
            ORDER BY CASE c.document_type WHEN 'CURRICULUM_STANDARD' THEN 0
                         WHEN 'KNOWLEDGE_TAXONOMY' THEN 1
                         WHEN 'TEXTBOOK_CHAPTER_CATALOG' THEN 2 ELSE 3 END,
                     c.authority_level ASC, rank ASC
            LIMIT ?
        """
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(sql, (match, max(1, min(limit, 8)))).fetchall()
        except sqlite3.Error:
            return []
        finally:
            connection.close()
        references = []
        for raw in rows:
            row = dict(raw)
            metadata = json.loads(row.pop("metadata_json") or "{}")
            content = re.sub(r"\s+", " ", row.pop("content", "")).strip()
            references.append(
                {
                    "source_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "document_type": row["document_type"],
                    "authority_level": row["authority_level"],
                    "review_status": row["review_status"],
                    "summary": content[:500],
                    "source_url": row["source_url"],
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                    "version": metadata.get("version"),
                }
            )
        return references

    def curriculum_basis(self) -> list[dict[str, Any]]:
        return self.search("英语课程标准 语言能力 阅读 语篇 词汇 语法", limit=5)
