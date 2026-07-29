#!/usr/bin/env python3
"""使用 SQLite FTS5 查询 AI Education 知识库。"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = KNOWLEDGE_ROOT / "91_indexes" / "knowledge.db"


def query_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for sequence in re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9_]+", text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", sequence) and len(sequence) > 1:
            tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        else:
            tokens.append(sequence)
    return list(dict.fromkeys(token for token in tokens if token.strip()))


def search(
    query: str,
    *,
    subject: str | None = None,
    province: str | None = None,
    document_type: str | None = None,
    top_k: int = 8,
) -> list[dict[str, object]]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"索引不存在，请先运行 build_knowledge_base.py: {DB_PATH}")
    tokens = query_tokens(query)
    if not tokens:
        return []
    match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:24])
    clauses = ["chunks_fts MATCH ?"]
    parameters: list[object] = [match]
    if subject:
        clauses.append("(c.subject = ? OR c.subject = 'all')")
        parameters.append(subject)
    if province:
        clauses.append("(c.province = ? OR c.province IS NULL)")
        parameters.append(province)
    if document_type:
        clauses.append("c.document_type = ?")
        parameters.append(document_type)
    parameters.append(top_k)
    sql = f"""
        SELECT c.*, bm25(chunks_fts, 0.0, 2.0, 1.0, 0.4) AS rank
        FROM chunks_fts
        JOIN chunks AS c ON c.chunk_id = chunks_fts.chunk_id
        WHERE {" AND ".join(clauses)}
        ORDER BY rank ASC, c.authority_level ASC
        LIMIT ?
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()
    results = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        item["citation"] = {
            "title": item["title"],
            "url": item["source_url"],
            "page_start": item["page_start"],
            "page_end": item["page_end"],
        }
        results.append(item)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="查询全国新课标Ⅰ卷知识库")
    parser.add_argument("query", help="自然语言或关键词")
    parser.add_argument("--subject")
    parser.add_argument("--province", help="省份 slug，如 zhejiang")
    parser.add_argument("--document-type")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--content-limit", type=int, default=500)
    args = parser.parse_args()
    results = search(
        args.query,
        subject=args.subject,
        province=args.province,
        document_type=args.document_type,
        top_k=max(1, min(args.top_k, 50)),
    )
    for item in results:
        item["content"] = item["content"][: args.content_limit]
    print(
        json.dumps(
            {"query": args.query, "count": len(results), "results": results},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
