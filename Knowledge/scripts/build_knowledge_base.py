#!/usr/bin/env python3
"""构建 AI Education 可追溯知识库。

流水线只下载 source_registry.json 中登记且域名在白名单内的官方公开 PDF，
并将原文按页提取、语义分块，最终生成 JSONL 与 SQLite FTS5 检索索引。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = KNOWLEDGE_ROOT / "00_manifest" / "source_registry.json"
RAW_ROOT = KNOWLEDGE_ROOT / "01_official_standards" / "raw"
PAGES_ROOT = KNOWLEDGE_ROOT / "90_processed" / "pages"
MARKDOWN_ROOT = KNOWLEDGE_ROOT / "90_processed" / "markdown"
CHUNKS_ROOT = KNOWLEDGE_ROOT / "90_processed" / "chunks"
INDEX_ROOT = KNOWLEDGE_ROOT / "91_indexes"
REPORT_ROOT = KNOWLEDGE_ROOT / "92_reports"
MANIFEST_PATH = KNOWLEDGE_ROOT / "00_manifest" / "document_manifest.csv"
CHUNKS_PATH = CHUNKS_ROOT / "all_chunks.jsonl"
DB_PATH = INDEX_ROOT / "knowledge.db"
BUILD_VERSION = "1.0.0"

MANIFEST_FIELDS = [
    "document_id",
    "file_name",
    "sha256",
    "title",
    "subject",
    "province",
    "exam_year",
    "paper_type",
    "document_type",
    "publisher",
    "edition",
    "volume",
    "isbn",
    "authority_level",
    "source_url",
    "copyright_status",
    "review_status",
    "effective_date",
    "expiry_date",
    "page_count",
    "ocr_required",
    "version",
    "file_size_bytes",
    "download_date",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\ufeff", "")
    lines = []
    for raw_line in value.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def validate_source(source: dict[str, Any], allowed_domains: set[str]) -> None:
    required = {
        "document_id",
        "title",
        "document_type",
        "subject",
        "source_url",
        "filename",
        "version",
        "authority_level",
        "copyright_status",
    }
    missing = sorted(required - source.keys())
    if missing:
        raise ValueError(f"{source.get('document_id', 'UNKNOWN')} 缺少字段: {missing}")
    parsed = urllib.parse.urlparse(source["source_url"])
    if parsed.scheme != "https" or parsed.hostname not in allowed_domains:
        raise ValueError(f"来源不在 HTTPS 白名单: {source['source_url']}")
    if source["copyright_status"] != "OFFICIAL_PUBLIC":
        raise ValueError(f"禁止自动下载非官方公开资源: {source['document_id']}")


def valid_pdf(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 512:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def download_pdf(source: dict[str, Any], retries: int = 3) -> Path:
    destination = RAW_ROOT / source["filename"]
    if valid_pdf(destination):
        return destination
    request = urllib.request.Request(
        source["source_url"],
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AI-Education-KB/1.0; research)",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        temporary = destination.with_suffix(".pdf.part")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if not data.startswith(b"%PDF-"):
                raise ValueError(f"响应不是 PDF，开头为 {data[:20]!r}")
            temporary.write_bytes(data)
            temporary.replace(destination)
            return destination
        except (OSError, urllib.error.URLError, ValueError) as exc:
            error = exc
            temporary.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError(f"下载失败 {source['document_id']}: {error}")


def split_long_text(text: str, limit: int = 950) -> list[str]:
    if len(text) <= limit:
        return [text]
    sentences = [part.strip() for part in re.split(r"(?<=[。！？；!?;])", text) if part.strip()]
    if len(sentences) == 1:
        return [text[index : index + limit] for index in range(0, len(text), limit)]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        pieces.append(current)
    return pieces


def extract_pdf(source: dict[str, Any], path: Path) -> tuple[list[dict[str, Any]], bool]:
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = normalized_text(page.extract_text() or "")
        except Exception as exc:  # pypdf 对个别异常字体可能失败，保留页级错误
            text = ""
            extraction_error = str(exc)
        else:
            extraction_error = None
        pages.append(
            {
                "document_id": source["document_id"],
                "page": page_number,
                "text": text,
                "char_count": len(text),
                "extraction_error": extraction_error,
            }
        )
    empty_ratio = sum(not page["text"] for page in pages) / max(len(pages), 1)
    return pages, empty_ratio > 0.20


def chunk_pages(source: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[tuple[int, str]] = []
    for page in pages:
        paragraphs = re.split(r"\n{1,}", page["text"])
        for paragraph in paragraphs:
            cleaned = paragraph.strip()
            if cleaned:
                for piece in split_long_text(cleaned):
                    units.append((page["page"], piece))

    grouped: list[tuple[int, int, str]] = []
    current: list[str] = []
    start_page: int | None = None
    end_page: int | None = None
    size = 0
    for page_number, unit in units:
        addition = len(unit) + (1 if current else 0)
        if current and size + addition > 1100 and size >= 280:
            grouped.append((start_page or page_number, end_page or page_number, "\n".join(current)))
            current, size, start_page = [], 0, None
        if start_page is None:
            start_page = page_number
        current.append(unit)
        size += addition
        end_page = page_number
    if current:
        grouped.append((start_page or 1, end_page or start_page or 1, "\n".join(current)))

    chunks = []
    for index, (page_start, page_end, content) in enumerate(grouped, start=1):
        chunks.append(
            make_chunk(
                chunk_id=f"{source['document_id']}-C{index:05d}",
                document_id=source["document_id"],
                title=source["title"],
                content=content,
                subject=source["subject"],
                document_type=source["document_type"],
                source_url=source["source_url"],
                authority_level=source["authority_level"],
                copyright_status=source["copyright_status"],
                review_status="AUTO_EXTRACTED_REVIEW_REQUIRED",
                page_start=page_start,
                page_end=page_end,
                metadata={"version": source["version"], "source_org": source.get("source_org")},
            )
        )
    return chunks


def make_chunk(
    *,
    chunk_id: str,
    document_id: str,
    title: str,
    content: str,
    subject: str,
    document_type: str,
    authority_level: str,
    copyright_status: str,
    review_status: str,
    source_url: str | None = None,
    province: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "title": title,
        "content": content,
        "subject": subject,
        "province": province,
        "document_type": document_type,
        "source_url": source_url,
        "page_start": page_start,
        "page_end": page_end,
        "authority_level": authority_level,
        "copyright_status": copyright_status,
        "review_status": review_status,
        "metadata": metadata or {},
    }


def curated_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    routes = load_json(KNOWLEDGE_ROOT / "catalogs" / "province_exam_routes.json")
    for province in routes["provinces"]:
        content = json.dumps(
            {"paper_system": routes["paper_system"], **province}, ensure_ascii=False, indent=2
        )
        chunks.append(
            make_chunk(
                chunk_id=f"CUR-PROVINCE-{province['slug'].upper()}",
                document_id="CUR-PROVINCE-ROUTES-2026",
                title=f"2026 {province['name']}高考科目与试卷路由",
                content=content,
                subject="all",
                province=province["slug"],
                document_type="PROVINCE_EXAM_ROUTE",
                source_url=province["official_url"],
                authority_level="A",
                copyright_status="OFFICIAL_PUBLIC",
                review_status="CURATED_REVIEW_REQUIRED",
                metadata={"exam_year": 2026},
            )
        )

    textbooks = load_json(KNOWLEDGE_ROOT / "catalogs" / "textbook_catalog.json")
    for index, item in enumerate(textbooks["subjects"], start=1):
        chunks.append(
            make_chunk(
                chunk_id=f"CUR-TEXTBOOK-{index:03d}",
                document_id="CUR-TEXTBOOK-CATALOG-2026",
                title=f"{item.get('name', item['subject'])}教材版本目录",
                content=json.dumps(item, ensure_ascii=False, indent=2),
                subject=item["subject"],
                document_type="TEXTBOOK_CATALOG",
                authority_level="B",
                copyright_status="LINK_ONLY",
                review_status="CURATED_REVIEW_REQUIRED",
                metadata={"notice": textbooks["copyright_notice"]},
            )
        )

    taxonomy = load_json(KNOWLEDGE_ROOT / "taxonomy" / "knowledge_taxonomy.json")
    for subject in taxonomy["subjects"]:
        for module in subject["modules"]:
            content = (
                f"学科：{subject['name']}\n模块：{module['name']}\n"
                f"核心素养：{'、'.join(subject['core_competencies'])}\n"
                f"知识主题：{'、'.join(module['topics'])}"
            )
            chunks.append(
                make_chunk(
                    chunk_id=f"CUR-TAXONOMY-{module['id']}",
                    document_id="CUR-KNOWLEDGE-TAXONOMY-2026",
                    title=f"{subject['name']} / {module['name']}",
                    content=content,
                    subject=subject["subject"],
                    document_type="KNOWLEDGE_TAXONOMY",
                    authority_level="B",
                    copyright_status="PUBLIC_DOMAIN",
                    review_status="CURATED_REVIEW_REQUIRED",
                    metadata={
                        "module_id": module["id"],
                        "taxonomy_version": taxonomy["taxonomy_version"],
                    },
                )
            )

    evaluation = load_json(KNOWLEDGE_ROOT / "curated" / "gaokao_evaluation_framework.json")
    chunks.append(
        make_chunk(
            chunk_id="CUR-GAOKAO-EVALUATION-FRAMEWORK",
            document_id="CUR-GAOKAO-EVALUATION-FRAMEWORK",
            title=evaluation["title"],
            content=json.dumps(evaluation, ensure_ascii=False, indent=2),
            subject="all",
            document_type="EVALUATION_FRAMEWORK",
            source_url=evaluation["source_url"],
            authority_level="A",
            copyright_status="OFFICIAL_PUBLIC",
            review_status="CURATED_REVIEW_REQUIRED",
        )
    )

    policy = load_json(KNOWLEDGE_ROOT / "curated" / "retrieval_policy.json")
    policy_parts = [
        (
            "EVIDENCE",
            "检索证据优先级与回答要求",
            {
                "evidence_priority": policy["evidence_priority"],
                "mandatory_filters": policy["mandatory_filters"],
                "answer_requirements": policy["answer_requirements"],
            },
        )
    ]
    policy_parts.extend(
        (rule["id"], f"检索路由规则 {rule['id']}", rule) for rule in policy["rules"]
    )
    for part_id, title, content in policy_parts:
        chunks.append(
            make_chunk(
                chunk_id=f"CUR-RETRIEVAL-POLICY-{part_id}",
                document_id="CUR-RETRIEVAL-POLICY",
                title=title,
                content=json.dumps(content, ensure_ascii=False, indent=2),
                subject="all",
                document_type="RETRIEVAL_POLICY",
                authority_level="A",
                copyright_status="PUBLIC_DOMAIN",
                review_status="CURATED_REVIEW_REQUIRED",
                metadata={"policy_version": policy["policy_version"]},
            )
        )
    return chunks


def write_markdown(source: dict[str, Any], pages: list[dict[str, Any]]) -> None:
    path = MARKDOWN_ROOT / f"{source['document_id']}.md"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {source['title']}\n\n")
        handle.write(f"- 来源：{source['source_url']}\n")
        handle.write(f"- 版本：{source['version']}\n")
        handle.write("- 状态：自动抽取，引用前需复核原 PDF 页码\n\n")
        for index, page in enumerate(pages, start=1):
            handle.write(f"## 第 {page['page']} 页\n\n")
            handle.write(page["text"] or "[本页未提取到文本，可能需要 OCR]")
            handle.write("\n" if index == len(pages) else "\n\n")


def search_terms(text: str) -> str:
    tokens: list[str] = []
    for sequence in re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9_]+", text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", sequence):
            if len(sequence) == 1:
                tokens.append(sequence)
            else:
                tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        else:
            tokens.append(sequence)
    return " ".join(dict.fromkeys(tokens))


def build_database(chunks: list[dict[str, Any]]) -> None:
    DB_PATH.unlink(missing_ok=True)
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE chunks (
              chunk_id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              subject TEXT NOT NULL,
              province TEXT,
              document_type TEXT NOT NULL,
              source_url TEXT,
              page_start INTEGER,
              page_end INTEGER,
              authority_level TEXT NOT NULL,
              copyright_status TEXT NOT NULL,
              review_status TEXT NOT NULL,
              metadata_json TEXT NOT NULL
            );
            CREATE INDEX idx_chunks_subject ON chunks(subject);
            CREATE INDEX idx_chunks_province ON chunks(province);
            CREATE INDEX idx_chunks_type ON chunks(document_type);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
              chunk_id UNINDEXED, title, content, search_terms,
              tokenize='unicode61 remove_diacritics 2'
            );
            """
        )
        for chunk in chunks:
            connection.execute(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    chunk["chunk_id"],
                    chunk["document_id"],
                    chunk["title"],
                    chunk["content"],
                    chunk["subject"],
                    chunk["province"],
                    chunk["document_type"],
                    chunk["source_url"],
                    chunk["page_start"],
                    chunk["page_end"],
                    chunk["authority_level"],
                    chunk["copyright_status"],
                    chunk["review_status"],
                    json.dumps(chunk["metadata"], ensure_ascii=False, separators=(",", ":")),
                ),
            )
            searchable = " ".join(
                [chunk["title"], chunk["content"], chunk["subject"], chunk["province"] or ""]
            )
            connection.execute(
                "INSERT INTO chunks_fts VALUES (?, ?, ?, ?)",
                (chunk["chunk_id"], chunk["title"], chunk["content"], search_terms(searchable)),
            )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()


