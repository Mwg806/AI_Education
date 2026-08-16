"""Resolve textbook scope labels to stable, subject-specific knowledge concepts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TAXONOMY_PATH = PROJECT_ROOT / "Knowledge" / "taxonomy" / "knowledge_taxonomy.json"

SUBJECT_TAXONOMY_KEYS: dict[str, tuple[str, ...]] = {
    "chinese": ("chinese",),
    "mathematics": ("mathematics",),
    "foreign_language": ("english",),
    "physics": ("physics",),
    "chemistry": ("chemistry",),
    "biology": ("biology",),
    "history": ("history",),
    "geography": ("geography",),
    "ideology_politics": ("politics",),
    "technology": ("information_technology", "general_technology"),
}

BOOK_CONTEXT = re.compile(
    r"(?:选择性\s*)?必修(?:\s*第?\s*[一二三四五六七八九十百0-9]+(?:\s*册)?)?|"
    r"第\s*[一二三四五六七八九十百0-9]+\s*(?:章|单元|节|册)|"
    r"(?:上|下|全一)册|教材|全册|整本书|全部章节"
)
SCOPE_SEPARATOR = re.compile(r"[、，,；;：:·/（）()\[\]【】]|(?:以及|与|和|及|的)")
NORMALIZE_NOISE = re.compile(r"[^\u3400-\u9fffA-Za-z0-9]+")
CONCEPT_NOISE = {
    "课程标准模块",
    "课程标准",
    "第一册",
    "第二册",
    "第三册",
    "第四册",
    "第五册",
    "第六册",
    "上册",
    "下册",
    "全一册",
    "概述",
    "简介",
    "活动",
    "探究",
    "复习",
    "总结",
    "章末",
    "单元",
    "应用",
    "问题",
    "研究",
    "学习",
}


def clean_scope_label(value: str) -> str:
    """Remove volume/chapter boilerplate while retaining the actual concept title."""

    cleaned = BOOK_CONTEXT.sub(" ", value)
    return " ".join(cleaned.split()).strip(" ·-—_：:")


def normalize_concept(value: str) -> str:
    value = BOOK_CONTEXT.sub("", value.lower())
    value = re.sub(r"(?:以及|与|和|及|的)", "", value)
    return NORMALIZE_NOISE.sub("", value)


def _concept_fragments(value: str) -> list[str]:
    cleaned = clean_scope_label(value)
    candidates = [cleaned, *SCOPE_SEPARATOR.split(cleaned)]
    return list(
        dict.fromkeys(
            item.strip()
            for item in candidates
            if len(item.strip()) >= 2
            and not item.strip().isdigit()
            and item.strip() not in CONCEPT_NOISE
        )
    )


def _bigrams(value: str) -> set[str]:
    return {value[index : index + 2] for index in range(max(0, len(value) - 1))}


def _similarity(left: str, right: str) -> float:
    left_normalized = normalize_concept(left)
    right_normalized = normalize_concept(right)
    if len(left_normalized) < 2 or len(right_normalized) < 2:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    if left_normalized in right_normalized or right_normalized in left_normalized:
        length_ratio = min(len(left_normalized), len(right_normalized)) / max(
            len(left_normalized), len(right_normalized)
        )
        return max(0.7, length_ratio)
    left_bigrams = _bigrams(left_normalized)
    right_bigrams = _bigrams(right_normalized)
    if not left_bigrams or not right_bigrams:
        return 0.0
    return 2 * len(left_bigrams & right_bigrams) / (
        len(left_bigrams) + len(right_bigrams)
    )


@dataclass(frozen=True, slots=True)
class DiagnosticScopeProfile:
    label: str
    cleaned_label: str
    direct_terms: tuple[str, ...]
    module_ids: tuple[str, ...]
    taxonomy_terms: tuple[str, ...]

    @property
    def search_terms(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.direct_terms, *self.taxonomy_terms)))


class DiagnosticScopeResolver:
    """Map edition-specific chapter titles to the shared knowledge taxonomy."""

    def __init__(self, taxonomy_path: Path = DEFAULT_TAXONOMY_PATH) -> None:
        self.taxonomy_path = taxonomy_path
        self._subjects = self._load_subjects()

    def _load_subjects(self) -> dict[str, dict[str, Any]]:
        if not self.taxonomy_path.exists():
            return {}
        payload = json.loads(self.taxonomy_path.read_text(encoding="utf-8"))
        return {
            str(item["subject"]): item
            for item in payload.get("subjects", [])
            if item.get("subject")
        }

    @lru_cache(maxsize=4_096)
    def resolve(self, subject: str, label: str) -> DiagnosticScopeProfile:
        cleaned = clean_scope_label(label)
        direct_terms = _concept_fragments(label)
        ranked_modules: list[tuple[float, dict[str, Any]]] = []
        for taxonomy_key in SUBJECT_TAXONOMY_KEYS.get(subject, (subject,)):
            taxonomy_subject = self._subjects.get(taxonomy_key, {})
            for module in taxonomy_subject.get("modules", []):
                module_name = str(module.get("name") or "")
                topic_scores = [
                    _similarity(cleaned, str(topic))
                    for topic in module.get("topics", [])
                ]
                score = max(
                    _similarity(cleaned, module_name),
                    max(topic_scores, default=0.0),
                )
                if score >= 0.42:
                    ranked_modules.append((score, module))

        ranked_modules.sort(key=lambda item: item[0], reverse=True)
        selected_modules: list[dict[str, Any]] = []
        if ranked_modules:
            best_score = ranked_modules[0][0]
            selected_modules = [
                module
                for score, module in ranked_modules
                if score >= max(0.42, best_score - 0.08)
            ][:2]

        taxonomy_terms: list[str] = []
        module_ids: list[str] = []
        for module in selected_modules:
            module_ids.append(str(module.get("id") or ""))
            taxonomy_terms.extend(_concept_fragments(str(module.get("name") or "")))
            for topic in module.get("topics", []):
                taxonomy_terms.extend(_concept_fragments(str(topic)))

        return DiagnosticScopeProfile(
            label=label,
            cleaned_label=cleaned,
            direct_terms=tuple(dict.fromkeys(direct_terms)),
            module_ids=tuple(item for item in dict.fromkeys(module_ids) if item),
            taxonomy_terms=tuple(dict.fromkeys(taxonomy_terms)),
        )
