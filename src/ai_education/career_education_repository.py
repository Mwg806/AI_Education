"""Persistence boundary for Agent 6 V1 job, project and coding banks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.mysql_persistence import MySQLPersistence
from ai_education.programming_learning_repository import ProgrammingLearningRepository


class CareerEducationRepository(ProgrammingLearningRepository):
    def __init__(self, persistence: MySQLPersistence | None = None) -> None:
        super().__init__(persistence)
        self.jobs: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []
        self.questions: list[dict[str, Any]] = []

    def sync_catalog(self, catalog: dict[str, Any]) -> None:
        self.jobs = deepcopy(catalog["jobs"])
        self.projects = deepcopy(catalog["projects"])
        self.questions = deepcopy(catalog["questions"])
        if self.persistence:
            self.persistence.sync_career_catalog(self.jobs, self.projects, self.questions)

    def list_jobs(self) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_career_jobs()
        return deepcopy(self.jobs)

    def list_projects(self, target_job_id: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_career_projects(target_job_id)
        return deepcopy([item for item in self.projects if item["target_job_id"] == target_job_id])

    def list_questions(self, target_job_id: str) -> list[dict[str, Any]]:
        if self.persistence:
            return self.persistence.list_career_questions(target_job_id)
        return deepcopy([item for item in self.questions if item["target_job_id"] == target_job_id])

    def get_project(self, project_id: str, target_job_id: str) -> dict[str, Any] | None:
        return next(
            (
                deepcopy(item)
                for item in self.list_projects(target_job_id)
                if item["project_id"] == project_id
            ),
            None,
        )

    def get_question(self, question_id: str, target_job_id: str) -> dict[str, Any] | None:
        return next(
            (
                deepcopy(item)
                for item in self.list_questions(target_job_id)
                if item["question_id"] == question_id
            ),
            None,
        )
