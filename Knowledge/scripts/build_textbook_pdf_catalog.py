#!/usr/bin/env python3
"""Build a traceable textbook edition/chapter catalog from local PDF contents.

Only short bibliographic facts and table-of-contents headings are retained. The
textbooks themselves stay local and are never copied into the generated JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import tempfile
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF_ROOT = PROJECT_ROOT / "Knowledge" / "book" / "高中各版18科"
DEFAULT_OUTPUT = PROJECT_ROOT / "Knowledge" / "catalogs" / "textbook_pdf_catalog.json"

SOURCE_SUBJECTS = {
    "语文": ("chinese", "语文"),
    "数学": ("mathematics", "数学"),
    "英语": ("foreign_language", "英语"),
    "物理": ("physics", "物理"),
    "化学": ("chemistry", "化学"),
    "生物学": ("biology", "生物学"),
    "思想政治": ("ideology_politics", "思想政治"),
    "历史": ("history", "历史"),
    "地理": ("geography", "地理"),
    "信息技术": ("technology", "技术"),
    "通用技术": ("technology", "技术"),
}
SUBJECT_CODES = {
    "chinese": "CHN",
    "mathematics": "MATH",
    "foreign_language": "ENG",
    "physics": "PHY",
    "chemistry": "CHEM",
    "biology": "BIO",
    "ideology_politics": "POL",
    "history": "HIS",
    "geography": "GEO",
    "technology": "TECH",
}
KIND_PREFERENCES = {
    "语文": ["单元", "章", "课"],
    "数学": ["章", "单元", "专题"],
    "物理": ["章", "单元", "专题"],
    "化学": ["章", "专题", "单元"],
    "生物学": ["章", "单元", "专题"],
    "思想政治": ["课", "单元", "章"],
    "历史": ["单元", "课", "章"],
    "地理": ["章", "单元", "专题"],
    "信息技术": ["章", "单元", "项目", "专题"],
    "通用技术": ["章", "单元", "项目", "专题"],
}
TOC_RE = re.compile(r"目\s*录|CONTENTS|Contents", re.IGNORECASE)
CHINESE_HEADING_RE = re.compile(
    r"^第\s*([〇零一二三四五六七八九十百两0-9IVXLC]+)\s*(章|单元|课|篇)\s*(.*)$"
)
NUMBERED_HEADING_RE = re.compile(
    r"^(专题|项目)\s*([〇零一二三四五六七八九十百两0-9IVXLC]+)\s*(.*)$"
)
ENGLISH_UNIT_RE = re.compile(r"^(WELCOME\s+UNIT|UNIT\s*([0-9IVXLC]+))\b\s*(.*)$", re.I)
PAGE_ONLY_RE = re.compile(r"^(?:p\.?\s*)?[0-9ivxlc]+$", re.I)
LEADER_PAGE_RE = re.compile(r"[·•.。…/\-—_\s]+(?:p\.?)?\s*[0-9ivxlc]+\s*$", re.I)

_OCR_ENGINE: Any | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--no-ocr", action="store_true")
    return parser.parse_args()


def stable_id(prefix: str, value: str, length: int = 12) -> str:
    digest = hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:length]
    return f"{prefix}-{digest}".upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_line(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u3000", " ").replace("\ufeff", " ")
    value = re.sub(r"[\ue000-\uf8ff]", "", value)
    return re.sub(r"\s+", " ", value).strip(" |\t")


def clean_title(value: str) -> str:
    value = normalize_line(value)
    value = LEADER_PAGE_RE.sub("", value)
    value = re.sub(r"^[·•.。…/\-—_\s]+|[·•.。…/\-—_\s]+$", "", value)
    return value.strip()


def useful_title_line(value: str) -> bool:
    if not value or PAGE_ONLY_RE.fullmatch(value) or TOC_RE.fullmatch(value):
        return False
    if re.match(r"^(习题|复习题|本章小结|阅读材料|附录|APPENDICES|WORKBOOK)", value, re.I):
        return False
    return len(value) <= 90


def direct_pages(pdf: Path, max_pages: int) -> list[str]:
    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", str(max_pages), "-layout", str(pdf), "-"],
            check=False,
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return result.stdout.split("\f")[:max_pages]


def get_ocr_engine() -> Any:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def raw_heading_keys(subject_dir: str, page: str) -> set[str]:
    if subject_dir == "英语":
        candidates, _ = english_candidates([page])
    else:
        candidates, _ = chinese_candidates([page])
    return {normalize_line(item["number"]).upper() for item in candidates}


def ocr_pages(pdf: Path, max_pages: int, subject_dir: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="ai_education_toc_", dir="/tmp") as temp_dir:
        prefix = Path(temp_dir) / "page"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    "1",
                    "-l",
                    str(max_pages),
                    "-jpeg",
                    "-r",
                    "150",
                    str(pdf),
                    str(prefix),
                ],
                check=False,
                capture_output=True,
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        engine = get_ocr_engine()
        images = sorted(Path(temp_dir).glob("page-*.jpg"))
        pages = [""] * len(images)
        toc_seen = False
        known_headings: set[str] = set()
        pages_without_new_heading = 0
        for index, image in enumerate(images):
            result, _ = engine(str(image))
            text = "\n".join(item[1] for item in (result or []))
            pages[index] = text
            if TOC_RE.search(text):
                toc_seen = True
            page_headings = raw_heading_keys(subject_dir, text)
            new_headings = page_headings - known_headings
            known_headings.update(page_headings)
            if toc_seen and new_headings:
                pages_without_new_heading = 0
            elif toc_seen:
                pages_without_new_heading += 1
            if toc_seen and len(known_headings) >= 2 and pages_without_new_heading >= 2:
                break
        return pages


def toc_window(pages: list[str]) -> tuple[list[tuple[int, str]], list[int]]:
    toc_indexes = [index for index, page in enumerate(pages) if TOC_RE.search(page)]
    start = toc_indexes[0] if toc_indexes else 0
    end = min(len(pages), start + 10)
    return list(enumerate(pages[start:end], start=start + 1)), [index + 1 for index in toc_indexes]


def next_title(lines: list[str], start: int) -> str:
    for value in lines[start : start + 4]:
        candidate = clean_title(value)
        if useful_title_line(candidate) and not (
            CHINESE_HEADING_RE.match(candidate) or NUMBERED_HEADING_RE.match(candidate)
        ):
            return candidate
    return ""


def chinese_candidates(pages: list[str]) -> tuple[list[dict[str, Any]], list[int]]:
    selected_pages, toc_pages = toc_window(pages)
    candidates: list[dict[str, Any]] = []
    for pdf_page, page in selected_pages:
        lines = [normalize_line(line) for line in page.splitlines()]
        for index, line in enumerate(lines):
            match = CHINESE_HEADING_RE.match(line)
            if match:
                number, kind, raw_title = match.groups()
            else:
                numbered = NUMBERED_HEADING_RE.match(line)
                if not numbered:
                    continue
                kind, number, raw_title = numbered.groups()
            title = clean_title(raw_title) or next_title(lines, index + 1)
            candidates.append(
                {
                    "number": (
                        f"第{number}{kind}" if kind not in {"专题", "项目"} else f"{kind}{number}"
                    ),
                    "kind": kind,
                    "title": title or f"{kind}{number}",
                    "pdf_page": pdf_page,
                    "raw_heading": line[:180],
                }
            )
    return candidates, toc_pages


def english_candidates(pages: list[str]) -> tuple[list[dict[str, Any]], list[int]]:
    selected_pages, toc_pages = toc_window(pages)
    candidates: list[dict[str, Any]] = []
    for pdf_page, page in selected_pages:
        lines = [normalize_line(line) for line in page.splitlines()]
        for index, line in enumerate(lines):
            match = ENGLISH_UNIT_RE.match(line)
            if not match:
                if line.upper() == "UNIT" and index and lines[index - 1].upper() == "WELCOME":
                    candidates.append(
                        {
                            "number": "WELCOME UNIT",
                            "kind": "unit",
                            "title": "Welcome Unit",
                            "pdf_page": pdf_page,
                            "raw_heading": "WELCOME UNIT",
                        }
                    )
                continue
            label, number, remainder = match.groups()
            unit_number = "WELCOME" if label.upper().startswith("WELCOME") else str(number)
            title = ""
            remainder = clean_title(remainder)
            if remainder and remainder.upper() == remainder and len(remainder) <= 50:
                title = remainder.title()
            if not title:
                upper_parts: list[str] = []
                for value in lines[index + 1 : index + 8]:
                    value = clean_title(value)
                    if not value or PAGE_ONLY_RE.fullmatch(value):
                        continue
                    letters = re.sub(r"[^A-Za-z]", "", value)
                    if letters and value.upper() == value and len(value) <= 45:
                        upper_parts.append(value)
                        if len(upper_parts) == 2:
                            break
                title = " ".join(upper_parts).title()
            candidates.append(
                {
                    "number": "WELCOME UNIT" if unit_number == "WELCOME" else f"UNIT {unit_number}",
                    "kind": "unit",
                    "title": title
                    or ("Welcome Unit" if unit_number == "WELCOME" else f"Unit {unit_number}"),
                    "pdf_page": pdf_page,
                    "raw_heading": line[:180],
                }
            )
    return candidates, toc_pages


def choose_candidates(subject_dir: str, pages: list[str]) -> tuple[list[dict[str, Any]], list[int]]:
    if subject_dir == "英语":
        candidates, toc_pages = english_candidates(pages)
    else:
        candidates, toc_pages = chinese_candidates(pages)
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            by_kind.setdefault(candidate["kind"], []).append(candidate)
        preference = KIND_PREFERENCES.get(subject_dir, ["章", "单元", "课", "专题", "项目"])
        candidates = next(
            (by_kind[kind] for kind in preference if len(by_kind.get(kind, [])) >= 2),
            max(by_kind.values(), key=len, default=[]),
        )

    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_line(candidate["number"]).upper()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(candidate)
    return deduplicated, toc_pages


def volume_label(pdf: Path, source_subject: str) -> str:
    label = pdf.stem
    label = re.sub(r"^普通高中教科书[·・]?", "", label)
    label = re.sub(rf"^{re.escape(source_subject)}(?:（[^）]+）)?\s*", "", label)
    return normalize_line(label)


def inspect_pdf(task: tuple[str, Path, Path, int, bool]) -> dict[str, Any]:
    source_subject, pdf, pdf_root, max_pages, no_ocr = task
    target_subject, _ = SOURCE_SUBJECTS[source_subject]
    relative = pdf.relative_to(PROJECT_ROOT).as_posix()
    edition_dir = pdf.parent.name
    edition_label, publisher = (
        edition_dir.rsplit("-", 1) if "-" in edition_dir else (edition_dir, "待版权页复核")
    )
    if target_subject == "technology":
        edition_display = f"{source_subject}｜{edition_label}"
    else:
        edition_display = edition_label
    edition_key = f"{source_subject}/{edition_dir}"
    volume_key = pdf.relative_to(pdf_root).as_posix()

    try:
        reader = PdfReader(str(pdf))
        page_count = len(reader.pages)
    except Exception:  # noqa: BLE001 - the catalog must retain unreadable local sources
        page_count = 0
    pages = direct_pages(pdf, min(max_pages, page_count)) if page_count else []
    chapters, toc_pages = choose_candidates(source_subject, pages)
    method = "PDF_TEXT_TOC"
    direct_characters = sum(len(normalize_line(page)) for page in pages)

    # A PDF can expose valid chapter headings while its stylized “目录” glyph is
    # not text-searchable. OCR only when text/heading evidence is insufficient;
    # otherwise retain the extracted headings with an explicit review flag.
    should_ocr = page_count > 0 and not no_ocr and (direct_characters < 500 or len(chapters) < 2)
    if should_ocr:
        # Textbook contents are normally in the front matter. Capping OCR keeps
        # full-catalog rebuilds practical while direct text can still use more pages.
        try:
            scanned_pages = ocr_pages(pdf, min(max_pages, page_count, 14), source_subject)
        except Exception:  # noqa: BLE001 - retain direct evidence if OCR fails
            scanned_pages = []
        ocr_chapters, ocr_toc_pages = choose_candidates(source_subject, scanned_pages)
        direct_score = (len(chapters), sum(bool(item["title"]) for item in chapters))
        ocr_score = (len(ocr_chapters), sum(bool(item["title"]) for item in ocr_chapters))
        if ocr_score > direct_score:
            chapters, toc_pages = ocr_chapters, ocr_toc_pages
            method = "PDF_OCR_TOC"

    verification_status = "VERIFIED_FROM_PDF_TOC"
    if not chapters and page_count:
        verification_status = "VOLUME_ONLY_REVIEW_REQUIRED"
        chapters = [
            {
                "number": "全册",
                "kind": "volume",
                "title": f"{volume_label(pdf, source_subject)}（目录待人工复核）",
                "pdf_page": 1,
                "raw_heading": pdf.name,
            }
        ]
        method = "PDF_FILENAME"
    elif not chapters:
        verification_status = "UNREADABLE_PDF"
        method = "PDF_UNREADABLE"
    elif not toc_pages:
        verification_status = "HEADING_EXTRACTED_REVIEW_REQUIRED"

    volume_id = stable_id(f"TB-{SUBJECT_CODES[target_subject]}-V", volume_key)
    for index, chapter in enumerate(chapters, start=1):
        chapter["id"] = f"{volume_id}-C{index:02d}"
        chapter["evidence"] = {
            "source_pdf": relative,
            "pdf_page": chapter.pop("pdf_page"),
            "raw_heading": chapter.pop("raw_heading"),
            "extraction_method": method,
        }

    return {
        "target_subject": target_subject,
        "target_label": SOURCE_SUBJECTS[source_subject][1],
        "source_subject": source_subject,
        "edition_key": edition_key,
        "edition_id": stable_id(f"TB-{SUBJECT_CODES[target_subject]}-E", edition_key),
        "edition_label": edition_display,
        "publisher": publisher,
        "volume": {
            "id": volume_id,
            "label": volume_label(pdf, source_subject),
            "source_pdf": relative,
            "source_sha256": sha256_file(pdf),
            "source_size_bytes": pdf.stat().st_size,
            "page_count": page_count,
            "toc_pdf_pages": toc_pages,
            "catalog_status": verification_status,
            "extraction_method": method,
            "chapters": chapters,
        },
    }


def build_catalog(pdf_root: Path, *, workers: int, max_pages: int, no_ocr: bool) -> dict[str, Any]:
    tasks: list[tuple[str, Path, Path, int, bool]] = []
    for source_subject in SOURCE_SUBJECTS:
        subject_root = pdf_root / source_subject
        tasks.extend(
            (source_subject, pdf, pdf_root, max_pages, no_ocr)
            for pdf in sorted(subject_root.rglob("*.pdf"))
        )

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(inspect_pdf, task): task[1] for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            pdf = futures[future]
            try:
                results.append(future.result())
                print(f"[{completed}/{len(tasks)}] {pdf.relative_to(pdf_root)}", flush=True)
            except Exception as exc:  # noqa: BLE001 - report every source failure in the catalog
                print(f"ERROR {pdf}: {exc}", flush=True)

    subjects: dict[str, dict[str, Any]] = {}
    for result in sorted(results, key=lambda item: (item["target_subject"], item["edition_key"])):
        subject = subjects.setdefault(
            result["target_subject"],
            {
                "id": result["target_subject"],
                "label": result["target_label"],
                "editions": {},
            },
        )
        edition = subject["editions"].setdefault(
            result["edition_key"],
            {
                "id": result["edition_id"],
                "label": result["edition_label"],
                "publisher": result["publisher"],
                "catalog_status": "LOCAL_PDF_TOC_CATALOG",
                "source_type": "USER_PROVIDED_LOCAL_PDF",
                "volumes": [],
            },
        )
        edition["volumes"].append(result["volume"])

    output_subjects: list[dict[str, Any]] = []
    for subject in subjects.values():
        editions = list(subject.pop("editions").values())
        for edition in editions:
            edition["volumes"].sort(key=lambda item: item["source_pdf"])
            edition["pdf_count"] = len(edition["volumes"])
            edition["chapter_count"] = sum(len(item["chapters"]) for item in edition["volumes"])
            edition["review_required_volume_count"] = sum(
                item["catalog_status"] != "VERIFIED_FROM_PDF_TOC" for item in edition["volumes"]
            )
        subject["editions"] = editions
        output_subjects.append(subject)

    return {
        "schema_version": "1.0.0",
        "generated_from": "Knowledge/book/高中各版18科",
        "source_scope": "用户提供的本地教材PDF；目录事实可用于选项，正文不得重新分发",
        "methodology": {
            "direct": "优先读取PDF前20页目录文本",
            "ocr": "扫描版使用RapidOCR识别目录页",
            "fallback": "无法确认目录时只生成带复核标记的全册选项，不虚构章节",
        },
        "pdf_count": len(results),
        "subjects": output_subjects,
    }


def main() -> None:
    args = parse_args()
    catalog = build_catalog(
        args.pdf_root.resolve(),
        workers=args.workers,
        max_pages=args.max_pages,
        no_ocr=args.no_ocr,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output} with {catalog['pdf_count']} PDFs")


if __name__ == "__main__":
    main()
