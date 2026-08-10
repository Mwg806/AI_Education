"""Read-only catalog for Agent 6 skills, diagnostics and project templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_education.config import PROJECT_ROOT

DEFAULT_PROGRAMMING_CATALOG = (
    PROJECT_ROOT / "Knowledge" / "Agent_6" / "programming_learning_catalog.json"
)


class ProgrammingKnowledgeService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PROGRAMMING_CATALOG
        self._catalog = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def version(self) -> str:
        return str(self._catalog["content_version"])

    def sources(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._catalog["sources"]]

    def skills(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._catalog["skill_nodes"]]

    def skill(self, skill_id: str) -> dict[str, Any]:
        return next(
            (dict(item) for item in self._catalog["skill_nodes"] if item["skill_id"] == skill_id),
            {"skill_id": skill_id, "label": skill_id, "category": "待核验"},
        )

    def diagnostic_questions(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._catalog["diagnostic_questions"]]

    def projects(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._catalog["project_templates"]]

    def project(self, project_id: str) -> dict[str, Any] | None:
        return next(
            (
                dict(item)
                for item in self._catalog["project_templates"]
                if item["project_id"] == project_id
            ),
            None,
        )

    def interview_questions(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._catalog["interview_questions"]]

    def hint(self, level: int) -> str:
        hints = self._catalog["hint_ladder"]
        return str(hints[max(0, min(level, len(hints) - 1))])