def write_manifest(rows: list[dict[str, Any]]) -> None:
    with MANIFEST_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in MANIFEST_FIELDS} for row in rows)


def manifest_row(
    source: dict[str, Any], path: Path, pages: list[dict[str, Any]], ocr: bool
) -> dict[str, Any]:
    return {
        "document_id": source["document_id"],
        "file_name": path.name,
        "sha256": sha256_file(path),
        "title": source["title"],
        "subject": source["subject"],
        "province": "national",
        "exam_year": "",
        "paper_type": "",
        "document_type": source["document_type"],
        "publisher": source.get("source_org", ""),
        "edition": source["version"],
        "volume": "",
        "isbn": "",
        "authority_level": source["authority_level"],
        "source_url": source["source_url"],
        "copyright_status": source["copyright_status"],
        "review_status": "AUTO_EXTRACTED_REVIEW_REQUIRED",
        "effective_date": "",
        "expiry_date": "",
        "page_count": len(pages),
        "ocr_required": str(ocr).lower(),
        "version": source["version"],
        "file_size_bytes": path.stat().st_size,
        "download_date": date.today().isoformat(),
    }


def build(args: argparse.Namespace) -> int:
    started = datetime.now(UTC)
    for directory in (RAW_ROOT, PAGES_ROOT, MARKDOWN_ROOT, CHUNKS_ROOT, INDEX_ROOT, REPORT_ROOT):
        directory.mkdir(parents=True, exist_ok=True)

    registry = load_json(REGISTRY_PATH)
    allowed_domains = set(registry["allowed_domains"])
    sources = registry["sources"]
    if args.only:
        sources = [source for source in sources if source["document_id"] in args.only]
        unknown = args.only - {source["document_id"] for source in sources}
        if unknown:
            raise ValueError(f"未知 document_id: {sorted(unknown)}")

    all_chunks: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    documents_report: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for source in sources:
        print(f"[build] {source['document_id']} {source['title']}", flush=True)
        try:
            validate_source(source, allowed_domains)
            path = RAW_ROOT / source["filename"] if args.no_download else download_pdf(source)
            if not valid_pdf(path):
                raise FileNotFoundError(f"缺少有效 PDF: {path}")
            pages, ocr_required = extract_pdf(source, path)
            chunks = chunk_pages(source, pages)
            write_jsonl(PAGES_ROOT / f"{source['document_id']}.jsonl", pages)
            write_markdown(source, pages)
            all_chunks.extend(chunks)
            manifest_rows.append(manifest_row(source, path, pages, ocr_required))
            documents_report.append(
                {
                    "document_id": source["document_id"],
                    "pages": len(pages),
                    "chunks": len(chunks),
                    "characters": sum(page["char_count"] for page in pages),
                    "empty_pages": sum(not page["text"] for page in pages),
                    "ocr_required": ocr_required,
                    "sha256": sha256_file(path),
                }
            )
        except Exception as exc:  # 逐文档记录，完成后统一失败
            errors.append({"document_id": source.get("document_id", "UNKNOWN"), "error": str(exc)})
            print(f"[error] {source.get('document_id')}: {exc}", file=sys.stderr, flush=True)

    if not args.only:
        all_chunks.extend(curated_chunks())

    if all_chunks:
        duplicate_ids = [
            item for item, count in Counter(c["chunk_id"] for c in all_chunks).items() if count > 1
        ]
        if duplicate_ids:
            errors.append(
                {"document_id": "CHUNKS", "error": f"重复 chunk_id: {duplicate_ids[:10]}"}
            )
        write_jsonl(CHUNKS_PATH, all_chunks)
        build_database(all_chunks)
    write_manifest(manifest_rows)

    finished = datetime.now(UTC)
    report = {
        "build_version": BUILD_VERSION,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "status": "failed" if errors else "success",
        "source_registry_version": registry["registry_version"],
        "documents": documents_report,
        "document_count": len(documents_report),
        "chunk_count": len(all_chunks),
        "subject_counts": dict(sorted(Counter(c["subject"] for c in all_chunks).items())),
        "document_type_counts": dict(
            sorted(Counter(c["document_type"] for c in all_chunks).items())
        ),
        "review_status_counts": dict(
            sorted(Counter(c["review_status"] for c in all_chunks).items())
        ),
        "database": str(DB_PATH.relative_to(KNOWLEDGE_ROOT)),
        "errors": errors,
    }
    write_json(REPORT_ROOT / "build_report.json", report)
    print(
        json.dumps(
            {key: report[key] for key in ("status", "document_count", "chunk_count", "errors")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载、解析并索引官方公开教育资料")
    parser.add_argument("--no-download", action="store_true", help="只处理已存在的原始 PDF")
    parser.add_argument("--only", nargs="*", metavar="DOCUMENT_ID", help="仅处理指定文档（调试用）")
    args = parser.parse_args()
    args.only = set(args.only or [])
    return args


if __name__ == "__main__":
    raise SystemExit(build(parse_args()))
