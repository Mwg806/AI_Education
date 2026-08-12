from __future__ import annotations

import unittest

from ai_education.agents.programming_learning import ProgrammingLearningAgent
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus
from ai_education.domain.programming_learning import (
    ProgrammingCodeReviewInput,
    ProgrammingDiagnosticAnswer,
    ProgrammingDiagnosticSubmission,
    ProgrammingInterviewAnswerInput,
    ProgrammingInterviewCreateInput,
    ProgrammingProfileInput,
    ProgrammingProjectHintInput,
    ProgrammingProjectRecommendationInput,
)
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.programming_learning_repository import ProgrammingLearningRepository
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService
from ai_education.services.programming_learning import ProgrammingLearningService

AUTH_PROFILE = {
    "role": "student",
    "studentId": "student_programming",
    "studentName": "编程同学",
    "grade": "grade_11",
    "provinceCode": "43",
    "targetExamYear": 2027,
}


class ProgrammingLearningAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = ProgrammingLearningRepository()
        self.knowledge = ProgrammingKnowledgeService()
        self.service = ProgrammingLearningService(self.repository, self.knowledge)
        self.profile = ProgrammingProfileInput(
            learning_mode="beginner",
            target_direction="computer_science_exploration",
            weekly_available_minutes=180,
            max_session_minutes=40,
            exam_period=True,
            programming_months=0,
            project_count=0,
            interests=["学习工具", "数据分析"],
        )

    def configure(self) -> dict:
        return self.service.update_profile("student_programming", self.profile, AUTH_PROFILE)

    def test_profile_creates_roadmap_and_exam_period_reduces_load(self) -> None:
        result = self.configure()
        self.assertEqual(result["effective_weekly_minutes"], 90)
        self.assertEqual(result["roadmap"]["duration_weeks"], 16)
        self.assertTrue(result["roadmap"]["exam_period_adjustment"]["active"])
        dashboard = self.service.dashboard("student_programming", AUTH_PROFILE)
        self.assertTrue(dashboard["profile"]["configured"])
        self.assertEqual(dashboard["knowledge"]["supported_languages"], ["Python"])

    def test_diagnostic_hides_answers_then_creates_bounded_evidence(self) -> None:
        self.configure()
        diagnostic = self.service.create_diagnostic("student_programming")
        self.assertFalse(diagnostic["answer_content_exposed"])
        self.assertNotIn("answer_index", diagnostic["questions"][0])
        source = self.knowledge.diagnostic_questions()
        answers = [
            ProgrammingDiagnosticAnswer(
                question_id=item["question_id"],
                selected_option=item["answer_index"],
                confidence=0.8,
            )
            for item in source
        ]
        result = self.service.submit_diagnostic(
            "student_programming",
            diagnostic["diagnostic_id"],
            ProgrammingDiagnosticSubmission(answers=answers),
        )
        self.assertEqual(result["correct_count"], 5)
        self.assertTrue(result["single_assessment_not_deterministic"])
        states = self.repository.list_skill_states("student_programming")
        self.assertEqual(len(states), 5)
        self.assertTrue(all(item["change"] <= 0.12 for item in states))

    def test_code_review_is_static_and_h5_requires_review_stage(self) -> None:
        self.configure()
        result = self.service.review_code(
            "student_programming",
            ProgrammingCodeReviewInput(
                code="for value in [5, 9, 3]:\n    max_value = value\nprint(max_value)",
                problem_statement="找出列表中的最大值并输出",
                expected_behavior="输出 9",
                observed_problem="输出了最后一个元素",
                hint_level=5,
            ),
        )
        self.assertEqual(result["execution"]["status"], "not_executed")
        self.assertEqual(result["next_hint"]["hint_level"], 4)
        self.assertTrue(result["next_hint"]["answer_leakage_blocked"])
        self.assertTrue(any(item["category"] == "loop_state" for item in result["findings"]))

    def test_project_tasks_are_atomic_and_hint_progresses_one_level(self) -> None:
        self.configure()
        project = self.service.recommend_project(
            "student_programming",
            ProgrammingProjectRecommendationInput(
                interest="学习工具", available_weeks=4, use_for_portfolio=True
            ),
        )
        tasks = [task for milestone in project["milestones"] for task in milestone["tasks"]]
        self.assertTrue(tasks)
        self.assertTrue(all(item["estimated_minutes"] <= 40 for item in tasks))
        hint = self.service.next_project_hint(
            "student_programming",
            project["project_instance_id"],
            ProgrammingProjectHintInput(
                task_id=tasks[0]["task_id"],
                observed_problem="不知道先做什么",
                previous_hint_levels=[0],
                max_allowed_level=3,
            ),
        )
        self.assertEqual(hint["hint_level"], 1)
        self.assertFalse(hint["full_reference_available"])

    def test_interview_scores_dimensions_without_fabricating_experience(self) -> None:
        self.configure()
        session = self.service.create_interview(
            "student_programming", ProgrammingInterviewCreateInput()
        )
        score = self.service.score_interview_answer(
            "student_programming",
            session["session_id"],
            ProgrammingInterviewAnswerInput(
                question_id=session["questions"][0]["question_id"],
                answer_text=(
                    "我做了一个学习时间记录小程序。首先明确输入字段，然后用三个"
                    "样例测试结果；目前不足是没有处理空数据，下次会补充边界测试。"
                ),
            ),
        )
        self.assertEqual(len(score["dimension_scores"]), 7)
        self.assertIn("不会代为编造", score["authenticity_notice"])

    async def test_agent_is_registered_role_and_returns_dashboard(self) -> None:
        self.configure()
        agent = ProgrammingLearningAgent(self.service)
        response = await agent.ainvoke(
            AgentRequest(
                student_id="student_programming",
                actor=Operator(type=ActorType.STUDENT, id="student_programming"),
                intent="get_programming_dashboard",
                context={"student_profile": AUTH_PROFILE},
            )
        )
        self.assertEqual(agent.metadata.role, AgentRole.PROGRAMMING_LEARNING)
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        self.assertEqual(response.agent_role, AgentRole.PROGRAMMING_LEARNING)
        self.assertEqual(len(response.evidence), 2)

    def test_mysql_schema_contains_agent_6_private_tables(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        for table in (
            "programming_learner_profiles",
            "programming_learning_records",
            "programming_learning_events",
            "programming_skill_states",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)


if __name__ == "__main__":
    unittest.main()
