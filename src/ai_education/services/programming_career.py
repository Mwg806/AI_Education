"""Career-driven Python backend training workflow for Agent 6 V2."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError
from ai_education.domain.programming_learning import (
    CareerCodeSubmissionInput,
    CareerCodingTaskInput,
    CareerDiagnosticSubmission,
    CareerProgrammingProfileInput,
)
from ai_education.services.programming_code_runner import ProgrammingCodeRunner
from ai_education.services.programming_learning import ProgrammingLearningService, _now


class CareerProgrammingLearningService(ProgrammingLearningService):
    """Keeps the V1 contracts available while making the V2 loop primary."""

    def __init__(self, repository, knowledge) -> None:
        super().__init__(repository, knowledge)
        self.code_runner = ProgrammingCodeRunner()

    def dashboard(self, student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        stored = self.repository.load_profile(student_id)
        configured = bool(stored and stored.get("career_agent_version") == "2.0")
        profile = stored if configured else self._default_career_profile(student_id, auth_profile)
        skills = self._career_skill_states(student_id)
        gaps = sorted(skills, key=lambda item: (item["mastery"], -item["importance"]))[:4]
        task_records = self.repository.list_records(
            student_id, record_type="career_coding_task", limit=20
        )
        current = next(
            (item["payload"] for item in task_records if item["status"] == "in_progress"),
            None,
        )
        diagnostic_done = any(
            item["status"] == "completed"
            for item in self.repository.list_records(
                student_id, record_type="career_diagnostic", limit=5
            )
        )
        recent = self.repository.list_records(student_id, record_type="career_submission", limit=4)
        return {
            "agent_version": "2.0",
            "profile": {**profile, "configured": configured},
            "role": self.knowledge.career_role(),
            "readiness": self._career_readiness(skills),
            "priority_gaps": gaps,
            "skill_domains": self._group_skill_domains(skills),
            "learning_plan": self._career_learning_plan(gaps),
            "current_task": self._public_task(current) if current else None,
            "recent_submissions": [item["payload"] for item in recent],
            "next_action": (
                "完善职业目标"
                if not configured
                else "完成 6 题基础诊断"
                if not diagnostic_done
                else "继续当前编程任务"
                if current
                else "开始推荐训练"
            ),
            "progress": {
                "diagnostic_completed": diagnostic_done,
                "coding_attempts": len(
                    self.repository.list_records(
                        student_id, record_type="career_submission", limit=50
                    )
                ),
                "completed_tasks": sum(item["status"] == "completed" for item in task_records),
            },
            "runner": {
                "mode": self.code_runner.mode,
                "production_ready": False,
                "notice": self.code_runner.safety_notice,
            },
            "knowledge": {
                "content_version": self.knowledge.career_version,
                "sources": self.knowledge.career_sources(),
            },
        }

    def configure_career_profile(
        self,
        student_id: str,
        body: CareerProgrammingProfileInput,
        auth_profile: dict[str, Any],
    ) -> dict[str, Any]:
        previous = self.repository.load_profile(student_id) or {}
        payload = {
            "student_id": student_id,
            "student_name": auth_profile.get("studentName", "同学"),
            "career_agent_version": "2.0",
            "target_role": "python_backend_engineer",
            **body.model_dump(mode="json"),
            "learning_mode": "advanced" if body.python_experience == "project" else "beginner",
            "target_direction": "software_engineering",
            "weekly_available_minutes": body.weekly_hours * 60,
            "effective_weekly_minutes": body.weekly_hours * 60,
            "max_session_minutes": 45,
            "exam_period": False,
            "profile_version": int(previous.get("profile_version", 0)) + 1,
            "updated_at": _now(),
        }
        self.repository.save_profile(payload)
        return {**payload, "configured": True}

    def create_career_diagnostic(self, student_id: str) -> dict[str, Any]:
        self._require_career_profile(student_id)
        diagnostic_id = f"career_diag_{uuid4().hex}"
        questions = self.knowledge.career_diagnostic_questions()
        private = {
            "diagnostic_id": diagnostic_id,
            "questions": questions,
            "created_at": _now(),
        }
        self._save_simple_record(student_id, diagnostic_id, "career_diagnostic", private)
        visible = [
            {
                key: value
                for key, value in item.items()
                if key not in {"answer_index", "explanation"}
            }
            for item in questions
        ]
        return {
            "diagnostic_id": diagnostic_id,
            "status": "in_progress",
            "estimated_minutes": 8,
            "questions": visible,
            "answer_content_exposed": False,
        }

    def submit_career_diagnostic(
        self, student_id: str, diagnostic_id: str, body: CareerDiagnosticSubmission
    ) -> dict[str, Any]:
        record = self.repository.load_record(
            diagnostic_id, student_id=student_id, record_type="career_diagnostic"
        )
        if record["status"] != "in_progress":
            raise InputValidationError("该职业诊断已经提交")
        questions = record["payload"]["questions"]
        by_id = {item["question_id"]: item for item in questions}
        if {answer.question_id for answer in body.answers} != set(by_id):
            raise InputValidationError("请完成全部诊断题")
        results: list[dict[str, Any]] = []
        for answer in body.answers:
            question = by_id[answer.question_id]
            correct = answer.selected_option == question["answer_index"]
            state = self._record_evidence(
                student_id,
                skill_id=question["skill_id"],
                event_type="quiz",
                source_id=diagnostic_id,
                score=1.0 if correct else 0.0,
                independence=max(0.4, answer.confidence),
                reasoning=0.6,
                verification=0.7,
                hint_level=0,
                description=f"Python 后端基线诊断：{question['dimension']}",
            )
            results.append(
                {
                    "question_id": answer.question_id,
                    "skill_id": question["skill_id"],
                    "correct": correct,
                    "explanation": question["explanation"],
                    "mastery_update": state,
                }
            )
        correct_count = sum(item["correct"] for item in results)
        completed = {
            "diagnostic_id": diagnostic_id,
            "status": "completed",
            "score": round(correct_count / len(results), 4),
            "correct_count": correct_count,
            "question_count": len(results),
            "results": results,
            "priority_gaps": [
                item["name"]
                for item in sorted(
                    self._career_skill_states(student_id),
                    key=lambda value: value["mastery"],
                )[:3]
            ],
            "next": "开始第一个针对性编程任务",
        }
        record.update(status="completed", payload=completed, updated_at=_now())
        self.repository.save_record(record)
        return completed

    def create_coding_task(self, student_id: str, body: CareerCodingTaskInput) -> dict[str, Any]:
        self._require_career_profile(student_id)
        active = next(
            (
                item["payload"]
                for item in self.repository.list_records(
                    student_id, record_type="career_coding_task", limit=20
                )
                if item["status"] == "in_progress"
            ),
            None,
        )
        if active:
            return self._public_task(active)
        template = self._select_coding_task(student_id, body.skill_id, body.difficulty)
        instance_id = f"career_task_{uuid4().hex}"
        public = self._public_task({**template, "task_id": instance_id})
        private = {
            **public,
            "template_task_id": template["task_id"],
            "hidden_tests": template["hidden_tests"],
        }
        self._save_simple_record(student_id, instance_id, "career_coding_task", private)
        return public

    def submit_coding_task(
        self, student_id: str, task_id: str, body: CareerCodeSubmissionInput
    ) -> dict[str, Any]:
        task_record = self.repository.load_record(
            task_id, student_id=student_id, record_type="career_coding_task"
        )
        task = task_record["payload"]
        if task_record["status"] == "completed":
            raise InputValidationError("该任务已经通过，请开始下一项训练")
        submissions = [
            item
            for item in self.repository.list_records(
                student_id, record_type="career_submission", limit=50
            )
            if item["payload"].get("task_id") == task_id
        ]
        attempt = len(submissions) + 1
        execution = self.code_runner.run(body.code, task["hidden_tests"])
        passed = execution["execution_status"] == "passed"
        hint_level = 0 if passed else min(4, attempt)
        template = self.knowledge.coding_task(task["template_task_id"])
        if template is None:
            raise InputValidationError("任务模板不存在")
        hint = "已通过，无需提示" if passed else template["hints"][hint_level - 1]
        submission_id = f"career_submission_{uuid4().hex}"
        test_count = max(1, len(task["hidden_tests"]))
        mastery = self._record_evidence(
            student_id,
            skill_id=task["skill_id"],
            event_type="coding",
            source_id=submission_id,
            score=1.0 if passed else max(0.1, execution["tests_passed"] / test_count),
            independence=max(0.35, 1 - hint_level * 0.12),
            reasoning=0.75 if passed else 0.5,
            verification=1.0 if passed else 0.45,
            hint_level=hint_level,
            description=f"编程任务：{task['title']}（第 {attempt} 次）",
        )
        result = {
            "submission_id": submission_id,
            "task_id": task_id,
            "attempt": attempt,
            "passed": passed,
            "execution": execution,
            "diagnosis": {
                "error_type": execution["error_type"],
                "message": execution["message"],
                "related_skill_id": task["skill_id"],
            },
            "feedback": {
                "hint_level": hint_level,
                "hint": hint,
                "solution_unlocked": False,
                "teaching_policy": "方向 → 知识点 → 伪代码 → 关键片段",
            },
            "mastery_update": mastery,
            "next_action": "进入下一项训练" if passed else "根据提示修改后再次提交",
            "created_at": _now(),
        }
        self._save_simple_record(
            student_id,
            submission_id,
            "career_submission",
            result,
            status="passed" if passed else "needs_revision",
        )
        if passed:
            task_record.update(status="completed", updated_at=_now())
            task_record["payload"] = {**task, "status": "completed"}
            self.repository.save_record(task_record)
        return result

    def get_coding_hint(self, student_id: str, task_id: str) -> dict[str, Any]:
        record = self.repository.load_record(
            task_id, student_id=student_id, record_type="career_coding_task"
        )
        template = self.knowledge.coding_task(record["payload"]["template_task_id"])
        if template is None:
            raise InputValidationError("任务模板不存在")
        attempts = len(
            [
                item
                for item in self.repository.list_records(
                    student_id, record_type="career_submission", limit=50
                )
                if item["payload"].get("task_id") == task_id
            ]
        )
        level = min(4, max(1, attempts + 1))
        return {
            "task_id": task_id,
            "hint_level": level,
            "hint": template["hints"][level - 1],
            "solution_unlocked": False,
        }

    def _require_career_profile(self, student_id: str) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        if not profile or profile.get("career_agent_version") != "2.0":
            raise InputValidationError("请先设置 Python 后端职业目标")
        return profile

    def _career_skill_states(self, student_id: str) -> list[dict[str, Any]]:
        stored = {item["skill_id"]: item for item in self.repository.list_skill_states(student_id)}
        result = []
        for skill in self.knowledge.career_skills():
            state = stored.get(skill["skill_id"], {})
            mastery = float(state.get("mastery", 0.15))
            result.append(
                {
                    **skill,
                    "mastery": mastery,
                    "confidence": float(state.get("confidence", 0.1)),
                    "evidence_count": int(state.get("evidence_count", 0)),
                    "level": state.get("level", "L0"),
                }
            )
        return result

    @staticmethod
    def _career_readiness(skills: list[dict[str, Any]]) -> dict[str, Any]:
        weight = sum(float(item["importance"]) for item in skills)
        score = sum(float(item["mastery"]) * float(item["importance"]) for item in skills)
        value = round(score / max(weight, 1), 4)
        return {
            "score": value,
            "percent": round(value * 100),
            "label": "接近实习要求"
            if value >= 0.65
            else "正在打基础"
            if value >= 0.35
            else "起步阶段",
            "explanation": "按岗位重要度汇总已记录的测评与代码证据；无证据技能按 15% 起始值计算。",
        }

    @staticmethod
    def _group_skill_domains(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in skills:
            grouped.setdefault(item["domain"], []).append(item)
        return [
            {
                "domain": domain,
                "mastery": round(sum(item["mastery"] for item in items) / len(items), 4),
                "skills": items,
            }
            for domain, items in grouped.items()
        ]

    def _career_learning_plan(self, gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gap_ids = {item["skill_id"] for item in gaps}
        return [
            {
                **phase,
                "priority": "current" if gap_ids.intersection(phase["skills"]) else "later",
                "objective": phase["outcome"],
                "task": "完成对应知识点训练和自动测试",
                "acceptance": "至少一次独立提交通过全部测试",
                "estimated_hours": 12 + int(phase["phase"]) * 4,
            }
            for phase in self.knowledge.learning_phases()
        ]

    def _select_coding_task(
        self, student_id: str, skill_id: str | None, difficulty: int | None
    ) -> dict[str, Any]:
        tasks = self.knowledge.coding_tasks()
        completed_templates = {
            item["payload"].get("template_task_id")
            for item in self.repository.list_records(
                student_id, record_type="career_coding_task", limit=50
            )
            if item["status"] == "completed"
        }
        candidates = [item for item in tasks if item["task_id"] not in completed_templates] or tasks
        if skill_id:
            matching = [item for item in candidates if item["skill_id"] == skill_id]
            if matching:
                candidates = matching
        if difficulty:
            candidates.sort(key=lambda item: abs(item["difficulty"] - difficulty))
        mastery = {
            item["skill_id"]: item["mastery"] for item in self._career_skill_states(student_id)
        }
        return min(candidates, key=lambda item: mastery.get(item["skill_id"], 0.15))

    @staticmethod
    def _public_task(task: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in task.items()
            if key not in {"hidden_tests", "template_task_id", "hints"}
        }

    @staticmethod
    def _default_career_profile(student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "student_id": student_id,
            "student_name": auth_profile.get("studentName", "同学"),
            "career_agent_version": "2.0",
            "target_role": "python_backend_engineer",
            "target_level": "intern",
            "deadline_days": 90,
            "weekly_hours": 10,
            "current_identity": "undergraduate",
            "python_experience": "basic",
            "project_experience": "none",
            "interview_experience": "none",
            "profile_version": 0,
        }
