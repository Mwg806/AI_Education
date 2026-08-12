"""Fixed, source-grounded fallback bank for planner quick diagnostics."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from ai_education.services.exam_diagnosis import DEFAULT_BANK_ROOT

HTML_TAG = re.compile(r"<[^>]+>")
IMAGE_TAG = re.compile(r"<img\b[^>]*alt=\"([^\"]*)\"[^>]*>", re.IGNORECASE)
WHITESPACE = re.compile(r"\s+")
DIMENSIONS = [
    "prerequisite",
    "concept",
    "basic_application",
    "integrated_application",
    "transfer",
] * 2
OPTION_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3}
SUBJECT_KNOWLEDGE_HINTS: dict[str, list[str]] = {
    "chinese": ["论述类文本", "文学类文本", "文言文", "古代诗歌", "语言文字运用", "名篇名句"],
    "mathematics": [
        "集合",
        "复数",
        "函数",
        "导数",
        "数列",
        "三角",
        "向量",
        "立体几何",
        "解析几何",
        "圆锥曲线",
        "概率",
        "统计",
        "不等式",
        "排列组合",
    ],
    "foreign_language": ["阅读理解", "完形填空", "七选五", "语法填空", "词汇", "语法"],
    "physics": ["运动与力", "电场", "磁场", "电磁感应", "机械能", "动量", "热学", "光学"],
    "chemistry": ["化学实验", "元素化学", "有机化学", "化学反应原理", "物质结构", "电化学"],
    "biology": ["细胞", "细胞代谢", "遗传与进化", "稳态与调节", "生态系统", "生物技术", "生物实验"],
    "history": ["古代史", "近代史", "现代史", "世界史", "改革与制度", "经济史", "思想文化"],
    "geography": [
        "自然地理",
        "人口与城市",
        "农业地理",
        "工业地理",
        "区域发展",
        "水循环",
        "地貌",
        "气候",
    ],
    "ideology_politics": [
        "经济与社会",
        "政治与法治",
        "哲学与文化",
        "法律与生活",
        "逻辑与思维",
        "国际政治与经济",
    ],
    "technology": [
        "数据与信息",
        "算法与程序",
        "流程与设计",
        "系统与设计",
        "控制与设计",
        "技术试验",
    ],
}


class QuickDiagnosticBank:
    """Read ten objective questions from the local traceable Gaokao bank."""

    def __init__(self, bank_root: Path = DEFAULT_BANK_ROOT) -> None:
        self.bank_root = bank_root
        self._cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def available(self) -> bool:
        return (self.bank_root / "manifest.json").exists()

    def questions(
        self,
        *,
        subject: str,
        seed: str,
        progress_label: str,
        whole_book: bool,
    ) -> list[dict[str, Any]]:
        candidates = self._subject_questions(subject)
        if len(candidates) < 10:
            raise RuntimeError(f"{subject} 固定诊断题库不足 10 题")

        ordered = sorted(
            candidates,
            key=lambda item: hashlib.sha256(
                f"{seed}:{item['source_question_id']}".encode()
            ).hexdigest(),
        )
        if not whole_book:
            keywords = self._keywords(progress_label)
            ordered.sort(
                key=lambda item: -sum(keyword in item["search_text"] for keyword in keywords)
            )

        selected: list[dict[str, Any]] = []
        seen_focus: set[str] = set()
        seen_source: set[str] = set()
        # First pass maximizes distinct knowledge labels and source papers.
        for item in ordered:
            focus = item["knowledge_focus"]
            source = item["source_paper_id"]
            if focus in seen_focus or source in seen_source:
                continue
            selected.append(item)
            seen_focus.add(focus)
            seen_source.add(source)
            if len(selected) == 10:
                break
        # Some subjects have deliberately broad source tags. Fill the remainder
        # from different questions while retaining the deterministic shuffle.
        for item in ordered:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) == 10:
                break

        result: list[dict[str, Any]] = []
        for index, source in enumerate(selected):
            item = {key: value for key, value in source.items() if key != "search_text"}
            item.update(
                {
                    "dimension": DIMENSIONS[index],
                    "expected_seconds": 90,
                    "scope_id": (
                        f"diagnostic:{subject}:{self._stable_id(source['knowledge_focus'])}"
                        if whole_book
                        else ""
                    ),
                    "scope_label": source["knowledge_focus"],
                }
            )
            result.append(item)
        return result

    def _subject_questions(self, subject: str) -> list[dict[str, Any]]:
        cached = self._cache.get(subject)
        if cached is not None:
            return cached
        questions: list[dict[str, Any]] = []
        for paper_path in sorted((self.bank_root / subject).glob("*.json")):
            paper = self._load(paper_path)
            answer_path = self.bank_root / "answers" / subject / f"{paper_path.stem}.answers.json"
            answers = {
                item["question_id"]: item for item in self._load(answer_path).get("answers", [])
            }
            for question in paper.get("questions", []):
                if question.get("type") != "multiple_choice":
                    continue
                options = question.get("options", [])
                answer = answers.get(question.get("question_id"), {})
                correct_option = OPTION_INDEX.get(str(answer.get("correct_option", "")).upper())
                if len(options) != 4 or correct_option is None:
                    continue
                prompt_html = str(question.get("stem_html", ""))
                option_html = [str(item.get("content_html", "")) for item in options]
                prompt = self._plain_text(prompt_html)
                option_text = [self._plain_text(item) for item in option_html]
                if not prompt or any(not item for item in option_text):
                    continue
                explanation = str(answer.get("analysis_text", "")).strip()
                if not explanation:
                    explanation = self._plain_text(str(answer.get("analysis_html", "")))
                tags = [str(item) for item in question.get("knowledge_tags", []) if item]
                focus = self._infer_focus(subject, tags, f"{prompt} {explanation}")
                questions.append(
                    {
                        "knowledge_focus": focus,
                        "difficulty": max(0.2, min(float(question.get("difficulty", 0.5)), 0.85)),
                        "prompt": prompt,
                        "prompt_html": prompt_html,
                        "options": option_text,
                        "options_html": option_html,
                        "correct_option": correct_option,
                        "explanation": explanation or "依据本题对应知识与题干条件判断。",
                        "source_question_id": str(question["question_id"]),
                        "source_paper_id": str(paper["paper_id"]),
                        "search_text": f"{focus} {prompt}",
                    }
                )
        self._cache[subject] = questions
        return questions

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _plain_text(value: str) -> str:
        value = IMAGE_TAG.sub(lambda match: f"[{match.group(1) or '图或公式'}]", value)
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = HTML_TAG.sub(" ", value)
        return WHITESPACE.sub(" ", html.unescape(value)).strip()

    @staticmethod
    def _keywords(value: str) -> list[str]:
        return [
            item
            for item in re.findall(r"[\u4e00-\u9fff]{2,8}", value)
            if item not in {"选择性必修", "必修", "章节", "教材"}
        ]

    @staticmethod
    def _stable_id(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _infer_focus(subject: str, tags: list[str], text: str) -> str:
        for hint in SUBJECT_KNOWLEDGE_HINTS.get(subject, []):
            if hint in text:
                return hint
        return next(
            (item for item in tags if not item.endswith("综合")),
            tags[0] if tags else "学科综合",
        )
