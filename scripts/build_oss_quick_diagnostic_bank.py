#!/usr/bin/env python3
"""Build traceable quick-diagnostic JSON shards from licensed OSS DOCX sources.

This is an offline build step.  It streams one source object at a time, extracts
only four-option questions with a source-provided answer, rejects unresolved
figures/formulas, and writes compact per-subject shards.  Online API requests
read those shards and never parse the raw corpus.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_exam_diagnosis_bank import (  # noqa: E402
    SourceQuestion,
    extract_source_questions,
    plain_text,
)

from ai_education.services.oss_quick_diagnostic_bank import (  # noqa: E402
    SCHEMA_VERSION,
    AlibabaCloudOssObjectReader,
)

DEFAULT_CATALOG = ROOT / "Knowledge" / "catalogs" / "question_bank_catalog.json"
DEFAULT_OUTPUT = ROOT / "data" / "runtime" / "oss_quick_diagnostic_build"
DEFAULT_BUCKET = "mwg-ai-knowledge-2026"
DEFAULT_REGION = "cn-hangzhou"
DEFAULT_ENDPOINT = "https://oss-cn-hangzhou-internal.aliyuncs.com"
DEFAULT_ROLE = "EcsOssKnowledgeReadRole"
DEFAULT_RAW_PREFIX = "knowledge/raw/title/2026五年高考三年模拟53A、B版新高考全套资料"
DEFAULT_OUTPUT_PREFIX = "knowledge/processed/quick_diagnostic/v1"
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_PROMPT_CHARS = 6000
MAX_OPTION_CHARS = 1200
IMG_MARKER = "{{IMG:"
NOISE = re.compile(
    r"(?:2026|五年高考三年模拟|五三|5·3|A版|B版|新高考|训练册|精练册|"
    r"试题WORD|word|Word|专题检测|真题分类|教师版|学生版)",
    re.IGNORECASE,
)

PRODUCT_MARKERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("新高考 语文", ".语文.5·3", "/语文/"), "chinese"),
    (("新高考 数学", ".数学.5·3", "/数学/"), "mathematics"),
    (("新高考 英语", ".英语.5·3", "/英语/"), "foreign_language"),
    (("新高考 物理", ".物理.5·3", "/物理/"), "physics"),
    (("新高考 化学", ".化学.5·3", "/化学/"), "chemistry"),
    (("新高考 生物", ".生物.5·3", "/生物/"), "biology"),
    (("新高考 历史", ".历史.5·3", "/历史/"), "history"),
    (("新高考 地理", ".地理.5·3", "/地理/"), "geography"),
    (("新高考 政治", ".政治.5·3", "/政治/"), "ideology_politics"),
)


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("题源目录缺少 items")
    return [item for item in items if isinstance(item, dict)]


def path_subject(relative_path: str, catalog_subject: str) -> str:
    normalized = f"/{relative_path.replace(chr(92), '/')}/"
    for markers, subject in PRODUCT_MARKERS:
        if any(marker in normalized for marker in markers):
            return subject
    return catalog_subject


def source_items(
    items: Iterable[dict[str, Any]], subjects: set[str], max_files: int
) -> list[dict[str, Any]]:
    result = []
    for item in items:
        relative_path = str(item.get("relative_path") or "")
        subject = path_subject(relative_path, str(item.get("subject") or ""))
        if (
            item.get("file_type") != "docx"
            or subject not in subjects
            or int(item.get("file_size") or 0) > MAX_SOURCE_BYTES
            or relative_path.startswith("~$")
        ):
            continue
        result.append({**item, "subject": subject})
    result.sort(
        key=lambda item: (
            0 if any(marker in str(item["relative_path"]) for marker in ("带答案", "答案")) else 1,
            str(item["relative_path"]),
        )
    )
    return result[:max_files] if max_files else result


def docx_has_answer_marker(payload: bytes) -> bool:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            text = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except (BadZipFile, KeyError, OSError):
        return False
    visible_text = re.sub(r"<[^>]+>", "", text)
    # This is only a cheap prefilter.  The source parser below still requires an
    # explicit answer marker and a valid A/B/C/D answer before exporting a question.
    return "答案" in visible_text


def clean_topic(relative_path: str) -> str:
    path = Path(relative_path)
    candidates = [path.stem, *reversed(path.parts[:-1])]
    for candidate in candidates:
        value = NOISE.sub(" ", candidate)
        value = re.sub(r"^[\d_ .、．：:-]+", "", value)
        value = re.sub(r"[\s　]+", " ", value).strip(" -_（）()")
        if len(value) >= 3:
            return value[:160]
    return "学科综合"


def source_kind(relative_path: str) -> str:
    if any(marker in relative_path for marker in ("模拟", "预测", "专题检测")):
        return "licensed_mock_question"
    return "licensed_textbook_practice"


def normalized_prompt(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value).lower()


def build_question(
    source: SourceQuestion,
    *,
    subject: str,
    relative_path: str,
) -> dict[str, Any] | None:
    if (
        source.question_type != "multiple_choice"
        or not source.correct_option
        or source.correct_option not in "ABCD"
    ):
        return None
    markup = source.stem_markup + "".join(source.options_markup)
    if IMG_MARKER in markup:
        return None
    prompt = plain_text(source.stem_markup)
    options = [plain_text(item) for item in source.options_markup]
    if (
        not 8 <= len(prompt) <= MAX_PROMPT_CHARS
        or len(options) != 4
        or any(not option or len(option) > MAX_OPTION_CHARS for option in options)
        or len(set(options)) != 4
        or "【答案】" in prompt
    ):
        return None
    topic = clean_topic(relative_path)
    tags = list(dict.fromkeys([*source.knowledge_tags, topic]))[:6]
    focus = next((tag for tag in tags if not tag.endswith("综合")), topic)
    explanation = plain_text(source.analysis_markup or source.answer_markup)
    explanation = re.sub(r"^[ABCD](?:[.．、，。：:]|\s)+", "", explanation).strip()
    if len(explanation) < 8:
        explanation = f"本题标准答案为 {source.correct_option}，请结合题干条件与“{focus}”知识复核。"
    source_locator = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    source_question_id = (
        "oss53_"
        + hashlib.sha256(
            f"{relative_path}:{source.original_number}:{normalized_prompt(prompt)}".encode()
        ).hexdigest()[:22]
    )
    return {
        "knowledge_focus": focus,
        "difficulty": max(0.2, min(float(source.difficulty), 0.9)),
        "prompt": prompt,
        "prompt_html": source.stem_markup,
        "options": options,
        "options_html": source.options_markup,
        "correct_option": "ABCD".index(source.correct_option),
        "explanation": explanation[:4000],
        "source_question_id": source_question_id,
        "source_paper_id": f"oss53_{source_locator[:18]}",
        "source_title": Path(relative_path).stem[:180],
        "source_document_sha256": source.source_hash,
        "source_locator_sha256": source_locator,
        "source_kind": source_kind(relative_path),
        "knowledge_tags": tags,
        "search_text": " ".join([focus, topic, *tags, prompt]),
    }


def source_bytes(
    item: dict[str, Any],
    *,
    source_dir: Path | None,
    reader: AlibabaCloudOssObjectReader | None,
    raw_prefix: str,
) -> bytes:
    relative_path = str(item["relative_path"])
    if source_dir is not None:
        return (source_dir / relative_path).read_bytes()
    assert reader is not None
    return reader.get_bytes(f"{raw_prefix.strip('/')}/{relative_path}", max_bytes=MAX_SOURCE_BYTES)


def extract_bank(
    candidates: list[dict[str, Any]],
    *,
    source_dir: Path | None,
    reader: AlibabaCloudOssObjectReader | None,
    raw_prefix: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    questions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_prompts: dict[str, set[str]] = defaultdict(set)
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="mwg-oss-qb-") as temporary_dir:
        temporary_root = Path(temporary_dir)
        for index, item in enumerate(candidates, start=1):
            relative_path = str(item["relative_path"])
            subject = str(item["subject"])
            try:
                payload = source_bytes(
                    item,
                    source_dir=source_dir,
                    reader=reader,
                    raw_prefix=raw_prefix,
                )
                stats["source_bytes"] += len(payload)
                if not docx_has_answer_marker(payload):
                    stats["documents_without_answer_marker"] += 1
                    continue
                source_path = temporary_root / f"{index:06d}.docx"
                source_path.write_bytes(payload)
                extracted = extract_source_questions(subject, source_path)
                stats["documents_with_answer_marker"] += 1
                stats["questions_extracted"] += len(extracted)
                for source in extracted:
                    question = build_question(
                        source,
                        subject=subject,
                        relative_path=relative_path,
                    )
                    if question is None:
                        stats["questions_rejected"] += 1
                        continue
                    key = normalized_prompt(str(question["prompt"]))
                    if key in seen_prompts[subject]:
                        stats["duplicates_removed"] += 1
                        continue
                    seen_prompts[subject].add(key)
                    questions[subject].append(question)
                    stats["questions_accepted"] += 1
            except Exception as exc:
                stats["documents_failed"] += 1
                if len(errors) < 100:
                    errors.append(
                        {
                            "source_locator_sha256": hashlib.sha256(
                                relative_path.encode("utf-8")
                            ).hexdigest(),
                            "error": str(exc)[:240],
                        }
                    )
            if index % 25 == 0 or index == len(candidates):
                print(
                    f"processed={index}/{len(candidates)} accepted={stats['questions_accepted']} "
                    f"answer_docs={stats['documents_with_answer_marker']}",
                    flush=True,
                )
    return dict(questions), {"counts": dict(stats), "errors": errors}


def encode_outputs(
    questions: dict[str, list[dict[str, Any]]], output_dir: Path
) -> tuple[dict[str, bytes], dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat()
    artifacts: dict[str, bytes] = {}
    subject_entries: dict[str, dict[str, Any]] = {}
    for subject, items in sorted(questions.items()):
        payload = {
            "schema_version": SCHEMA_VERSION,
            "subject": subject,
            "generated_at": generated_at,
            "questions": items,
        }
        compressed = gzip.compress(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            compresslevel=9,
            mtime=0,
        )
        relative_key = f"subjects/{subject}.json.gz"
        artifacts[relative_key] = compressed
        subject_entries[subject] = {
            "object_key": relative_key,
            "sha256": hashlib.sha256(compressed).hexdigest(),
            "question_count": len(items),
            "content_encoding": "gzip",
        }
        target = output_dir / relative_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(compressed)

    version_input = "\n".join(
        f"{subject}:{entry['sha256']}:{entry['question_count']}"
        for subject, entry in sorted(subject_entries.items())
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "bank_version": hashlib.sha256(version_input.encode()).hexdigest()[:20],
        "generated_at": generated_at,
        "subject_count": len(subject_entries),
        "question_count": sum(entry["question_count"] for entry in subject_entries.values()),
        "subjects": subject_entries,
    }
    return artifacts, manifest


def write_manifest(
    output_dir: Path,
    output_prefix: str,
    artifacts: dict[str, bytes],
    manifest: dict[str, Any],
) -> bytes:
    prefix = output_prefix.strip("/")
    for entry in manifest["subjects"].values():
        entry["object_key"] = f"{prefix}/{entry['object_key']}"
    payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    (output_dir / "manifest.json").write_bytes(payload)
    artifacts["manifest.json"] = payload
    return payload


def upload_outputs(
    reader: AlibabaCloudOssObjectReader,
    *,
    output_prefix: str,
    artifacts: dict[str, bytes],
) -> None:
    prefix = output_prefix.strip("/")
    # Upload immutable shards first and publish the manifest last as the atomic switch.
    ordered = sorted(key for key in artifacts if key != "manifest.json") + ["manifest.json"]
    for relative_key in ordered:
        content_type = "application/gzip" if relative_key.endswith(".gz") else "application/json"
        key = f"{prefix}/{relative_key}"
        etag = reader.put_bytes(key, artifacts[relative_key], content_type=content_type)
        print(f"uploaded={key} etag={etag}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--ecs-role-name", default=DEFAULT_ROLE)
    parser.add_argument("--raw-prefix", default=DEFAULT_RAW_PREFIX)
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument(
        "--subjects",
        default=",".join(subject for _, subject in PRODUCT_MARKERS),
        help="Comma-separated internal subject IDs",
    )
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--upload", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    subjects = {item.strip() for item in args.subjects.split(",") if item.strip()}
    items = source_items(load_catalog(args.catalog), subjects, max(0, args.max_files))
    if not items:
        raise RuntimeError("没有找到可处理的 DOCX 题源")
    reader = None
    if args.source_dir is None or args.upload:
        reader = AlibabaCloudOssObjectReader(
            bucket=args.bucket,
            region=args.region,
            endpoint=args.endpoint,
            ecs_role_name=args.ecs_role_name,
        )
    questions, report = extract_bank(
        items,
        source_dir=args.source_dir,
        reader=reader,
        raw_prefix=args.raw_prefix,
    )
    artifacts, manifest = encode_outputs(questions, args.output)
    write_manifest(args.output, args.output_prefix, artifacts, manifest)
    report.update(
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": manifest["generated_at"],
            "source_document_count": len(items),
            "subjects": {
                subject: len(subject_questions)
                for subject, subject_questions in sorted(questions.items())
            },
            "manifest": manifest,
        }
    )
    (args.output / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not questions:
        raise RuntimeError("没有抽取到通过质量门禁的四选一题目")
    if args.upload:
        assert reader is not None
        upload_outputs(reader, output_prefix=args.output_prefix, artifacts=artifacts)
    print(
        f"complete subjects={len(questions)} questions={manifest['question_count']} "
        f"output={args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
