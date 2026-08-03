"""LLM-generated, deterministically scored quick diagnostic sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from ai_education.config import Settings
from ai_education.core.errors import InputValidationError, PlannerModelUnavailableError
from ai_education.llm.diagnostic_generator import StructuredDiagnosticGenerator
from ai_education.services.curriculum_catalog import SUBJECT_LABELS, CurriculumCatalogService

FOUNDATION_DIMENSIONS = {"prerequisite", "concept", "basic_application"}
APPLICATION_DIMENSIONS = {"integrated_application", "transfer"}


class DiagnosticService:
    def __init__(
        self,
        catalog: CurriculumCatalogService,
        generator: StructuredDiagnosticGenerator,
        settings: Settings,
    ) -> None:
        self.catalog = catalog
        self.generator = generator
        self.settings = settings
        self.sessions: dict[str, dict[str, Any]] = {}

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.generator.available:
            raise PlannerModelUnavailableError(
                "快速诊断模型尚未配置，不会使用固定题目模板代替",
                details={"provider": self.settings.llm_provider, "model": self.settings.llm_model},
            )
        subject = str(payload["subject"])
        progress = self._progress_context(
            subject,
            str(payload["curriculum_version"]),
            str(payload["chapter_id"]),
        )
        context = {
            "subject_label": SUBJECT_LABELS[subject],
            "grade": str(payload["grade"]),
            "progress_label": progress["label"],
            "knowledge_context": progress["context"],
        }
        try:
            generated = await self.generator.generate(context)
        except Exception as exc:
            raise PlannerModelUnavailableError(
                "快速诊断题生成失败，不会降级为固定题库模板",
                details={
                    "provider": self.settings.llm_provider,
                    "model": self.settings.llm_model,
                    "stage": "diagnostic_generation",
                },
            ) from exc
        if generated is None:
            raise PlannerModelUnavailableError("快速诊断模型没有返回有效题目")
        diagnostic_id = f"diag_{uuid4().hex[:14]}"
        questions = []
        for index, question in enumerate(generated.questions, start=1):
            item = question.model_dump(mode="json")
            item["question_id"] = f"{diagnostic_id}_q{index:02d}"
            questions.append(item)
        session = {
            "diagnostic_id": diagnostic_id,
            "student_id": str(payload["student_id"]),
            "subject": subject,
            "chapter_id": str(payload["chapter_id"]),
            "progress_label": progress["label"],
            "status": "in_progress",
            "questions": questions,
            "created_at": datetime.now().astimezone().isoformat(),
            "result": None,
        }
        self.sessions[diagnostic_id] = session
        return self._public_session(session)

    def submit(
        self,
        diagnostic_id: str,
        student_id: str,
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session = self.sessions.get(diagnostic_id)
        if not session or session["student_id"] != student_id:
            raise InputValidationError("快速诊断会话不存在或不属于当前学生")
        if session["status"] == "completed":
            return session["result"]
        by_question = {item["question_id"]: item for item in session["questions"]}
        by_response = {str(item["question_id"]): item for item in responses}
        if set(by_response) != set(by_question):
            raise InputValidationError("必须完成全部 10 道诊断题后再提交")

        now = datetime.now().astimezone()
        evidence: list[dict[str, Any]] = []
        reviews = []
        dimension_scores: dict[str, list[float]] = {
            "foundation": [],
            "application": [],
        }
        calibration_scores = []
        correct_count = 0
        for question_id, question in by_question.items():
            response = by_response[question_id]
            selected = int(response["selected_option"])
            if selected < 0 or selected > 3:
                raise InputValidationError("诊断题选项下标必须在 0～3 之间")
            correct = selected == int(question["correct_option"])
            correct_count += int(correct)
            elapsed = max(1, min(int(response.get("response_time_seconds", 0)), 1800))
            expected = max(int(question["expected_seconds"]), 1)
            time_efficiency = max(0.0, 1 - abs(elapsed - expected) / expected)
            difficulty = float(question["difficulty"])
            difficulty_adjusted = min(1.0, (0.7 + 0.6 * difficulty)) if correct else 0.0
            performance = (
                min(1.0, 0.8 * difficulty_adjusted + 0.2 * time_efficiency)
                if correct
                else 0.0
            )
            group = (
                "foundation"
                if question["dimension"] in FOUNDATION_DIMENSIONS
                else "application"
            )
            dimension_scores[group].append(performance)
            confidence = min(max(float(response.get("confidence", 0.5)), 0), 1)
            calibration_scores.append(1 - abs(confidence - float(correct)))
            knowledge_id = f"{session['chapter_id']}_{group}"
            evidence.append(
                {
                    "knowledge_id": knowledge_id,
                    "score": round(performance, 3),
                    "weight": round(0.72 + 0.25 * difficulty, 3),
                    "source_type": "adaptive_diagnostic",
                    "source_id": f"{diagnostic_id}:{question_id}",
                    "description": (
                        f"{session['progress_label']}快速诊断：{question['knowledge_focus']}"
                    ),
                    "observed_at": now.isoformat(),
                    "error_tags": [] if correct else ["diagnostic_incorrect"],
                }
            )
            reviews.append(
                {
                    "question_id": question_id,
                    "selected_option": selected,
                    "correct_option": question["correct_option"],
                    "correct": correct,
                    "explanation": question["explanation"],
                }
            )

        foundation_score = self._average(dimension_scores["foundation"])
        application_score = self._average(dimension_scores["application"])
        result = {
            "diagnostic_id": diagnostic_id,
            "status": "completed",
            "question_count": len(by_question),
            "correct_count": correct_count,
            "objective_score": round(correct_count / len(by_question), 3),
            "foundation_score": round(foundation_score, 3),
            "application_score": round(application_score, 3),
            "metacognitive_accuracy": round(self._average(calibration_scores), 3),
            "objective_evidence_count": len(evidence),
            "knowledge_evidence": evidence,
            "reviews": reviews,
            "completed_at": now.isoformat(),
        }
        session["status"] = "completed"
        session["result"] = result
        return result

    def _progress_context(self, subject: str, edition_id: str, progress_id: str) -> dict[str, str]:
        catalog = self.catalog.subject_catalog(subject)
        edition = next(
            (item for item in catalog["editions"] if item["id"] == edition_id),
            None,
        )
        if edition:
            for volume in edition.get("volumes", []):
                for chapter in volume.get("chapters", []):
                    if chapter["id"] == progress_id:
                        label = (
                            f"{volume.get('label', '')} "
                            f"{chapter.get('title', progress_id)}"
                        ).strip()
                        evidence = chapter.get("evidence", {})
                        return {
                            "label": label,
                            "context": (
                                f"教材章节：{label}；目录证据页："
                                f"{evidence.get('pdf_page', '待核验')}"
                            ),
                        }
        module = next(
            (item for item in catalog["standard_modules"] if item["id"] == progress_id),
            None,
        )
        if module:
            topics = "、".join(module.get("topics", []))
            return {
                "label": module["label"],
                "context": f"课程标准模块：{module['label']}；主题：{topics}",
            }
        raise InputValidationError("当前诊断范围不在已核验教材或课程标准目录中")

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        questions = [
            {
                key: value
                for key, value in question.items()
                if key not in {"correct_option", "explanation"}
            }
            for question in session["questions"]
        ]
        return {
            "diagnostic_id": session["diagnostic_id"],
            "student_id": session["student_id"],
            "subject": session["subject"],
            "chapter_id": session["chapter_id"],
            "progress_label": session["progress_label"],
            "status": session["status"],
            "question_count": len(questions),
            "questions": questions,
            "created_at": session["created_at"],
        }
