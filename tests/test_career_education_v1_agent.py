from __future__ import annotations

import unittest

from ai_education.agents.career_education_v1 import CareerEducationV1Agent
from ai_education.career_education_repository import CareerEducationRepository
from ai_education.domain.career_education import (
    CareerChatInput,
    CareerCodingNextInput,
    CareerCodingSubmissionInput,
    CareerEducationOnboardingInput,
    CareerProjectAnswerInput,
    CareerProjectChatInput,
    CareerProjectStartInput,
    GaokaoProgrammingNextInput,
    GaokaoProgrammingSubmissionInput,
)
from ai_education.domain.enums import ActorType, StandardStatus
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.llm.career_education import GeneratedCareerReply
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.services.career_education_v1 import CareerEducationV1Service
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService

AUTH_PROFILE = {
    "role": "student",
    "studentId": "career_v1_student",
    "studentName": "职业教育验收同学",
}


class CareerEducationV1Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = CareerEducationRepository()
        self.service = CareerEducationV1Service(
            self.repository,
            ProgrammingKnowledgeService(),
        )

    def onboard(self) -> dict:
        return self.service.onboarding(
            "career_v1_student",
            CareerEducationOnboardingInput(
                identity="undergraduate",
                education_stage="undergraduate",
                programming_level="basic",
                known_languages=["Python"],
                weekly_hours=10,
                learning_goal="internship",
                target_period_weeks=16,
            ),
            AUTH_PROFILE,
        )

    @staticmethod
    def project_answer() -> CareerProjectAnswerInput:
        return CareerProjectAnswerInput(
            development_plan=(
                "先梳理用户注册登录、待办 CRUD、分页和统一异常需求，再按模块开发，"
                "使用 pytest 覆盖正常、边界和失败路径，最后按照验收清单逐项验证。"
            ),
            technology_selection=(
                "选择 FastAPI 提供 REST API，因为类型校验清晰；MySQL 保存关系数据，"
                "pytest 负责自动测试，密码使用安全哈希。"
            ),
            architecture_design=(
                "采用路由、服务、仓储分层，认证依赖提供当前用户上下文；服务层校验"
                "资源归属和权限，异常统一映射为 HTTP 状态码。"
            ),
            database_design=(
                "users 表保存用户，todos 表通过 user_id 外键关联；建立 user_id、status、"
                "deadline 联合索引，写操作使用事务并保留 created_at。"
            ),
            api_design=(
                "提供 POST /todos、GET /todos 分页查询、PATCH /todos/{id} 和 DELETE 接口；"
                "不存在返回 404，参数错误返回 422，未认证返回 401。"
            ),
            problem_solutions={
                "P001-01": "从认证上下文读取用户并做资源归属校验，增加用户 A 越权测试。",
                "P001-02": "增加 user_id 与 status 联合索引，分页并检查执行计划。",
                "P001-03": "仓储查询为空时抛出异常并映射 404，覆盖失败路径测试。",
            },
        )

    def test_schema_and_catalog_are_complete(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        self.assertIn("career_job_positions", schema)
        self.assertIn("career_project_templates", schema)
        self.assertIn("career_coding_questions", schema)
        self.assertEqual(len(self.repository.list_jobs()), 1)
        self.assertEqual(len(self.repository.list_projects("JOB_PY_BACKEND")), 3)
        questions = self.repository.list_questions("JOB_PY_BACKEND")
        self.assertEqual(len(questions), 9)
        self.assertEqual(
            {level: sum(item["difficulty"] == level for item in questions) for level in (1, 2, 3)},
            {1: 3, 2: 3, 3: 3},
        )

    def test_high_school_profile_and_recommended_difficulty(self) -> None:
        for programming_level, expected_difficulty in (
            ("beginner", 1),
            ("basic", 2),
            ("project", 3),
        ):
            profile = self.service.onboarding(
                "career_v1_student",
                CareerEducationOnboardingInput(
                    identity="high_school_student",
                    education_stage="high_school",
                    programming_level=programming_level,
                    known_languages=["Python"],
                    weekly_hours=8,
                    learning_goal="gaokao",
                    target_period_weeks=12,
                ),
                AUTH_PROFILE,
            )
            self.assertEqual(profile["identity"], "high_school_student")
            session = self.service.next_coding_question(
                "career_v1_student",
                CareerCodingNextInput(selection_mode="recommended"),
            )
            self.assertEqual(session["question"]["difficulty"], expected_difficulty)
            self.assertEqual(session["selection"]["recommended_difficulty"], expected_difficulty)
            random_session = self.service.next_coding_question(
                "career_v1_student",
                CareerCodingNextInput(selection_mode="random"),
            )
            self.assertEqual(random_session["question"]["difficulty"], expected_difficulty)

    async def test_gaokao_programming_uses_real_bank_and_never_reveals_answer(self) -> None:
        self.onboard()
        first = self.service.next_gaokao_programming_question(
            "career_v1_student", GaokaoProgrammingNextInput()
        )
        question = first["question"]
        self.assertEqual(question["authenticity"], "高考真题")
        self.assertIn("浙江", question["source"]["source_title"])
        self.assertNotIn("_correct_option", question)
        self.assertNotIn("_standard_answer", question)
        self.assertGreaterEqual(first["bank"]["candidate_count"], 20)

        response = await self.service.submit_gaokao_programming_answer(
            "career_v1_student",
            first["session_id"],
            GaokaoProgrammingSubmissionInput(answer="我先跟踪循环变量和每一步状态变化"),
        )
        self.assertFalse(response["answer_revealed"])
        self.assertEqual(response["practice_redirect"]["mode"], "CODING")
        self.assertTrue(response["hints"])
        self.assertNotIn("标准答案", response["diagnosis"])

        private_question = next(
            item
            for item in self.service.gaokao_programming_questions
            if item["question_id"] == question["question_id"]
        )
        leaked = self.service._sanitize_gaokao_feedback(
            private_question,
            {
                "score": 0,
                "diagnosis": f"正确答案是 {private_question['_correct_option']}",
                "strengths": ["已作答"],
                "issues": ["正确选项已经给出"],
                "hints": [f"应该选 {private_question['_correct_option']}"],
                "next_step": "继续练习",
            },
        )
        serialized = str(leaked)
        self.assertNotIn("正确答案", serialized)
        self.assertNotIn("正确选项", serialized)
        self.assertNotIn("应该选", serialized)

    async def test_dashboard_and_career_mode_use_stable_context(self) -> None:
        initial = self.service.dashboard("career_v1_student", AUTH_PROFILE)
        self.assertFalse(initial["configured"])
        profile = self.onboard()
        self.assertEqual(profile["target_job_id"], "JOB_PY_BACKEND")
        result = await self.service.career_chat(
            "career_v1_student",
            CareerChatInput(message="FastAPI 应该学到什么程度？"),
        )
        self.assertEqual(result["mode"], "CAREER")
        self.assertEqual(result["context_used"]["target_job_id"], "JOB_PY_BACKEND")
        self.assertEqual(len(result["task_breakdown"]), 3)
        self.assertTrue(all(item["acceptance"] for item in result["task_breakdown"]))

    async def test_career_mentor_uses_llm_and_previous_turns(self) -> None:
        class FakeMentor:
            available = True

            def __init__(self) -> None:
                self.contexts: list[dict] = []

            async def generate(self, context: dict) -> GeneratedCareerReply:
                self.contexts.append(context)
                return GeneratedCareerReply(
                    analysis="你是在确认 FastAPI 学习深度。",
                    answer="可以正常交流：先掌握路由、校验和异常处理，再用项目验证。",
                    follow_up_question="你现在写过完整接口吗？",
                )

        self.onboard()
        mentor = FakeMentor()
        self.service.career_mentor = mentor
        first = await self.service.career_chat(
            "career_v1_student", CareerChatInput(message="FastAPI 要学到什么程度？")
        )
        second = await self.service.career_chat(
            "career_v1_student", CareerChatInput(message="那这个要怎么练？")
        )
        self.assertEqual(first["generation_mode"], "llm")
        self.assertIn("正常交流", first["answer"])
        self.assertEqual(second["context_used"]["conversation_turns"], 1)
        self.assertEqual(
            mentor.contexts[1]["conversation_history"][0]["student"],
            "FastAPI 要学到什么程度？",
        )

    def test_project_documents_and_evidence_based_report(self) -> None:
        self.onboard()
        session = self.service.start_project(
            "career_v1_student",
            CareerProjectStartInput(project_id="P001_TODO_API"),
        )
        self.assertIn("# 项目实训任务", session["requirement_doc"])
        self.assertIn("# 学员回答区域", session["requirement_doc"])
        self.assertNotIn("reference_points", str(session["project"]))
        self.service.submit_project_answer(
            "career_v1_student", session["session_id"], self.project_answer()
        )
        evaluation = self.service.evaluate_project("career_v1_student", session["session_id"])
        self.assertEqual(len(evaluation["dimensions"]), 8)
        self.assertTrue(all(item["evidence"] for item in evaluation["dimensions"]))
        report, filename = self.service.project_document(
            "career_v1_student", session["session_id"], "report"
        )
        self.assertEqual(filename, "report.md")
        self.assertIn("评分依据", report)
        self.assertIn("逐项修改建议", report)

    async def test_project_chat_reads_selected_project_and_keeps_context(self) -> None:
        self.onboard()
        session = self.service.start_project(
            "career_v1_student",
            CareerProjectStartInput(project_id="P001_TODO_API"),
        )
        first = await self.service.project_chat(
            "career_v1_student",
            CareerProjectChatInput(
                session_id=session["session_id"],
                message="请先告诉我这个项目该从哪里开始？",
            ),
        )
        second = await self.service.project_chat(
            "career_v1_student",
            CareerProjectChatInput(
                session_id=session["session_id"],
                message="那数据库部分呢？",
            ),
        )
        self.assertTrue(first["context_used"]["project_loaded"])
        self.assertTrue(first["guiding_questions"])
        self.assertEqual(second["context_used"]["conversation_turns"], 1)

    def test_coding_hides_answer_then_judges_and_records_history(self) -> None:
        self.onboard()
        session = self.service.next_coding_question(
            "career_v1_student", CareerCodingNextInput(category="python")
        )
        self.assertNotIn("hidden_tests", session["question"])
        self.assertNotIn("reference_solution", session["question"])
        failed = self.service.submit_coding(
            "career_v1_student",
            session["session_id"],
            CareerCodingSubmissionInput(code=session["question"]["starter_code"], action="submit"),
        )
        self.assertEqual(failed["status"], "attempted")
        self.assertEqual(failed["feedback"]["current_hint_level"], 1)
        passed = self.service.submit_coding(
            "career_v1_student",
            session["session_id"],
            CareerCodingSubmissionInput(
                code=(
                    "def count_status(items):\n"
                    "    result = {}\n"
                    "    for item in items:\n"
                    "        result[item] = result.get(item, 0) + 1\n"
                    "    return result"
                ),
                action="submit",
            ),
        )
        self.assertEqual(passed["judge_result"]["status"], "ACCEPTED")
        self.assertEqual(len(self.service.coding_history("career_v1_student")), 2)

    def test_coding_next_excludes_current_question_for_selected_language(self) -> None:
        self.onboard()
        first = self.service.next_coding_question(
            "career_v1_student", CareerCodingNextInput(language="python")
        )
        second = self.service.next_coding_question(
            "career_v1_student",
            CareerCodingNextInput(
                language="python",
                exclude_question_id=first["question"]["question_id"],
            ),
        )
        self.assertNotEqual(
            first["question"]["question_id"],
            second["question"]["question_id"],
        )
        self.assertEqual(second["question"]["language"].lower(), "python")

    async def test_langgraph_routes_complete_v1_dashboard(self) -> None:
        self.onboard()
        agent = CareerEducationV1Agent(self.service)
        response = await agent.ainvoke(
            AgentRequest(
                student_id="career_v1_student",
                actor=Operator(type=ActorType.STUDENT, id="career_v1_student"),
                intent="v1_dashboard",
                context={"student_profile": AUTH_PROFILE},
            )
        )
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        self.assertEqual(response.result["spec_version"], "1.0")
        self.assertEqual(response.result["current_mode"], "CAREER")

        question_response = await agent.ainvoke(
            AgentRequest(
                student_id="career_v1_student",
                actor=Operator(type=ActorType.STUDENT, id="career_v1_student"),
                intent="v1_next_question",
                payload={"category": "python", "difficulty": 1},
                context={"student_profile": AUTH_PROFILE},
            )
        )
        self.assertEqual(question_response.status, StandardStatus.SUCCESS)
        coding_session = question_response.result
        submit_response = await agent.ainvoke(
            AgentRequest(
                student_id="career_v1_student",
                actor=Operator(type=ActorType.STUDENT, id="career_v1_student"),
                intent="v1_submit_code",
                payload={
                    "session_id": coding_session["session_id"],
                    "code": coding_session["question"]["starter_code"],
                    "action": "submit",
                },
                context={"student_profile": AUTH_PROFILE},
            )
        )
        self.assertEqual(submit_response.status, StandardStatus.SUCCESS)
        self.assertEqual(submit_response.result["status"], "attempted")


if __name__ == "__main__":
    unittest.main()
