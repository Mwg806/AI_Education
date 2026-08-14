"""Paper catalog, secure answer-bank lookup, sessions and fair grading."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError, ModelUnavailableError
from ai_education.domain.protocols import utc_now
from ai_education.llm.exam_grader import ConstructedResponseGrade, StructuredExamGrader
from ai_education.mysql_persistence import MySQLPersistence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BANK_ROOT = PROJECT_ROOT / "Knowledge" / "Exam" / "高考真题" / "diagnose"
HTML_TAG = re.compile(r"<[^>]+>")


class ExamDiagnosticService:
    """Keep answer data server-side and expose only public papers and scored work."""

    def __init__(
        self,
        grader: StructuredExamGrader,
        bank_root: Path = DEFAULT_BANK_ROOT,
        persistence: MySQLPersistence | None = None,
    ) -> None:
        self.grader = grader
        self.bank_root = bank_root
        self.persistence = persistence
        self._manifest = self._load_json(bank_root / "manifest.json")
        self._papers: dict[str, dict[str, Any]] = {}
        self._answers: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise InputValidationError(f"高考诊断题库文件不存在：{path.name}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputValidationError(f"高考诊断题库文件损坏：{path.name}") from exc

    @property
    def available(self) -> bool:
        return bool(self._manifest.get("paper_count"))

    def catalog(self) -> dict[str, Any]:
        return {
            "schema_version": self._manifest["schema_version"],
            "paper_count": self._manifest["paper_count"],
            "subjects": copy.deepcopy(self._manifest["subjects"]),
            "answer_content_exposed": False,
            "constructed_response_grading": "multimodal_llm" if self.grader.available else "unavailable",
        }

    def teacher_assignable_paper(self, paper_id: str) -> dict[str, Any]:
        for subject in self._manifest.get("subjects", []):
            teacher_papers = subject.get("papers", [])[5:10]
            if any(item.get("paper_id") == paper_id for item in teacher_papers):
                return self.paper(paper_id)
        raise InputValidationError(
            "教师诊断卷只能选择每个科目第 6 至第 10 套，避免与平台诊断卷重复"
        )

    def paper(self, paper_id: str) -> dict[str, Any]:
        cached = self._papers.get(paper_id)
        if cached is not None:
            return copy.deepcopy(cached)
        subject = self._subject_for_paper(paper_id)
        payload = self._load_json(self.bank_root / subject / f"{paper_id}.json")
        for question in payload.get("questions", []):
            question["stem_html"] = question.get("stem_html", "").replace(
                "/agent-api/api/v1/exam-diagnostics/assets/",
                "/api/v1/exam-diagnostics/assets/",
            )
            for option in question.get("options", []):
                option["content_html"] = option.get("content_html", "").replace(
                    "/agent-api/api/v1/exam-diagnostics/assets/",
                    "/api/v1/exam-diagnostics/assets/",
                )
        if payload.get("paper_id") != paper_id:
            raise InputValidationError("诊断卷 ID 与题库内容不一致")
        if any("correct_option" in question or "standard_answer" in question for question in payload["questions"]):
            raise InputValidationError("学生端题面包含答案字段，已拒绝发布")
        self._papers[paper_id] = payload
        return copy.deepcopy(payload)

    def _answer_bank(self, paper_id: str) -> dict[str, Any]:
        cached = self._answers.get(paper_id)
        if cached is not None:
            return cached
        subject = self._subject_for_paper(paper_id)
        payload = self._load_json(
            self.bank_root / "answers" / subject / f"{paper_id}.answers.json"
        )
        if payload.get("paper_id") != paper_id or not payload.get("generated_from_source_only"):
            raise InputValidationError("标准答案库溯源校验失败")
        self._answers[paper_id] = payload
        return payload

    def _subject_for_paper(self, paper_id: str) -> str:
        for item in self._manifest.get("subjects", []):
            if any(paper.get("paper_id") == paper_id for paper in item.get("papers", [])):
                return str(item["subject"])
        raise InputValidationError("未找到指定的高考真题诊断卷")

    def create_session(
        self,
        *,
        student_id: str,
        paper_id: str,
        grade: str,
        province_code: str,
        target_exam_year: int,
        assignment_id: str | None = None,
    ) -> dict[str, Any]:
        paper = self.paper(paper_id)
        assignment = None
        if assignment_id:
            if not self.persistence:
                raise InputValidationError("教师诊断任务需要启用 MySQL 持久化")
            assignment = self.persistence.student_exam_assignment(
                student_id, assignment_id, paper_id
            )
            if not assignment:
                raise InputValidationError("诊断任务不存在、已关闭或不属于当前学生班级")
        session_id = f"examdiag_{uuid4().hex}"
        session = {
            "session_id": session_id,
            "student_id": student_id,
            "assignment_id": assignment_id,
            "assignment_title": assignment.get("title") if assignment else None,
            "assignment_classroom_id": assignment.get("classroom_id") if assignment else None,
            "assignment_class_name": assignment.get("class_name") if assignment else None,
            "paper_id": paper_id,
            "subject": paper["subject"],
            "grade": grade,
            "province_code": province_code,
            "target_exam_year": target_exam_year,
            "status": "in_progress",
            "created_at": utc_now().isoformat(),
            "objective_answers": {},
            "constructed_grades": {},
            "question_durations": {},
            "result": None,
        }
        self._sessions[session_id] = session
        if self.persistence:
            self.persistence.save_exam_session(session)
        return {"session": self._public_session(session), "paper": paper}

    def get_session(self, session_id: str, student_id: str) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        return {"session": self._public_session(session), "paper": self.paper(session["paper_id"])}

    def _session(self, session_id: str, student_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None and self.persistence:
            session = self.persistence.load_exam_session(session_id)
            if session:
                self._sessions[session_id] = session
        if session is None:
            raise InputValidationError("高考诊断会话不存在或服务已重启，请重新选卷")
        if session["student_id"] != student_id:
            raise InputValidationError("无权访问其他学生的诊断会话")
        return session

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        grades = {
            question_id: copy.deepcopy(result)
            for question_id, result in session["constructed_grades"].items()
        }
        return {
            key: copy.deepcopy(value)
            for key, value in session.items()
            if key not in {"objective_answers", "constructed_grades"}
        } | {
            "answered_objective_count": len(session["objective_answers"]),
            "graded_constructed_count": len(grades),
            "constructed_grades": grades,
        }

    async def grade_constructed(
        self,
        *,
        session_id: str,
        student_id: str,
        question_id: str,
        image_data_urls: list[str],
        ocr_text: str,
        image_warnings: list[str],
        duration_seconds: int,
    ) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        if session["status"] != "in_progress":
            raise InputValidationError("诊断卷已提交，不能重复修改主观题")
        paper = self.paper(session["paper_id"])
        question = next((item for item in paper["questions"] if item["question_id"] == question_id), None)
        if question is None or question["type"] != "constructed_response":
            raise InputValidationError("该题不是可拍照评分的主观题")
        if not image_data_urls:
            raise InputValidationError("请至少上传一张清晰的学生作答图片")
        if not self.grader.available:
            raise ModelUnavailableError("主观题多模态评分模型当前不可用，未使用规则分数替代")
        answer_bank = self._answer_bank(session["paper_id"])
        answer = next(item for item in answer_bank["answers"] if item["question_id"] == question_id)
        candidate = await self.grader.grade(
            question=question,
            answer=answer,
            image_data_urls=image_data_urls,
            ocr_text=ocr_text,
        )
        if candidate is None:
            raise ModelUnavailableError("主观题多模态评分模型未返回结果")
        grade_result = self._validated_grade(candidate, answer, image_warnings)
        session["question_durations"][question_id] = max(1, min(duration_seconds, 14_400))
        session["constructed_grades"][question_id] = grade_result
        if self.persistence:
            self.persistence.save_exam_session(session)
        return {
            "session_id": session_id,
            "question_id": question_id,
            "grading": copy.deepcopy(grade_result),
            "standard_answer_exposed": False,
        }

    @staticmethod
    def _validated_grade(
        candidate: ConstructedResponseGrade,
        answer: dict[str, Any],
        image_warnings: list[str],
    ) -> dict[str, Any]:
        expected = float(answer["max_score"])
        criteria_total = sum(item.possible for item in candidate.criteria)
        invalid_scale = (
            abs(candidate.max_score - expected) > 0.01
            or candidate.score > expected
            or (candidate.criteria and abs(criteria_total - expected) > 0.05)
        )
        requires_review = (
            candidate.requires_manual_review
            or not candidate.image_is_legible
            or candidate.confidence < 0.65
            or invalid_scale
        )
        score = None if invalid_scale or not candidate.image_is_legible else round(candidate.score, 2)
        review_reasons = [candidate.review_reason] if candidate.review_reason else []
        if invalid_scale:
            review_reasons.append("模型评分量表与本题满分不一致")
        if candidate.confidence < 0.65:
            review_reasons.append("模型评分置信度低于 65%")
        review_reasons.extend(image_warnings)
        return {
            "score": score,
            "max_score": expected,
            "recognized_student_work": candidate.recognized_student_work,
            "criteria": [item.model_dump(mode="json") for item in candidate.criteria],
            "strengths": candidate.strengths,
            "issues": candidate.issues,
            "feedback": candidate.feedback,
            "confidence": candidate.confidence,
            "image_is_legible": candidate.image_is_legible,
            "requires_manual_review": requires_review,
            "review_reason": "；".join(dict.fromkeys(item for item in review_reasons if item)),
            "graded_by": "multimodal_llm",
        }

    def submit(
        self,
        *,
        session_id: str,
        student_id: str,
        objective_answers: list[dict[str, Any]],
        question_durations: dict[str, int],
    ) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        if session["status"] != "in_progress":
            return copy.deepcopy(session["result"])
        paper = self.paper(session["paper_id"])
        bank = self._answer_bank(session["paper_id"])
        questions = {item["question_id"]: item for item in paper["questions"]}
        answer_map = {item["question_id"]: item for item in bank["answers"]}
        unknown_duration_ids = set(question_durations) - set(questions)
        if unknown_duration_ids:
            raise InputValidationError(
                "题目用时包含不属于本卷的题目",
                details={"unknown_question_ids": sorted(unknown_duration_ids)},
            )
        invalid_durations = {
            question_id: value
            for question_id, value in question_durations.items()
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 14_400
        }
        if invalid_durations:
            raise InputValidationError("题目用时必须为 1 到 14400 秒的整数")
        required_objective = {
            item["question_id"] for item in paper["questions"] if item["type"] == "multiple_choice"
        }
        submitted = {item["question_id"]: item for item in objective_answers}
        if len(submitted) != len(objective_answers):
            raise InputValidationError("同一道选择题不能重复提交")
        if set(submitted) != required_objective:
            missing = sorted(required_objective - set(submitted))
            raise InputValidationError("请完成全部选择题后再提交", details={"missing": missing})

        objective_results: list[dict[str, Any]] = []
        session["objective_answers"] = copy.deepcopy(submitted)
        session["question_durations"].update(copy.deepcopy(question_durations))
        for question_id, answer in submitted.items():
            duration = answer.get("duration_seconds")
            if duration is not None:
                session["question_durations"][question_id] = duration
        for question_id in sorted(required_objective, key=lambda item: questions[item]["sequence"]):
            selected = submitted[question_id]["selected_option"]
            correct = answer_map[question_id]["correct_option"]
            score = float(questions[question_id]["max_score"] if selected == correct else 0)
            objective_results.append({
                "question_id": question_id,
                "selected_option": selected,
                "score": score,
                "max_score": questions[question_id]["max_score"],
                "is_correct": selected == correct,
            })

        constructed_results = [
            {"question_id": question_id, **copy.deepcopy(result)}
            for question_id, result in session["constructed_grades"].items()
        ]
        required_constructed = {
            item["question_id"] for item in paper["questions"] if item["type"] == "constructed_response"
        }
        graded_ids = set(session["constructed_grades"])
        pending = sorted(required_constructed - graded_ids)
        review_ids = sorted(
            question_id
            for question_id, result in session["constructed_grades"].items()
            if result["requires_manual_review"] or result["score"] is None
        )
        earned = sum(item["score"] for item in objective_results)
        earned += sum(item["score"] or 0 for item in constructed_results)
        possible_scored = sum(item["max_score"] for item in objective_results)
        possible_scored += sum(item["max_score"] for item in constructed_results if item["score"] is not None)
        status = "completed"
        if review_ids:
            status = "manual_review_required"
        elif pending:
            status = "provisional"
        evidence_records = self._evidence_records(
            session, paper, objective_results, constructed_results
        )
        completed_at = utc_now().isoformat()
        learning_record = self._learning_record(
            session, paper, objective_results, constructed_results, completed_at, status
        )
        result = {
            "session_id": session_id,
            "paper_id": session["paper_id"],
            "subject": session["subject"],
            "status": status,
            "score": round(earned, 2),
            "scored_max": round(possible_scored, 2),
            "paper_max": paper["total_score"],
            "objective_results": objective_results,
            "constructed_results": constructed_results,
            "pending_constructed_question_ids": pending,
            "manual_review_question_ids": review_ids,
            "evidence_records": evidence_records,
            "learning_record": learning_record,
            "standard_answer_exposed": False,
            "completed_at": completed_at,
        }
        session["status"] = status
        session["result"] = result
        if self.persistence:
            self.persistence.save_exam_session(session)
        return copy.deepcopy(result)

    def attach_learning_diagnosis(
        self,
        session_id: str,
        student_id: str,
        diagnosis: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Persist the agent report beside the exam learning record for later retrieval."""
        session = self._session(session_id, student_id)
        if session["result"] is None:
            raise InputValidationError("诊断卷尚未提交")
        session["result"]["learning_diagnosis"] = copy.deepcopy(diagnosis)
        if self.persistence:
            self.persistence.save_exam_session(session)
        return copy.deepcopy(session["result"])

    @staticmethod
    def _learning_record(
        session: dict[str, Any],
        paper: dict[str, Any],
        objective_results: list[dict[str, Any]],
        constructed_results: list[dict[str, Any]],
        completed_at: str,
        status: str,
    ) -> dict[str, Any]:
        """Build a student-facing record from the same evidence used by diagnosis."""
        result_map = {
            item["question_id"]: item for item in [*objective_results, *constructed_results]
        }
        knowledge: dict[str, dict[str, Any]] = {}
        question_records: list[dict[str, Any]] = []
        for question in paper["questions"]:
            question_id = question["question_id"]
            scored = result_map.get(question_id)
            score = scored.get("score") if scored else None
            max_score = float(question["max_score"])
            duration = int(session["question_durations"].get(question_id, 1))
            is_correct: bool | None = None
            if scored is not None and score is not None:
                is_correct = bool(scored.get("is_correct", abs(float(score) - max_score) < 0.01))
            question_records.append({
                "question_id": question_id,
                "sequence": question["sequence"],
                "question_type": question["type"],
                "knowledge_tags": copy.deepcopy(question["knowledge_tags"]),
                "duration_seconds": duration,
                "score": score,
                "max_score": max_score,
                "is_correct": is_correct,
                "requires_manual_review": bool(scored and scored.get("requires_manual_review")),
                "source_title": question["source"]["source_title"],
                "source_question_number": question["source"]["original_number"],
            })
            for tag in question["knowledge_tags"] or ["未分类知识点"]:
                summary = knowledge.setdefault(tag, {
                    "knowledge_tag": tag,
                    "question_count": 0,
                    "scored_question_count": 0,
                    "full_credit_count": 0,
                    "score": 0.0,
                    "max_score": 0.0,
                    "duration_seconds": 0,
                })
                summary["question_count"] += 1
                summary["duration_seconds"] += duration
                if score is not None:
                    summary["scored_question_count"] += 1
                    summary["score"] += float(score)
                    summary["max_score"] += max_score
                    if abs(float(score) - max_score) < 0.01:
                        summary["full_credit_count"] += 1

        knowledge_statistics = []
        for item in knowledge.values():
            item["score"] = round(item["score"], 2)
            item["max_score"] = round(item["max_score"], 2)
            item["accuracy"] = round(item["score"] / item["max_score"], 4) if item["max_score"] else None
            item["average_duration_seconds"] = round(
                item["duration_seconds"] / item["question_count"]
            )
            knowledge_statistics.append(item)
        knowledge_statistics.sort(
            key=lambda item: (item["accuracy"] is None, item["accuracy"] or 0, -item["question_count"])
        )
        objective_correct = sum(1 for item in objective_results if item["is_correct"])
        earned = sum(float(item["score"] or 0) for item in result_map.values())
        return {
            "record_type": "gaokao_diagnostic",
            "assessment_id": session["session_id"],
            "student_id": session["student_id"],
            "subject": session["subject"],
            "paper_id": session["paper_id"],
            "paper_title": paper["title"],
            "started_at": session["created_at"],
            "completed_at": completed_at,
            "total_duration_seconds": sum(item["duration_seconds"] for item in question_records),
            "objective_accuracy": round(objective_correct / len(objective_results), 4) if objective_results else 0.0,
            "score_accuracy": round(earned / float(paper["total_score"]), 4) if paper["total_score"] else 0.0,
            "is_provisional": status != "completed",
            "knowledge_statistics": knowledge_statistics,
            "question_records": question_records,
        }

    @staticmethod
    def _evidence_records(
        session: dict[str, Any],
        paper: dict[str, Any],
        objective_results: list[dict[str, Any]],
        constructed_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        question_map = {item["question_id"]: item for item in paper["questions"]}
        scored = [*objective_results]
        scored.extend(item for item in constructed_results if item["score"] is not None)
        records: list[dict[str, Any]] = []
        for result in scored:
            question = question_map[result["question_id"]]
            error_tags: list[str] = []
            if result["score"] < result["max_score"]:
                error_tags.append(
                    "incorrect_option" if question["type"] == "multiple_choice" else "constructed_response_gap"
                )
            records.append({
                "assessment_id": session["session_id"],
                "assessment_type": "diagnostic",
                "question_id": question["question_id"],
                "knowledge_tags": question["knowledge_tags"],
                "question_type": "选择题" if question["type"] == "multiple_choice" else "解答题",
                "ability_tags": [],
                "difficulty": question["difficulty"],
                "score": result["score"],
                "max_score": result["max_score"],
                "duration_seconds": session["question_durations"].get(question["question_id"], 1),
                "error_tags": error_tags,
                "step_trace": result.get("recognized_student_work"),
                "source_id": f"gaokao:{question['source']['document_sha256']}:{question['source']['original_number']}",
                "occurred_at": datetime.fromisoformat(session["created_at"]).isoformat(),
            })
        return records
