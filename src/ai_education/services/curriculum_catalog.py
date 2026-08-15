"""Read-only, source-grounded onboarding catalogs and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_education.core.errors import InputValidationError, PolicyUnavailableError
from ai_education.domain.models import StudentAcademicProfile

PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_ROOT = PROJECT_ROOT / "Knowledge"
ALL_CHAPTERS_ID = "__all_chapters__"

SUBJECT_TAXONOMY_KEYS: dict[str, list[str]] = {
    "chinese": ["chinese"],
    "mathematics": ["mathematics"],
    "foreign_language": ["english"],
    "physics": ["physics"],
    "chemistry": ["chemistry"],
    "biology": ["biology"],
    "history": ["history"],
    "geography": ["geography"],
    "ideology_politics": ["politics"],
    "technology": ["information_technology", "general_technology"],
}
SUBJECT_LABELS = {
    "chinese": "语文",
    "mathematics": "数学",
    "foreign_language": "英语",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物学",
    "history": "历史",
    "geography": "地理",
    "ideology_politics": "思想政治",
    "technology": "技术",
}
EDITION_IDS = {
    "统编版": "unified",
    "人教版": "people_education",
    "外研版": "foreign_language_teaching",
    "译林版": "yilin",
    "北师大版": "beijing_normal",
    "苏教版": "jiangsu_education",
    "湘教版": "hunan_education",
    "鲁科版": "shandong_science",
    "粤教版": "guangdong_education",
    "教科版": "education_science",
    "沪科教版": "shanghai_science_education",
    "沪科版": "shanghai_science",
    "浙科版": "zhejiang_science",
    "中图版": "sinomaps",
    "鲁教版": "shandong_education",
}


class CurriculumCatalogService:
    """Keep profile choices constrained to versioned Knowledge catalogs."""

    def __init__(self, knowledge_root: Path | None = None) -> None:
        root = knowledge_root or KNOWLEDGE_ROOT
        self._routes = self._load(root / "catalogs" / "province_exam_routes.json")
        self._math = self._load(root / "catalogs" / "math_textbook_chapters.json")
        self._textbooks = self._load(root / "catalogs" / "textbook_catalog.json")
        self._pdf_textbooks = self._load(root / "catalogs" / "textbook_pdf_catalog.json")
        self._taxonomy = self._load(root / "taxonomy" / "knowledge_taxonomy.json")
        self._sources = self._load(root / "00_manifest" / "source_registry.json")

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise RuntimeError(f"知识库目录文件不存在: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def scope_year(self) -> int:
        return int(self._routes["exam_year"])

    def province_route(self, province_code: str) -> dict[str, Any]:
        route = next(
            (item for item in self._routes["provinces"] if item["code"] == province_code),
            None,
        )
        if route is None:
            raise PolicyUnavailableError(
                "该地区不在当前全国新课标Ⅰ卷知识库的已核验范围内",
                details={
                    "province_code": province_code,
                    "supported_codes": [item["code"] for item in self._routes["provinces"]],
                    "scope_year": self.scope_year,
                },
            )
        return route

    def math_edition(self, edition_id: str) -> dict[str, Any]:
        edition = next((item for item in self._math["editions"] if item["id"] == edition_id), None)
        if edition is None:
            raise InputValidationError(
                "数学教材版本不在已登记目录中",
                details={
                    "edition_id": edition_id,
                    "allowed_editions": [item["id"] for item in self._math["editions"]],
                },
            )
        return edition

    def standard_modules(self, subject: str) -> list[dict[str, Any]]:
        keys = SUBJECT_TAXONOMY_KEYS.get(subject)
        if not keys:
            raise InputValidationError(
                "规划科目不在已登记课程标准目录中",
                details={"subject": subject, "allowed_subjects": sorted(SUBJECT_TAXONOMY_KEYS)},
            )
        modules: list[dict[str, Any]] = []
        for key in keys:
            taxonomy = next(item for item in self._taxonomy["subjects"] if item["subject"] == key)
            modules.extend(
                {
                    "id": module["id"],
                    "label": module["name"],
                    "topics": module["topics"],
                    "taxonomy_subject": key,
                    "source_type": "CURRICULUM_STANDARD_TAXONOMY",
                }
                for module in taxonomy["modules"]
            )
        return modules

    def mathematics_standard_modules(self) -> list[dict[str, Any]]:
        return self.standard_modules("mathematics")

    def _legacy_subject_editions(self, subject: str) -> list[dict[str, Any]]:
        if subject == "mathematics":
            return self._math["editions"]
        if subject == "technology":
            return [
                {
                    "id": "school_confirmed",
                    "label": "学校实际版本（待确认）",
                    "publisher": "须按浙江当地教学用书目录及学校版权页确认",
                    "catalog_status": "STANDARD_ONLY",
                    "source_urls": [],
                    "volumes": [],
                }
            ]
        keys = set(SUBJECT_TAXONOMY_KEYS[subject])
        entries = [item for item in self._textbooks["subjects"] if item["subject"] in keys]
        labels: list[str] = []
        for entry in entries:
            candidates = entry.get("candidate_editions") or [entry.get("edition")]
            labels.extend(label for label in candidates if label and label not in labels)
        return [
            {
                "id": EDITION_IDS.get(label, f"registered_{index + 1}"),
                "label": label,
                "publisher": next(
                    (entry.get("publisher") for entry in entries if entry.get("publisher")),
                    "出版社须由学校版权页确认",
                ),
                "catalog_status": "EDITION_REGISTERED",
                "source_urls": [],
                "volumes": [],
            }
            for index, label in enumerate(labels)
        ]

    def subject_editions(self, subject: str) -> list[dict[str, Any]]:
        """Return edition/volume/chapter choices extracted from the supplied PDFs."""
        local_subject = next(
            (item for item in self._pdf_textbooks["subjects"] if item["id"] == subject),
            None,
        )
        if local_subject and local_subject["editions"]:
            return local_subject["editions"]
        return self._legacy_subject_editions(subject)

    def subject_catalog(self, subject: str) -> dict[str, Any]:
        keys = SUBJECT_TAXONOMY_KEYS.get(subject)
        if not keys:
            raise InputValidationError("规划科目不在已登记课程标准目录中")
        standards = [
            source
            for source in self._sources["sources"]
            if source.get("document_type") == "CURRICULUM_STANDARD"
            and source.get("subject") in keys
        ]
        return {
            "id": subject,
            "label": SUBJECT_LABELS[subject],
            "score_max": 150 if subject in {"chinese", "mathematics", "foreign_language"} else 100,
            "exam_scope": (
                "NATIONAL_UNIFIED"
                if subject in {"chinese", "mathematics", "foreign_language"}
                else "PROVINCIAL_SELECTIVE"
            ),
            "taxonomy_subjects": keys,
            "editions": self.subject_editions(subject),
            "standard_modules": self.standard_modules(subject),
            "standard_sources": standards,
        }

    def onboarding_catalog(self) -> dict[str, Any]:
        subjects = [self.subject_catalog(subject) for subject in SUBJECT_TAXONOMY_KEYS]
        return {
            "schema_version": "1.2.0",
            "scope": {
                "exam_system": self._routes["paper_system"],
                "basis_year": self.scope_year,
                "annual_reconfirmation_required": True,
                "source_document": (
                    "information/2026全国新课标I卷地区科目教材与知识库资料获取说明.md"
                ),
                "textbook_catalog_source": self._pdf_textbooks["generated_from"],
                "textbook_pdf_count": self._pdf_textbooks["pdf_count"],
                "textbook_catalog_methodology": self._pdf_textbooks["methodology"],
            },
            "provinces": self._routes["provinces"],
            "national_unified_subjects": self._routes["national_unified_subjects"],
            "subjects": subjects,
            "mathematics": next(item for item in subjects if item["id"] == "mathematics"),
        }

    def validate_student_profile(self, student: StudentAcademicProfile) -> None:
        self.province_route(student.province_code)
        if not student.curriculum_versions:
            raise InputValidationError("必须选择本次重点规划科目及教材版本")
        if len(student.curriculum_versions) > 6:
            raise InputValidationError("一次最多选择 6 个规划科目")
        allowed_goal_subjects = {"chinese", "mathematics", "foreign_language"}
        allowed_goal_subjects.update(item.value for item in student.selected_subjects)
        for subject, edition_id in student.curriculum_versions.items():
            raw_progress = student.class_progress.get(subject)
            progress_ids = [
                str(item)
                for item in (
                    raw_progress if isinstance(raw_progress, list) else [raw_progress]
                )
                if item
            ]
            if not progress_ids:
                raise InputValidationError(
                    f"必须选择{SUBJECT_LABELS.get(subject, subject)}当前进度"
                )
            if len(progress_ids) > 5:
                raise InputValidationError("每科最多选择 5 个章节范围")
            if len(set(progress_ids)) != len(progress_ids):
                raise InputValidationError("学习章节范围不能重复")
            if ALL_CHAPTERS_ID in progress_ids and len(progress_ids) > 1:
                raise InputValidationError("整本书范围不能与具体章节同时选择")
            if subject not in allowed_goal_subjects:
                raise InputValidationError(
                    "重点规划科目不在统一高考科目或已确认选科组合中"
                )

            catalog = self.subject_catalog(subject)
            edition = next(
                (
                    item
                    for item in catalog["editions"]
                    if item["id"] == str(edition_id)
                ),
                None,
            )
            if edition is None:
                # Keep previously issued API payloads valid while the UI migrates to
                # stable IDs generated from the local PDF paths.
                edition = next(
                    (
                        item
                        for item in self._legacy_subject_editions(subject)
                        if item["id"] == str(edition_id)
                    ),
                    None,
                )
            if edition is None:
                raise InputValidationError(
                    f"{catalog['label']}教材版本不在已登记目录中",
                    details={
                        "allowed_editions": [
                            item["id"] for item in catalog["editions"]
                        ]
                    },
                )

            textbook_chapters = {
                chapter["id"]
                for volume in edition.get("volumes", [])
                for chapter in volume.get("chapters", [])
            }
            if textbook_chapters:
                allowed = textbook_chapters
                source_type = "教材章节"
            else:
                allowed = {module["id"] for module in catalog["standard_modules"]}
                source_type = "课程标准模块"
            invalid_progress_ids = [
                item
                for item in progress_ids
                if item != ALL_CHAPTERS_ID and item not in allowed
            ]
            if invalid_progress_ids:
                raise InputValidationError(
                    f"{catalog['label']}当前进度不是该版本允许的{source_type}",
                    details={
                        "subject": subject,
                        "edition_id": edition_id,
                        "catalog_status": edition["catalog_status"],
                        "progress_ids": progress_ids,
                        "invalid_progress_ids": invalid_progress_ids,
                        "allowed_progress_ids": sorted(allowed),
                    },
                )
