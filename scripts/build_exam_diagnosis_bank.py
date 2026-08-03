#!/usr/bin/env python3
"""Build traceable diagnostic papers from local Gaokao answer DOCX files.

The script never invents questions or answers. Every exported question stores its
source document, original number, document hash and answer marker. Equations and
figures embedded in DOCX are copied into the diagnose asset directory.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from exam_svg_utils import browser_safe_svg_bytes


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Knowledge" / "Exam" / "高考真题"
OUTPUT_ROOT = SOURCE_ROOT / "diagnose"
WMF_CONVERTER = ROOT / "tools" / "libwmf-bin" / "usr" / "bin" / "wmf2svg"

SUBJECTS = {
    "chinese": ("语文", "语文真题试卷"),
    "mathematics": ("数学", "数学真题试卷"),
    "foreign_language": ("英语", "英语真题试卷"),
    "physics": ("物理", "物理真题试卷"),
    "chemistry": ("化学", "化学真题试卷"),
    "biology": ("生物", "生物真题试卷"),
    "history": ("历史", "历史真题试卷"),
    "geography": ("地理", "地理真题试卷"),
    "ideology_politics": ("政治", "政治真题试卷"),
    "technology": ("技术", "技术真题试卷"),
}

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
}
RID = f"{{{NS['r']}}}embed"
RID_LEGACY = f"{{{NS['r']}}}id"
QUESTION_START = re.compile(r"^\s*(\d{1,2})\s*[.．、]\s*(.+)")
ANSWER_MARKER = re.compile(r"【\s*答案\s*】")
ANALYSIS_MARKER = re.compile(r"【\s*(?:解析|分析|详解|解答|点睛)\s*】")
OPTION_MARKER = re.compile(r"(?<![A-Za-z])([ABCD])\s*[.．、:：]\s*")
SECTION_HEADING = re.compile(
    r"^\s*(?:[（(][一二三四五六七八九十]+[）)]|[一二三四五六七八九十]+\s*[、.]|第[一二三四五六七八九十]+部分|Part\s+[A-Z])",
    re.IGNORECASE,
)
READING_CONTEXT_INTRO = re.compile(
    r"^\s*(?:阅读(?:下面|下列|以上|材料|图文材料)|阅读材料|根据(?:以下|下列)材料|.+据此完成(?:下面|下列)小题)",
)
EXAM_DIRECTION = re.compile(
    r"^\s*(?:\d{1,2}\s*[.．、]\s*)?(?:答题时请|请按照题号顺序|作图可先|保持卡面清洁|考试结束后|必须使用|请将答案)",
)
MATERIAL_REFERENCE = re.compile(
    r"(?:下列对(?:文本|原文|文章)|(?<!一)文中|原文中|材料[一二三四]?(?:相关|中)|根据图|上述材料|这首(?:诗|词)|该诗|该文(?!学))",
)
TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r"\{\{IMG:([^}]+)}}")


@dataclass(slots=True)
class Paragraph:
    markup: str
    plain: str


@dataclass(slots=True)
class SourceQuestion:
    subject: str
    source_path: Path
    source_hash: str
    original_number: int
    question_type: str
    stem_markup: str
    options_markup: list[str]
    correct_option: str | None
    answer_markup: str
    analysis_markup: str
    knowledge_tags: list[str]
    difficulty: float


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_space(value: str) -> str:
    return re.sub(r"[\s\u3000]+", " ", value).strip()


def plain_text(markup: str) -> str:
    value = IMG_RE.sub(" [图或公式] ", markup)
    return clean_space(html.unescape(TAG_RE.sub(" ", value)))


class DocxReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.archive = zipfile.ZipFile(path)
        self.relationships = self._relationships()
        self.document = ET.fromstring(self.archive.read("word/document.xml"))

    def close(self) -> None:
        self.archive.close()

    def _relationships(self) -> dict[str, str]:
        root = ET.fromstring(self.archive.read("word/_rels/document.xml.rels"))
        return {
            item.attrib["Id"]: item.attrib["Target"]
            for item in root
            if item.attrib.get("Target")
        }

    def paragraphs(self) -> list[Paragraph]:
        body = self.document.find("w:body", NS)
        if body is None:
            return []
        result: list[Paragraph] = []
        for child in body:
            if local_name(child.tag) == "p":
                rendered = self._render(child)
                if rendered.plain:
                    result.append(rendered)
            elif local_name(child.tag) == "tbl":
                for row in child.findall(".//w:tr", NS):
                    cells: list[str] = []
                    for cell in row.findall("w:tc", NS):
                        chunks = [self._render(p).markup for p in cell.findall("w:p", NS)]
                        cells.append(" ".join(chunk for chunk in chunks if chunk))
                    markup = " ｜ ".join(cells)
                    if plain_text(markup):
                        result.append(Paragraph(markup=markup, plain=plain_text(markup)))
        return result

    def _render(self, element: ET.Element) -> Paragraph:
        chunks: list[str] = []
        seen_images: set[str] = set()
        for node in element.iter():
            name = local_name(node.tag)
            if name == "t" and node.text:
                chunks.append(html.escape(node.text))
            elif name == "tab":
                chunks.append("　")
            elif name in {"br", "cr"}:
                chunks.append("<br>")
            elif name == "blip":
                rid = node.attrib.get(RID)
                if rid and rid not in seen_images:
                    chunks.append(f"{{{{IMG:{rid}}}}}")
                    seen_images.add(rid)
            elif name == "imagedata":
                rid = node.attrib.get(RID_LEGACY)
                if rid and rid not in seen_images:
                    chunks.append(f"{{{{IMG:{rid}}}}}")
                    seen_images.add(rid)
        markup = clean_markup("".join(chunks))
        return Paragraph(markup=markup, plain=plain_text(markup))

    def image_bytes(self, rid: str) -> tuple[bytes, str] | None:
        target = self.relationships.get(rid)
        if not target:
            return None
        archive_path = str(Path("word") / target).replace("word/../", "")
        try:
            data = self.archive.read(archive_path)
        except KeyError:
            return None
        suffix = Path(target).suffix.lower() or ".png"
        if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".emf", ".wmf"}:
            suffix = ".png"
        return data, suffix


def clean_markup(value: str) -> str:
    value = re.sub(r"(?:<br>){3,}", "<br><br>", value)
    value = value.replace("\x00", "")
    return value.strip()


KNOWLEDGE_KEYWORDS: dict[str, tuple[tuple[str, str], ...]] = {
    "chinese": (("文言", "文言文阅读"), ("诗", "古代诗歌阅读"), ("作文", "写作"), ("病句", "语言文字运用"), ("小说", "文学类文本阅读"), ("论述", "信息类文本阅读")),
    "mathematics": (("函数", "函数"), ("数列", "数列"), ("向量", "平面向量"), ("椭圆", "圆锥曲线"), ("概率", "概率统计"), ("立体", "立体几何"), ("三角", "三角函数"), ("导数", "导数"), ("集合", "集合")),
    "foreign_language": (("阅读", "阅读理解"), ("完形", "完形填空"), ("语法", "语言运用"), ("写作", "书面表达"), ("听力", "听力理解")),
    "physics": (("电场", "电场"), ("磁场", "磁场"), ("电路", "电路"), ("动量", "动量"), ("机械能", "机械能"), ("实验", "物理实验"), ("运动", "运动与力")),
    "chemistry": (("有机", "有机化学"), ("电化学", "电化学"), ("平衡", "化学平衡"), ("实验", "化学实验"), ("元素", "元素化学"), ("结构", "物质结构")),
    "biology": (("遗传", "遗传与进化"), ("细胞", "细胞"), ("生态", "生态系统"), ("实验", "生物实验"), ("免疫", "稳态与调节"), ("代谢", "细胞代谢")),
    "history": (("中国古代", "中国古代史"), ("近代", "近代史"), ("现代", "现代史"), ("世界", "世界史"), ("改革", "改革与制度")),
    "geography": (("气候", "大气与气候"), ("地形", "地貌"), ("人口", "人口与城市"), ("农业", "农业地理"), ("工业", "工业地理"), ("区域", "区域发展"), ("水", "水循环")),
    "ideology_politics": (("经济", "经济与社会"), ("政治", "政治与法治"), ("哲学", "哲学与文化"), ("文化", "哲学与文化"), ("国际", "当代国际政治与经济"), ("法律", "法律与生活")),
    "technology": (("流程", "流程与设计"), ("结构", "结构与设计"), ("控制", "控制与设计"), ("算法", "算法与程序设计"), ("数据", "数据与信息"), ("系统", "系统与设计")),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_rank(path: Path) -> tuple[int, int, str]:
    name = path.name
    score = 0
    if "解析" in name:
        score += 80
    if "答案" in name:
        score += 45
    if "新课标" in name or "新高考" in name:
        score += 20
    if "全国" in name:
        score += 10
    if "原卷" in name or "空白" in name:
        score -= 100
    years = [int(item) for item in re.findall(r"20\d{2}", str(path))]
    year = max(years, default=0)
    score += max(0, year - 2017)
    return score, year, str(path)


def iter_source_documents(subject_dir: Path) -> Iterable[Path]:
    candidates = [
        path
        for path in subject_dir.rglob("*.docx")
        if OUTPUT_ROOT not in path.parents
        and not path.name.startswith("~$")
        and ("解析" in path.name or "答案" in path.name)
        and "原卷" not in path.name
        and "空白" not in path.name
    ]
    yield from sorted(candidates, key=source_rank, reverse=True)


def find_question_start(paragraphs: list[Paragraph], answer_index: int) -> int | None:
    # Answer editions normally place an answer immediately after its question.
    # A bounded backward search prevents us from swallowing the preceding answer.
    lower = max(0, answer_index - 45)
    for index in range(answer_index, lower - 1, -1):
        if index != answer_index and ANSWER_MARKER.search(paragraphs[index].plain):
            break
        if QUESTION_START.match(paragraphs[index].plain):
            return index
    return None


def context_start_between(
    paragraphs: list[Paragraph], lower: int, upper: int
) -> int | None:
    """Locate source material introduced before a question group.

    Humanities answer editions commonly put one passage before several numbered
    questions.  The later questions do not repeat that passage, so the exported
    paper must explicitly inherit it.  Prefer a reading/material instruction and
    retain its immediately preceding section heading when present.
    """
    intro_indices = [
        index
        for index in range(lower, upper)
        if READING_CONTEXT_INTRO.match(paragraphs[index].plain)
    ]
    if intro_indices:
        intro_index = intro_indices[-1]
        heading_indices = [
            index
            for index in range(lower, intro_index)
            if SECTION_HEADING.match(paragraphs[index].plain)
        ]
        if heading_indices and intro_index - heading_indices[-1] <= 3:
            return heading_indices[-1]
        return intro_index
    heading_indices = [
        index
        for index in range(lower, upper)
        if SECTION_HEADING.match(paragraphs[index].plain)
    ]
    return heading_indices[-1] if heading_indices else None


def context_by_question_start(
    paragraphs: list[Paragraph],
    question_run: list[tuple[int, int]],
    lower: int = 0,
) -> dict[int, str]:
    """Map every question in a shared-material group to the complete material."""
    result: dict[int, str] = {}
    active_context = ""
    scan_start = lower
    for question_index, _ in question_run:
        context_start = context_start_between(paragraphs, scan_start, question_index)
        if context_start is not None:
            active_context = clean_markup(
                "<br>".join(
                    paragraph.markup
                    for paragraph in paragraphs[context_start:question_index]
                )
            )
        result[question_index] = active_context
        scan_start = question_index + 1
    return result


def attach_shared_context(question: SourceQuestion, context_markup: str) -> None:
    if not context_markup or 'class="exam-shared-context"' in question.stem_markup:
        return
    question.stem_markup = clean_markup(
        f'<section class="exam-shared-context">{context_markup}</section><br>{question.stem_markup}'
    )


def split_options(markup: str) -> tuple[str, list[str]] | None:
    visible = plain_text(markup)
    matches = list(OPTION_MARKER.finditer(visible))
    if len(matches) != 4 or [match.group(1) for match in matches] != list("ABCD"):
        return None

    # Map visible positions back approximately by parsing the cleaned markup. Most
    # source options are plain text separated by embedded equation images, so the
    # marker offsets remain stable after HTML tags are removed.
    marker_matches = list(OPTION_MARKER.finditer(markup))
    if len(marker_matches) != 4 or [match.group(1) for match in marker_matches] != list("ABCD"):
        return None
    stem = markup[: marker_matches[0].start()].strip(" <br>")
    options: list[str] = []
    for pos, match in enumerate(marker_matches):
        end = marker_matches[pos + 1].start() if pos < 3 else len(markup)
        options.append(markup[match.end() : end].strip(" <br>"))
    if not stem or any(not plain_text(option) for option in options):
        return None
    return stem, options


def infer_tags(subject: str, text: str) -> list[str]:
    tags = [label for keyword, label in KNOWLEDGE_KEYWORDS[subject] if keyword in text]
    if tags:
        return list(dict.fromkeys(tags))[:3]
    return [f"{SUBJECTS[subject][0]}综合"]


def longest_numbered_run(items: list[tuple[int, int]]) -> list[tuple[int, int]]:
    runs: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for item in items:
        if not current or item[1] == current[-1][1] + 1:
            current.append(item)
        else:
            if current:
                runs.append(current)
            current = [item]
    if current:
        runs.append(current)
    return max(runs, key=len, default=[])


def build_source_question(
    subject: str,
    path: Path,
    digest: str,
    original_number: int,
    question_markup: str,
    answer_markup: str,
    analysis_markup: str = "",
) -> SourceQuestion | None:
    question_plain = plain_text(question_markup)
    if (
        len(question_plain) < 8
        or not plain_text(answer_markup)
        or EXAM_DIRECTION.match(question_plain)
    ):
        return None
    answer_plain = plain_text(answer_markup)
    correct_match = re.match(r"\s*([ABCD])(?:\b|[.．、，。])", answer_plain)
    parsed_options = split_options(question_markup)
    if parsed_options and correct_match:
        stem_markup, options_markup = parsed_options
        question_type = "multiple_choice"
        correct_option = correct_match.group(1)
    elif parsed_options:
        # Multi-select questions cannot be rewritten into a single A/B/C/D choice
        # without changing the original answer semantics, so they are excluded.
        return None
    else:
        constructed_signals = (
            "（1）", "（2）", "(1)", "(2)", "请", "分析", "说明", "证明",
            "写作", "解答", "简述", "概括", "翻译", "计算", "理由", "影响",
            "意义", "评价", "探究", "论述", "设计",
        )
        if len(answer_plain) < 35 and not any(
            signal in question_plain for signal in constructed_signals
        ):
            # This is normally a fill-in/short blank rather than a large response
            # question. The requested diagnostic papers reserve photo upload for
            # questions with observable reasoning or extended expression.
            return None
        stem_markup = question_markup
        options_markup = []
        question_type = "constructed_response"
        correct_option = None
    combined_plain = f"{plain_text(stem_markup)} {answer_plain}"
    difficulty = min(0.95, 0.3 + original_number * 0.025 + (0.18 if question_type == "constructed_response" else 0))
    return SourceQuestion(
        subject=subject,
        source_path=path,
        source_hash=digest,
        original_number=original_number,
        question_type=question_type,
        stem_markup=stem_markup,
        options_markup=options_markup,
        correct_option=correct_option,
        answer_markup=answer_markup,
        analysis_markup=analysis_markup,
        knowledge_tags=infer_tags(subject, combined_plain),
        difficulty=round(difficulty, 2),
    )


def extract_collective_answer_questions(
    subject: str,
    path: Path,
    digest: str,
    paragraphs: list[Paragraph],
    answer_index: int,
) -> list[SourceQuestion]:
    candidates: list[tuple[int, int]] = []
    for index, paragraph in enumerate(paragraphs[:answer_index]):
        match = QUESTION_START.match(paragraph.plain)
        if match:
            candidates.append((index, int(match.group(1))))
    question_run = longest_numbered_run(candidates)
    if len(question_run) < 5:
        return []

    response_markup = clean_markup("<br>".join(paragraph.markup for paragraph in paragraphs[answer_index:]))
    response_markup = ANSWER_MARKER.sub("", response_markup, count=1)
    answer_markers = [
        (match.start(), int(match.group(1)), match.end())
        for match in re.finditer(r"(?:^|<br>|\s)(\d{1,2})\s*[.．、]\s*", response_markup)
    ]
    answer_run_raw = longest_numbered_run([(start, number) for start, number, _ in answer_markers])
    if len(answer_run_raw) < 5:
        return []
    answer_end_by_start = {start: end for start, _, end in answer_markers}
    answer_positions = {
        number: (answer_end_by_start[start], answer_run_raw[pos + 1][0] if pos + 1 < len(answer_run_raw) else len(response_markup))
        for pos, (start, number) in enumerate(answer_run_raw)
    }

    contexts = context_by_question_start(paragraphs, question_run)
    questions: list[SourceQuestion] = []
    for pos, (start_index, number) in enumerate(question_run):
        answer_position = answer_positions.get(number)
        if answer_position is None:
            continue
        end_index = question_run[pos + 1][0] if pos + 1 < len(question_run) else answer_index
        question_markup = clean_markup("<br>".join(paragraph.markup for paragraph in paragraphs[start_index:end_index]))
        answer_markup = clean_markup(response_markup[answer_position[0] : answer_position[1]])
        question = build_source_question(
            subject, path, digest, number, question_markup, answer_markup
        )
        if question is not None:
            attach_shared_context(question, contexts.get(start_index, ""))
            questions.append(question)
    return questions


def parse_numbered_answers(markup: str) -> tuple[list[tuple[int, int]], dict[int, tuple[int, int]]]:
    markers = [
        (match.start(), int(match.group(1)), match.end())
        for match in re.finditer(r"(?:^|<br>|\s)(\d{1,2})\s*[.．、]\s*", markup)
    ]
    run = longest_numbered_run([(start, number) for start, number, _ in markers])
    marker_end = {start: end for start, _, end in markers}
    positions = {
        number: (marker_end[start], run[pos + 1][0] if pos + 1 < len(run) else len(markup))
        for pos, (start, number) in enumerate(run)
    }
    return run, positions


def extract_grouped_answer_questions(
    subject: str,
    path: Path,
    digest: str,
    paragraphs: list[Paragraph],
    markers: list[int],
) -> list[SourceQuestion]:
    questions: list[SourceQuestion] = []
    previous_marker = 0
    for marker_pos, answer_index in enumerate(markers):
        next_marker = markers[marker_pos + 1] if marker_pos + 1 < len(markers) else len(paragraphs)
        analysis_index = next(
            (
                index
                for index in range(answer_index + 1, next_marker)
                if ANALYSIS_MARKER.search(paragraphs[index].plain)
            ),
            next_marker,
        )
        response_markup = clean_markup("<br>".join(paragraph.markup for paragraph in paragraphs[answer_index:analysis_index]))
        response_markup = ANSWER_MARKER.sub("", response_markup, count=1)
        answer_run, answer_positions = parse_numbered_answers(response_markup)
        if len(answer_run) < 2:
            previous_marker = answer_index
            continue
        candidates: list[tuple[int, int]] = []
        for index in range(previous_marker, answer_index):
            match = QUESTION_START.match(paragraphs[index].plain)
            if match:
                candidates.append((index, int(match.group(1))))
        question_run = longest_numbered_run(candidates)
        answer_numbers = {number for _, number in answer_run}
        question_run = [item for item in question_run if item[1] in answer_numbers]
        context_markup = ""
        if question_run:
            first_question_index = question_run[0][0]
            context_start = context_start_between(
                paragraphs, previous_marker, first_question_index
            )
            if context_start is not None:
                context_markup = clean_markup(
                    "<br>".join(
                        paragraph.markup
                        for paragraph in paragraphs[context_start:first_question_index]
                    )
                )
        for pos, (start_index, number) in enumerate(question_run):
            answer_position = answer_positions.get(number)
            if answer_position is None:
                continue
            end_index = question_run[pos + 1][0] if pos + 1 < len(question_run) else answer_index
            question_markup = clean_markup("<br>".join(paragraph.markup for paragraph in paragraphs[start_index:end_index]))
            answer_markup = clean_markup(response_markup[answer_position[0] : answer_position[1]])
            question = build_source_question(
                subject, path, digest, number, question_markup, answer_markup
            )
            if question is not None:
                attach_shared_context(question, context_markup)
                questions.append(question)
        previous_marker = answer_index
    return questions


def extract_source_questions(subject: str, path: Path) -> list[SourceQuestion]:
    try:
        reader = DocxReader(path)
    except (KeyError, zipfile.BadZipFile, ET.ParseError, OSError):
        return []
    try:
        paragraphs = reader.paragraphs()
    finally:
        reader.close()
    markers = [index for index, paragraph in enumerate(paragraphs) if ANSWER_MARKER.search(paragraph.plain)]
    digest = file_sha256(path)
    if markers:
        grouped = extract_grouped_answer_questions(subject, path, digest, paragraphs, markers)
        if len(grouped) >= 5:
            return grouped
    if len(markers) <= 3 and markers:
        collective = extract_collective_answer_questions(subject, path, digest, paragraphs, markers[0])
        if collective:
            return collective
    starts = [find_question_start(paragraphs, index) for index in markers]
    numbered_starts = sorted(
        {
            start_index: int(QUESTION_START.match(paragraphs[start_index].plain).group(1))
            for start_index in starts
            if start_index is not None and QUESTION_START.match(paragraphs[start_index].plain)
        }.items()
    )
    contexts = context_by_question_start(paragraphs, numbered_starts)
    questions: list[SourceQuestion] = []
    for marker_pos, (answer_index, start_index) in enumerate(zip(markers, starts, strict=True)):
        if start_index is None:
            continue
        number_match = QUESTION_START.match(paragraphs[start_index].plain)
        if not number_match:
            continue
        original_number = int(number_match.group(1))
        next_starts = [value for value in starts[marker_pos + 1 :] if value is not None and value > answer_index]
        end_index = next_starts[0] if next_starts else min(len(paragraphs), answer_index + 100)

        question_parts = [paragraph.markup for paragraph in paragraphs[start_index:answer_index]]
        answer_paragraph = paragraphs[answer_index].markup
        answer_split = ANSWER_MARKER.split(answer_paragraph, maxsplit=1)
        before_answer = answer_split[0]
        after_answer = answer_split[1] if len(answer_split) > 1 else ""
        if before_answer.strip():
            question_parts.append(before_answer)
        response_parts = [after_answer]
        response_parts.extend(paragraph.markup for paragraph in paragraphs[answer_index + 1 : end_index])
        question_markup = clean_markup("<br>".join(question_parts))
        response_markup = clean_markup("<br>".join(response_parts))
        analysis_match = ANALYSIS_MARKER.search(response_markup)
        if analysis_match:
            answer_markup = clean_markup(response_markup[: analysis_match.start()])
            analysis_markup = clean_markup(response_markup[analysis_match.end() :])
        else:
            answer_markup = response_markup
            analysis_markup = ""
        question = build_source_question(
            subject, path, digest, original_number, question_markup, answer_markup, analysis_markup
        )
        if question is not None:
            attach_shared_context(question, contexts.get(start_index, ""))
            questions.append(question)
    return questions


def question_key(question: SourceQuestion) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", plain_text(question.stem_markup)).lower()
    if len(normalized) >= 20:
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{question.source_hash}:{question.original_number}:{question.question_type}"


def collect_subject_pool(subject: str, subject_dir: Path) -> tuple[list[SourceQuestion], dict[str, int]]:
    pool: list[SourceQuestion] = []
    seen: set[str] = set()
    stats = {"documents_scanned": 0, "questions_extracted": 0, "duplicates_removed": 0}
    for path in iter_source_documents(subject_dir):
        extracted = extract_source_questions(subject, path)
        stats["documents_scanned"] += 1
        stats["questions_extracted"] += len(extracted)
        for question in extracted:
            key = question_key(question)
            if key in seen:
                stats["duplicates_removed"] += 1
                continue
            seen.add(key)
            pool.append(question)
        mcq_count = sum(item.question_type == "multiple_choice" for item in pool)
        constructed_count = len(pool) - mcq_count
        if mcq_count >= 120 and constructed_count >= 80:
            break
    return pool, stats


def relative_source(path: Path) -> str:
    return path.relative_to(SOURCE_ROOT).as_posix()


def replace_images(markup: str, reader: DocxReader, subject: str) -> str:
    asset_dir = OUTPUT_ROOT / "assets" / subject
    asset_dir.mkdir(parents=True, exist_ok=True)

    def replacement(match: re.Match[str]) -> str:
        payload = reader.image_bytes(match.group(1))
        if payload is None:
            return '<span class="exam-missing-figure">[原题图片读取失败]</span>'
        data, suffix = payload
        digest = hashlib.sha256(data).hexdigest()[:20]
        target = asset_dir / f"{digest}{suffix}"
        if not target.exists():
            target.write_bytes(data)
        if suffix == ".wmf" and WMF_CONVERTER.exists():
            svg_target = asset_dir / f"{digest}.svg"
            if not svg_target.exists():
                converted = subprocess.run(
                    [str(WMF_CONVERTER), "--inline", "-o", str(svg_target), str(target)],
                    check=False,
                    capture_output=True,
                )
                if converted.returncode != 0:
                    return '<span class="exam-missing-figure">[原卷中存在无法转换的空白公式图]</span>'
            if svg_target.exists() and svg_target.stat().st_size:
                try:
                    svg_target.write_bytes(
                        browser_safe_svg_bytes(svg_target.read_bytes(), source_wmf=data)
                    )
                except (UnicodeError, ET.ParseError):
                    return '<span class="exam-missing-figure">[原卷公式图无法安全转换]</span>'
                target = svg_target
            else:
                return '<span class="exam-missing-figure">[原卷中存在空白公式图]</span>'
        # Keep generated papers independent from a particular frontend proxy.
        # The web client resolves this API-relative path against its configured API base.
        url = f"/api/v1/exam-diagnostics/assets/{subject}/{target.name}"
        image_class = (
            "exam-inline-image exam-formula-image"
            if target.suffix.lower() == ".svg"
            else "exam-inline-image exam-figure-image"
        )
        return f'<img class="{image_class}" src="{url}" alt="原题公式或图形">'

    return IMG_RE.sub(replacement, markup)


def build_papers_for_subject(subject: str, label: str, pool: list[SourceQuestion]) -> tuple[list[dict], list[dict]]:
    mcq = [item for item in pool if item.question_type == "multiple_choice"]
    constructed = [item for item in pool if item.question_type == "constructed_response"]
    if len(mcq) < 12 or len(constructed) < 8:
        raise RuntimeError(f"{label}有效题量不足：选择题 {len(mcq)}，大题 {len(constructed)}")
    papers: list[dict] = []
    answer_banks: list[dict] = []
    readers: dict[Path, DocxReader] = {}
    try:
        for paper_index in range(10):
            selected = [mcq[(paper_index * 12 + offset) % len(mcq)] for offset in range(12)]
            selected.extend(constructed[(paper_index * 8 + offset) % len(constructed)] for offset in range(8))
            paper_id = f"gaokao_diag_{subject}_{paper_index + 1:02d}"
            questions: list[dict] = []
            answers: list[dict] = []
            source_docs: dict[str, dict] = {}
            for sequence, source in enumerate(selected, start=1):
                reader = readers.get(source.source_path)
                if reader is None:
                    reader = DocxReader(source.source_path)
                    readers[source.source_path] = reader
                question_id = f"{paper_id}_q{sequence:02d}"
                source_info = {
                    "document": relative_source(source.source_path),
                    "document_sha256": source.source_hash,
                    "original_number": source.original_number,
                    "source_title": source.source_path.stem,
                }
                source_docs[source.source_hash] = {
                    "document": relative_source(source.source_path),
                    "document_sha256": source.source_hash,
                    "source_title": source.source_path.stem,
                }
                max_score = 5 if source.question_type == "multiple_choice" else 10
                questions.append(
                    {
                        "question_id": question_id,
                        "sequence": sequence,
                        "type": source.question_type,
                        "stem_html": replace_images(source.stem_markup, reader, subject),
                        "options": [
                            {"key": key, "content_html": replace_images(content, reader, subject)}
                            for key, content in zip("ABCD", source.options_markup)
                        ],
                        "max_score": max_score,
                        "knowledge_tags": source.knowledge_tags,
                        "difficulty": source.difficulty,
                        "source": source_info,
                    }
                )
                answers.append(
                    {
                        "question_id": question_id,
                        "type": source.question_type,
                        "correct_option": source.correct_option,
                        "standard_answer_html": replace_images(source.answer_markup, reader, subject),
                        "analysis_html": replace_images(source.analysis_markup, reader, subject),
                        "standard_answer_text": plain_text(source.answer_markup),
                        "analysis_text": plain_text(source.analysis_markup),
                        "max_score": max_score,
                        "source": source_info,
                    }
                )
            total_score = sum(item["max_score"] for item in questions)
            papers.append(
                {
                    "schema_version": "1.0",
                    "paper_id": paper_id,
                    "subject": subject,
                    "subject_label": label,
                    "title": f"{label}高考真题专业学情诊断卷（第{paper_index + 1}套）",
                    "description": "由本地高考真题及其官方/原卷解析答案构建，含12道四选一选择题和8道拍照作答题。",
                    "question_count": 20,
                    "multiple_choice_count": 12,
                    "constructed_response_count": 8,
                    "total_score": total_score,
                    "duration_minutes": 100,
                    "source_documents": list(source_docs.values()),
                    "questions": questions,
                }
            )
            answer_banks.append(
                {
                    "schema_version": "1.0",
                    "paper_id": paper_id,
                    "generated_from_source_only": True,
                    "answer_count": len(answers),
                    "answers": answers,
                }
            )
    finally:
        for reader in readers.values():
            reader.close()
    return papers, answer_banks


def validate_export(papers: list[dict], answer_banks: list[dict]) -> list[str]:
    errors: list[str] = []
    answers_by_id = {bank["paper_id"]: bank for bank in answer_banks}
    for paper in papers:
        if paper["question_count"] != len(paper["questions"]):
            errors.append(f"{paper['paper_id']}: question_count 不一致")
        if paper["multiple_choice_count"] < 1 or paper["constructed_response_count"] < 1:
            errors.append(f"{paper['paper_id']}: 题型不完整")
        bank = answers_by_id.get(paper["paper_id"])
        if bank is None or len(bank["answers"]) != len(paper["questions"]):
            errors.append(f"{paper['paper_id']}: 答案数量不一致")
            continue
        answer_map = {item["question_id"]: item for item in bank["answers"]}
        for question in paper["questions"]:
            answer = answer_map.get(question["question_id"])
            if answer is None or not answer["standard_answer_text"]:
                errors.append(f"{question['question_id']}: 缺少标准答案")
            if question["type"] == "multiple_choice":
                if [option["key"] for option in question["options"]] != list("ABCD"):
                    errors.append(f"{question['question_id']}: 选项不是 A/B/C/D")
                if not answer or answer["correct_option"] not in "ABCD":
                    errors.append(f"{question['question_id']}: 选择题答案无效")
            rendered = question["stem_html"] + "".join(
                option["content_html"] for option in question["options"]
            )
            stem_plain = plain_text(question["stem_html"])
            if EXAM_DIRECTION.match(stem_plain):
                errors.append(f"{question['question_id']}: 误收录了答题须知")
            if (
                paper["subject"] in {"chinese", "history", "geography", "ideology_politics"}
                and MATERIAL_REFERENCE.search(stem_plain)
                and len(stem_plain) < 160
                and "exam-shared-context" not in question["stem_html"]
                and "<img" not in question["stem_html"]
            ):
                errors.append(f"{question['question_id']}: 引用了材料但题面未携带完整材料")
            if ".wmf\"" in rendered or ".emf\"" in rendered or "exam-missing-figure" in rendered:
                errors.append(f"{question['question_id']}: 含浏览器无法显示的矢量图")
            source = SOURCE_ROOT / question["source"]["document"]
            if not source.exists():
                errors.append(f"{question['question_id']}: 来源文件不存在")
    return errors


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_all(output_root: Path) -> None:
    global OUTPUT_ROOT
    OUTPUT_ROOT = output_root
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    all_papers: list[dict] = []
    all_answers: list[dict] = []
    pool_stats: dict[str, dict] = {}
    for subject, (label, directory) in SUBJECTS.items():
        pool, stats = collect_subject_pool(subject, SOURCE_ROOT / directory)
        stats.update(
            {
                "pool_size": len(pool),
                "multiple_choice": sum(item.question_type == "multiple_choice" for item in pool),
                "constructed_response": sum(item.question_type == "constructed_response" for item in pool),
            }
        )
        pool_stats[subject] = stats
        print(f"[{label}] 扫描 {stats['documents_scanned']} 个文档，题库 {len(pool)} 题")
        papers, answers = build_papers_for_subject(subject, label, pool)
        all_papers.extend(papers)
        all_answers.extend(answers)
        for paper, bank in zip(papers, answers, strict=True):
            write_json(output_root / subject / f"{paper['paper_id']}.json", paper)
            write_json(output_root / "answers" / subject / f"{paper['paper_id']}.answers.json", bank)

    errors = validate_export(all_papers, all_answers)
    manifest = {
        "schema_version": "1.0",
        "source_root": str(SOURCE_ROOT),
        "paper_count": len(all_papers),
        "subjects": [
            {
                "subject": subject,
                "subject_label": label,
                "paper_count": 10,
                "papers": [
                    {
                        key: paper[key]
                        for key in (
                            "paper_id", "title", "description", "question_count",
                            "multiple_choice_count", "constructed_response_count",
                            "total_score", "duration_minutes",
                        )
                    }
                    for paper in all_papers
                    if paper["subject"] == subject
                ],
            }
            for subject, (label, _) in SUBJECTS.items()
        ],
    }
    report = {
        "valid": not errors,
        "paper_count": len(all_papers),
        "question_instances": sum(len(paper["questions"]) for paper in all_papers),
        "subject_pool_stats": pool_stats,
        "errors": errors,
    }
    write_json(output_root / "manifest.json", manifest)
    write_json(output_root / "integrity_report.json", report)
    (output_root / "README.md").write_text(
        "# 高考真题专业学情诊断卷\n\n"
        "本目录由 `scripts/build_exam_diagnosis_bank.py` 从同级各科高考真题解析卷自动生成。\n\n"
        "- 学生端题面：各科目录内的 JSON。\n"
        "- 后端专用答案：`answers/`，禁止由静态前端直接发布。\n"
        "- 原题公式和插图：`assets/`。\n"
        "- 每道题均记录原始 DOCX 相对路径、SHA-256 和原题号。\n"
        "- `integrity_report.json` 为数量、题型、答案及来源完整性校验结果。\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"导出校验失败，共 {len(errors)} 项；详见 {output_root / 'integrity_report.json'}")
    print(f"生成完成：{len(all_papers)} 套、{report['question_instances']} 道题次，校验通过。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    build_all(args.output.resolve())


if __name__ == "__main__":
    main()
