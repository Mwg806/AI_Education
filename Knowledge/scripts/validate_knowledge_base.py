#!/usr/bin/env python3
"""校验知识库结构、来源、哈希、分块 schema 与索引一致性。"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    document_schema = json.loads((ROOT / "schemas" / "document.schema.json").read_text("utf-8"))
    chunk_schema = json.loads((ROOT / "schemas" / "chunk.schema.json").read_text("utf-8"))
    registry = json.loads((ROOT / "00_manifest" / "source_registry.json").read_text("utf-8"))
    document_validator = Draft202012Validator(document_schema, format_checker=FormatChecker())
    chunk_validator = Draft202012Validator(chunk_schema, format_checker=FormatChecker())

    for source in registry["sources"]:
        for error in document_validator.iter_errors(source):
            errors.append(f"source {source.get('document_id')}: {error.message}")

    manifest_path = ROOT / "00_manifest" / "document_manifest.csv"
    manifest = list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig")))
    for row in manifest:
        raw = ROOT / "01_official_standards" / "raw" / row["file_name"]
        if not raw.exists():
            errors.append(f"manifest 文件不存在: {row['file_name']}")
        elif hash_file(raw) != row["sha256"]:
            errors.append(f"SHA256 不一致: {row['document_id']}")

    chunks = []
    seen: Counter[str] = Counter()
    with (ROOT / "90_processed" / "chunks" / "all_chunks.jsonl").open(
        "r", encoding="utf-8"
    ) as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"chunk JSONL 第{line_number}行: {exc}")
                continue
            chunks.append(chunk)
            seen[chunk.get("chunk_id", "")] += 1
            for error in chunk_validator.iter_errors(chunk):
                errors.append(f"chunk {chunk.get('chunk_id')}: {error.message}")
            if len(chunk.get("content", "")) > 1300:
                warnings.append(f"分块偏长: {chunk.get('chunk_id')} ({len(chunk['content'])})")
    duplicates = [chunk_id for chunk_id, count in seen.items() if count > 1]
    if duplicates:
        errors.append(f"重复 chunk_id: {duplicates[:10]}")

    db = sqlite3.connect(ROOT / "91_indexes" / "knowledge.db")
    try:
        db_count = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
        fts_count = db.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        db.close()
    if db_count != len(chunks) or fts_count != len(chunks):
        errors.append(f"索引计数不一致: jsonl={len(chunks)}, db={db_count}, fts={fts_count}")
    if integrity != "ok":
        errors.append(f"SQLite integrity_check: {integrity}")

    routes = json.loads((ROOT / "catalogs" / "province_exam_routes.json").read_text("utf-8"))
    province_count = len(routes["provinces"])
    if province_count != 11:
        errors.append(f"全国新课标Ⅰ卷省份应为11，当前为{province_count}")
    if not any(
        item["slug"] == "zhejiang" and item.get("technology_required_in_kb")
        for item in routes["provinces"]
    ):
        errors.append("浙江技术科路由缺失")

    textbook_catalog = json.loads(
        (ROOT / "catalogs" / "textbook_pdf_catalog.json").read_text("utf-8")
    )
    textbook_subjects = {item["id"] for item in textbook_catalog["subjects"]}
    expected_subjects = {
        "chinese",
        "mathematics",
        "foreign_language",
        "physics",
        "chemistry",
        "biology",
        "ideology_politics",
        "history",
        "geography",
        "technology",
    }
    if textbook_subjects != expected_subjects:
        errors.append(f"教材目录规划科目不完整: {sorted(textbook_subjects)}")
    textbook_editions = [
        edition for subject in textbook_catalog["subjects"] for edition in subject["editions"]
    ]
    textbook_volumes = [volume for edition in textbook_editions for volume in edition["volumes"]]
    if len(textbook_volumes) != textbook_catalog["pdf_count"]:
        errors.append(
            "教材 PDF 计数不一致: "
            f"catalog={textbook_catalog['pdf_count']}, volumes={len(textbook_volumes)}"
        )
    source_paths: set[str] = set()
    valid_statuses = {
        "VERIFIED_FROM_PDF_TOC",
        "HEADING_EXTRACTED_REVIEW_REQUIRED",
        "VOLUME_ONLY_REVIEW_REQUIRED",
        "UNREADABLE_PDF",
    }
    for volume in textbook_volumes:
        source_pdf = volume["source_pdf"]
        if source_pdf in source_paths:
            errors.append(f"教材 PDF 重复登记: {source_pdf}")
        source_paths.add(source_pdf)
        source_path = ROOT.parent / source_pdf
        if not source_path.exists():
            errors.append(f"教材 PDF 不存在: {source_pdf}")
        if volume["catalog_status"] not in valid_statuses:
            errors.append(f"未知教材目录状态: {volume['catalog_status']}")
        for chapter in volume["chapters"]:
            evidence = chapter["evidence"]
            if evidence["source_pdf"] != source_pdf:
                errors.append(f"章节证据 PDF 不匹配: {chapter['id']}")
            if not 1 <= evidence["pdf_page"] <= max(volume["page_count"], 1):
                errors.append(f"章节证据页码越界: {chapter['id']}")
    review_required_count = sum(
        volume["catalog_status"] != "VERIFIED_FROM_PDF_TOC" for volume in textbook_volumes
    )
    unreadable_count = sum(
        volume["catalog_status"] == "UNREADABLE_PDF" for volume in textbook_volumes
    )
    if review_required_count:
        warnings.append(f"教材目录待人工复核册数: {review_required_count}")
    if unreadable_count:
        warnings.append(f"不可读教材 PDF 册数: {unreadable_count}")

    report = {
        "status": "failed" if errors else "success",
        "document_count": len(manifest),
        "chunk_count": len(chunks),
        "database_chunk_count": db_count,
        "province_count": province_count,
        "textbook_pdf_count": len(textbook_volumes),
        "textbook_edition_count": len(textbook_editions),
        "textbook_review_required_count": review_required_count,
        "textbook_unreadable_count": unreadable_count,
        "errors": errors,
        "warnings": warnings,
    }
    (ROOT / "92_reports" / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
