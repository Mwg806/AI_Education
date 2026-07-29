"""Read-only, source-grounded onboarding catalogs and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_education.core.errors import InputValidationError, PolicyUnavailableError
from ai_education.domain.models import StudentAcademicProfile

PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_ROOT = PROJECT_ROOT / "Knowledge"


class CurriculumCatalogService:
    """Keep profile choices constrained to versioned Knowledge catalogs."""

    def __init__(self, knowledge_root: Path | None = None) -> None:
        root = knowledge_root or KNOWLEDGE_ROOT
        self._routes = self._load(root / "catalogs" / "province_exam_routes.json")
        self._math = self._load(root / "catalogs" / "math_textbook_chapters.json")
        self._taxonomy = self._load(root / "taxonomy" / "knowledge_taxonomy.json")

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

    def mathematics_standard_modules(self) -> list[dict[str, Any]]:
        math = next(item for item in self._taxonomy["subjects"] if item["subject"] == "mathematics")
        return [
            {
                "id": module["id"],
                "label": module["name"],
                "topics": module["topics"],
                "source_type": "CURRICULUM_STANDARD_TAXONOMY",
            }
            for module in math["modules"]
        ]

    def onboarding_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "scope": {
                "exam_system": self._routes["paper_system"],
                "basis_year": self.scope_year,
                "annual_reconfirmation_required": True,
                "source_document": (
                    "information/2026全国新课标I卷地区科目教材与知识库资料获取说明.md"
                ),
            },
            "provinces": self._routes["provinces"],
            "national_unified_subjects": self._routes["national_unified_subjects"],
            "mathematics": {
                **self._math,
                "standard_modules": self.mathematics_standard_modules(),
            },
        }

    def validate_student_profile(self, student: StudentAcademicProfile) -> None:
        self.province_route(student.province_code)
        edition_id = student.curriculum_versions.get("mathematics")
        progress_id = student.class_progress.get("mathematics")
        if not edition_id:
            raise InputValidationError("必须确认数学教材版本")
        if not progress_id:
            raise InputValidationError("必须选择数学当前进度")

        edition = self.math_edition(str(edition_id))
        if edition["catalog_status"] == "VERIFIED_OFFICIAL":
            allowed = {
                chapter["id"] for volume in edition["volumes"] for chapter in volume["chapters"]
            }
            source_type = "教材章节"
        else:
            allowed = {module["id"] for module in self.mathematics_standard_modules()}
            source_type = "课程标准主题"
        if str(progress_id) not in allowed:
            raise InputValidationError(
                f"数学当前进度不是该版本允许的{source_type}",
                details={
                    "edition_id": edition_id,
                    "catalog_status": edition["catalog_status"],
                    "progress_id": progress_id,
                    "allowed_progress_ids": sorted(allowed),
                },
            )
