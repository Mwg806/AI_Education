from __future__ import annotations

import unittest

from ai_education.agents.programming_career import CareerProgrammingLearningAgent
from ai_education.domain.enums import ActorType, StandardStatus
from ai_education.domain.programming_learning import (
    CareerCodeSubmissionInput,
    CareerCodingTaskInput,
    CareerDiagnosticSubmission,
    CareerProgrammingProfileInput,
    ProgrammingDiagnosticAnswer,
)
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.programming_learning_repository import ProgrammingLearningRepository
from ai_education.services.programming_career import CareerProgrammingLearningService
from ai_education.services.programming_code_runner import ProgrammingCodeRunner
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService

AUTH_PROFILE = {
    "studentId": "career_student",
    "studentName": "职业训练同学",
    "grade": "grade_12",
}


class CareerProgrammingAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = ProgrammingLearningRepository()
        self.knowledge = ProgrammingKnowledgeService()
        self.service = CareerProgrammingLearningService(self.repository, self.knowledge)

    def configure(self) -> dict:
        return self.service.configure_career_profile(
            "career_student",
            CareerProgrammingProfileInput(
                target_level="intern",
                deadline_days=90,
                weekly_hours=10,
                current_identity="undergraduate",
                python_experience="basic",
                project_experience="none",
                interview_experience="none",
            ),
            AUTH_PROFILE,
        )

    def test_dashboard_is_restrained_career_mvp(self) -> None:
        initial = self.service.dashboard("career_student", AUTH_PROFILE)
        self.assertFalse(initial["profile"]["configured"])
        self.assertEqual(initial["role"]["role_id"], "python_backend_engineer")
        self.assertEqual(initial["next_action"], "完善职业目标")
        self.configure()
        dashboard = self.service.dashboard("career_student", AUTH_PROFILE)
        self.assertTrue(dashboard["profile"]["configured"])
        self.assertEqual(len(dashboard["skill_domains"]), 6)
        self.assertEqual(dashboard["next_action"], "完成 6 题基础诊断")

    def test_diagnostic_updates_evidence_and_gap(self) -> None:
        self.configure()
        diagnostic = self.service.create_career_diagnostic("career_student")
        self.assertNotIn("answer_index", diagnostic["questions"][0])
        source = self.knowledge.career_diagnostic_questions()
        result = self.service.submit_career_diagnostic(
            "career_student",
            diagnostic["diagnostic_id"],
            CareerDiagnosticSubmission(
                answers=[
                    ProgrammingDiagnosticAnswer(
                        question_id=item["question_id"],
                        selected_option=item["answer_index"],
                        confidence=0.8,
                    )
                    for item in source
                ]
            ),
        )
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(len(self.repository.list_events("career_student")), 6)
        self.assertEqual(
            self.service.dashboard("career_student", AUTH_PROFILE)["next_action"],
            "开始推荐训练",
        )

    def test_coding_failure_hint_then_pass_updates_mastery(self) -> None:
        self.configure()
        task = self.service.create_coding_task(
            "career_student", CareerCodingTaskInput(skill_id="FASTAPI_SCHEMA")
        )
        failed = self.service.submit_coding_task(
            "career_student",
            task["task_id"],
            CareerCodeSubmissionInput(code=task["starter_code"]),
        )
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["feedback"]["hint_level"], 1)
        passed = self.service.submit_coding_task(
            "career_student",
            task["task_id"],
            CareerCodeSubmissionInput(
                code=(
                    "def build_user_response(user_id: int, name: str) -> dict:\n"
                    "    if not isinstance(user_id, int) or user_id <= 0:\n"
                    "        raise ValueError('invalid id')\n"
                    "    cleaned = name.strip()\n"
                    "    if not cleaned:\n"
                    "        raise ValueError('invalid name')\n"
                    "    return {'id': user_id, 'name': cleaned}"
                )
            ),
        )
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["execution"]["tests_failed"], 0)
        self.assertGreater(
            passed["mastery_update"]["mastery"],
            passed["mastery_update"]["previous_mastery"],
        )

    def test_runner_rejects_imports(self) -> None:
        result = ProgrammingCodeRunner().run("import os", ["assert True"])
        self.assertEqual(result["execution_status"], "rejected")
        self.assertEqual(result["error_type"], "security")

    async def test_langgraph_routes_v2_dashboard(self) -> None:
        self.configure()
        agent = CareerProgrammingLearningAgent(self.service)
        response = await agent.ainvoke(
            AgentRequest(
                student_id="career_student",
                actor=Operator(type=ActorType.STUDENT, id="career_student"),
                intent="get_programming_dashboard",
                context={"student_profile": AUTH_PROFILE},
            )
        )
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        self.assertEqual(response.result["agent_version"], "2.0")


if __name__ == "__main__":
    unittest.main()
