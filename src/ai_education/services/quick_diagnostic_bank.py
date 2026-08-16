"""Fixed, source-grounded fallback bank for planner quick diagnostics."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_education.services.diagnostic_scope import (
    DiagnosticScopeProfile,
    DiagnosticScopeResolver,
    normalize_concept,
)

if TYPE_CHECKING:
    from ai_education.services.oss_quick_diagnostic_bank import (
        StructuredOssQuickDiagnosticBank,
    )

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BANK_ROOT = PROJECT_ROOT / "Knowledge" / "Exam" / "高考真题" / "diagnose"

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
LOGGER = logging.getLogger(__name__)
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

    def __init__(
        self,
        bank_root: Path = DEFAULT_BANK_ROOT,
        *,
        supplemental_bank: StructuredOssQuickDiagnosticBank | None = None,
    ) -> None:
        self.bank_root = bank_root
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self.supplemental_bank = supplemental_bank
        self.scope_resolver = DiagnosticScopeResolver()

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
        scope_units: list[dict[str, str]] | None = None,
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
        if whole_book:
            units = [
                {
                    "id": f"diagnostic:{subject}:whole_book",
                    "label": progress_label,
                }
            ]
        else:
            units = scope_units or [
                {
                    "id": f"diagnostic:{subject}:subject",
                    "label": progress_label,
                }
            ]
        matched: list[
            tuple[int, dict[str, str], dict[str, Any], tuple[str, ...], tuple[str, ...]]
        ] = []
        if whole_book:
            # Every source paper is already filtered by subject, so it is inside
            # the selected whole-book range without inventing a chapter match.
            matched = [(1, units[0], item, (), ()) for item in ordered]
        else:
            scope_profiles = {
                scope["id"]: self.scope_resolver.resolve(subject, scope["label"]) for scope in units
            }
            for item in ordered:
                ranked_scopes = sorted(
                    (
                        (
                            *self._scope_match(scope_profiles[scope["id"]], item),
                            scope,
                        )
                        for scope in units
                    ),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                score, match_terms, module_ids, scope = ranked_scopes[0]
                if score > 0:
                    matched.append((score, scope, item, match_terms, module_ids))

        if len(matched) < 10:
            raise RuntimeError(f"{subject} 固定诊断题库中与所选章节可核验匹配的题目不足 10 题")

        matched.sort(
            key=lambda entry: (
                -entry[0],
                hashlib.sha256(f"{seed}:{entry[2]['source_question_id']}".encode()).hexdigest(),
            )
        )

        selected: list[dict[str, Any]] = []
        selected_scopes: dict[str, dict[str, str]] = {}
        selected_matches: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
        seen_focus: set[str] = set()
        seen_source: set[str] = set()
        # First guarantee that every selected scope has at least one genuinely matched question.
        for scope in units:
            candidate = next(
                (
                    item
                    for score, matched_scope, item, _, _ in matched
                    if matched_scope["id"] == scope["id"] and item not in selected
                ),
                None,
            )
            if candidate is None:
                raise RuntimeError(f"固定诊断题库没有与所选范围“{scope['label']}”可核验匹配的题目")
            selected.append(candidate)
            selected_scopes[candidate["source_question_id"]] = scope
            matched_entry = next(
                entry
                for entry in matched
                if entry[1]["id"] == scope["id"] and entry[2] is candidate
            )
            selected_matches[candidate["source_question_id"]] = (
                matched_entry[3],
                matched_entry[4],
            )
            seen_focus.add(candidate["knowledge_focus"])
            seen_source.add(candidate["source_paper_id"])

        # Then maximize distinct knowledge labels and source papers.
        for _, scope, item, match_terms, module_ids in matched:
            if item in selected:
                continue
            focus = item["knowledge_focus"]
            source = item["source_paper_id"]
            if focus in seen_focus or source in seen_source:
                continue
            selected.append(item)
            selected_scopes[item["source_question_id"]] = scope
            selected_matches[item["source_question_id"]] = (match_terms, module_ids)
            seen_focus.add(focus)
            seen_source.add(source)
            if len(selected) >= 10:
                break
        # Some subjects have broad source tags. Fill only from still-matched questions.
        if len(selected) < 10:
            for _, scope, item, match_terms, module_ids in matched:
                if item in selected:
                    continue
                selected.append(item)
                selected_scopes[item["source_question_id"]] = scope
                selected_matches[item["source_question_id"]] = (match_terms, module_ids)
                if len(selected) >= 10:
                    break

        result: list[dict[str, Any]] = []
        for index, source in enumerate(selected):
            item = {
                key: value
                for key, value in source.items()
                if key not in {"search_text", "knowledge_tags", "source_locator_sha256"}
            }
            scope = selected_scopes[source["source_question_id"]]
            match_terms, module_ids = selected_matches.get(source["source_question_id"], ((), ()))
            item.update(
                {
                    "dimension": DIMENSIONS[index],
                    "expected_seconds": 90,
                    "scope_id": scope["id"],
                    "scope_label": scope["label"],
                    "provenance": {
                        "mode": "verified_question_bank",
                        "source_id": source["source_question_id"],
                        "source_paper_id": source["source_paper_id"],
                        "title": source.get("source_title") or source["source_paper_id"],
                        "document_sha256": source.get("source_document_sha256"),
                        "source_storage": source.get("source_storage", "local"),
                        "source_kind": source.get("source_kind", "gaokao_past_paper"),
                        "scope_match_verified": True,
                        "scope_match_level": (
                            "subject_whole_book"
                            if whole_book
                            else "chapter_taxonomy"
                            if module_ids
                            else "chapter_concept"
                        ),
                        "scope_match_terms": list(match_terms),
                        "scope_module_ids": list(module_ids),
                    },
                }
            )
            result.append(item)
        return result

    def _subject_questions(self, subject: str) -> list[dict[str, Any]]:
        cached = self._cache.get(subject)
        if cached is None:
            cached = self._local_subject_questions(subject)
            self._cache[subject] = cached
        questions = list(cached)
        if self.supplemental_bank is not None:
            try:
                questions.extend(self.supplemental_bank.questions(subject))
            except Exception as exc:
                LOGGER.warning("OSS 快速诊断补充题库不可用，继续使用本地题库：%s", exc)
        result: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_prompts: set[str] = set()
        for item in questions:
            source_id = str(item.get("source_question_id") or "")
            prompt_key = hashlib.sha256(
                normalize_concept(str(item.get("prompt") or "")).encode("utf-8")
            ).hexdigest()
            if not source_id or source_id in seen_ids or prompt_key in seen_prompts:
                continue
            seen_ids.add(source_id)
            seen_prompts.add(prompt_key)
            result.append(item)
        return result

    def _local_subject_questions(self, subject: str) -> list[dict[str, Any]]:
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
                        "source_title": str(
                            (question.get("source") or {}).get("source_title")
                            or paper.get("title")
                            or paper["paper_id"]
                        ),
                        "source_document_sha256": str(
                            (question.get("source") or {}).get("document_sha256") or ""
                        ),
                        "source_storage": "local",
                        "source_kind": "gaokao_past_paper",
                        "knowledge_tags": tags,
                        "search_text": f"{focus} {prompt}",
                    }
                )
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
    def _scope_match(
        profile: DiagnosticScopeProfile,
        item: dict[str, Any],
    ) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
        search_text = str(item.get("search_text") or "").lower()
        normalized_text = normalize_concept(search_text)
        matched_terms: list[str] = []
        score = 0

        for term in profile.direct_terms:
            normalized_term = normalize_concept(term)
            if len(normalized_term) < 2:
                continue
            if term.lower() in search_text or normalized_term in normalized_text:
                matched_terms.append(term)
                score += 8 + min(len(normalized_term), 8)

        taxonomy_terms = [
            (term, normalize_concept(term))
            for term in profile.taxonomy_terms
            if len(normalize_concept(term)) >= 2
        ]
        signals = [
            str(item.get("knowledge_focus") or ""),
            *[str(tag) for tag in item.get("knowledge_tags", [])],
        ]
        for signal in signals:
            normalized_signal = normalize_concept(signal)
            if len(normalized_signal) < 2 or normalized_signal.endswith("综合"):
                continue
            related = next(
                (
                    term
                    for term, normalized_term in taxonomy_terms
                    if normalized_signal in normalized_term or normalized_term in normalized_signal
                ),
                None,
            )
            if related is not None:
                matched_terms.append(signal)
                score += 12 + min(len(normalized_signal), 8)

        return (
            score,
            tuple(dict.fromkeys(matched_terms)),
            profile.module_ids if score > 0 else (),
        )

    @staticmethod
    def _infer_focus(subject: str, tags: list[str], text: str) -> str:
        for hint in SUBJECT_KNOWLEDGE_HINTS.get(subject, []):
            if hint in text:
                return hint
        return next(
            (item for item in tags if not item.endswith("综合")),
            tags[0] if tags else "学科综合",
        )
