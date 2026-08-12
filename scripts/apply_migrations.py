#!/usr/bin/env python3
"""Checksum-verified additive MySQL migration runner."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from ai_education.config import PROJECT_ROOT, Settings
from ai_education.mysql_persistence import MySQLPersistence

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    checksum CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def migration_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*.sql") if not path.name.endswith(".rollback.sql"))


def statements(sql: str) -> list[str]:
    cleaned = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [item.strip() for item in re.split(r";\s*(?:\n|$)", cleaned) if item.strip()]


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(*, dry_run: bool) -> int:
    settings = Settings.from_env()
    if not settings.mysql_enabled:
        raise SystemExit("AI_EDUCATION_MYSQL_ENABLED 未开启，未执行迁移")
    persistence = MySQLPersistence(settings)
    files = migration_files(PROJECT_ROOT / "migrations")
    if dry_run:
        for path in files:
            print(f"PENDING-CHECK {path.name} sha256={checksum(path)}")
        return 0
    with persistence.connection() as connection, connection.cursor() as cursor:
        cursor.execute(MIGRATION_TABLE_SQL)
        cursor.execute("SELECT version, checksum FROM schema_migrations")
        applied = {row["version"]: row["checksum"] for row in cursor.fetchall()}
        for path in files:
            digest = checksum(path)
            previous = applied.get(path.name)
            if previous and previous != digest:
                raise RuntimeError(f"迁移校验和漂移：{path.name}")
            if previous:
                print(f"SKIP {path.name}")
                continue
            for statement in statements(path.read_text(encoding="utf-8")):
                cursor.execute(statement)
            cursor.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s,%s)",
                (path.name, digest),
            )
            print(f"APPLIED {path.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--rollback-plan",
        action="store_true",
        help="打印数据保留型回滚说明，不执行 DROP",
    )
    args = parser.parse_args()
    if args.rollback_plan:
        for path in sorted((PROJECT_ROOT / "migrations").glob("*.rollback.sql")):
            print(path.read_text(encoding="utf-8"))
        return 0
    return apply(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
