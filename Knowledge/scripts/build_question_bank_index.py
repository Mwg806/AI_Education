"""Build the metadata catalog and SQLite search index for the local 5·3 corpus."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ai_education.services.question_bank import (
    CATALOG_PATH,
    CORPUS_ROOT,
    INDEX_PATH,
    build_catalog_items,
    catalog_summary,
)


def build(corpus_root: Path, catalog_path: Path, index_path: Path) -> dict:
    items = build_catalog_items(corpus_root)
    summary = catalog_summary(items)
    payload = {
        "schema_version": "1.0",
        "corpus": "2026五年高考三年模拟53A、B版新高考全套资料",
        "copyright_boundary": "仅索引本地授权资源元数据；原文与答案不写入目录文件",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "items": items,
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(index_path) as connection:
        connection.execute("DROP TABLE IF EXISTS question_sources")
        connection.execute(
            """
            CREATE TABLE question_sources (
                source_id TEXT PRIMARY KEY,
                relative_path TEXT NOT NULL,
                title TEXT NOT NULL,
                subject TEXT,
                edition TEXT NOT NULL,
                region TEXT NOT NULL,
                content_role TEXT NOT NULL,
                topic TEXT,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                supported INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO question_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["source_id"],
                    item["relative_path"],
                    item["title"],
                    item.get("subject"),
                    item["edition"],
                    item["region"],
                    item["content_role"],
                    item.get("topic"),
                    item["file_type"],
                    item["file_size"],
                    int(item["supported"]),
                )
                for item in items
            ],
        )
        connection.execute("CREATE INDEX idx_qb_subject ON question_sources(subject)")
        connection.execute("CREATE INDEX idx_qb_role ON question_sources(content_role)")
        connection.execute("CREATE INDEX idx_qb_region ON question_sources(region)")
        connection.commit()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, default=CORPUS_ROOT)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    args = parser.parse_args()
    print(
        json.dumps(build(args.corpus_root, args.catalog, args.index), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
