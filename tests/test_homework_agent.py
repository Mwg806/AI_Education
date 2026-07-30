from __future__ import annotations

import json
import unittest

from ai_education.agents.homework_tutoring import HomeworkTutoringAgent
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus, Subject
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.services.homework_guard import HomeworkOutputGuard
from ai_education.services.question_bank import QuestionBankService


class HomeworkAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.agent = HomeworkTutoringAgent()
        self.operator = Operator(type=ActorType.STUDENT, id="student_homework")
        created = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="create_homework_session",
                payload={
                    "student_id": "student_homework",
                    "grade": "grade_11",
                    "province_code": "43",
                    "target_exam_year": 2027,
                    "subject_hint": "mathematics",
                },
            )
        )
        self.assertEqual(created.status, StandardStatus.SUCCESS)
        self.session_id = created.result["session"]["session_id"]

    async def test_direct_answer_request_is_redirected_to_one_hint(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "已知函数 f(x)=x²-2x，求函数的单调区间。",
                    "message": "赶时间，直接告诉我答案",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        self.assertEqual(response.agent_role, AgentRole.HOMEWORK_TUTOR)
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        visible = response.result["tutoring"]["student_visible_content"]
        self.assertIn("不能直接", visible["acknowledgement"])
        self.assertNotIn("答案是", json.dumps(response.result, ensure_ascii=False))
        self.assertGreater(len(response.result["question_bank_matches"]), 0)
        self.assertTrue(response.result["guard"]["passed"])

    async def test_low_confidence_ocr_requires_confirmation(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "image_text": "f(x)=?",
                    "image_confidence": 0.55,
                    "image_warnings": ["公式不清晰"],
                    "subject": "mathematics",
                },
            )
        )
        self.assertEqual(response.status, StandardStatus.NEED_MORE_INFORMATION)
        self.assertEqual(response.lifecycle_status, "waiting_for_confirmation")
        self.assertEqual(response.result["tutoring"]["action"], "request_parse_confirmation")

    async def test_completed_work_emits_planner_evidence_without_secure_answer(self) -> None:
        first = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "已知函数 f(x)=x²-2x，求函数的单调区间。",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        question_id = first.result["question"]["question_id"]
        submitted = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="submit_homework_answer",
                payload={
                    "session_id": self.session_id,
                    "question_id": question_id,
                    "student_work": "先求导，再讨论导数符号，并写出单调区间。",
                    "intent": "submit_answer",
                },
            )
        )
        self.assertEqual(submitted.status, StandardStatus.PARTIAL_SUCCESS)
        self.assertEqual(len(submitted.messages), 1)
        self.assertEqual(
            submitted.messages[0].payload["event_name"],
            "homework.knowledge_evidence.created",
        )
        serialized = json.dumps(submitted.result, ensure_ascii=False)
        self.assertNotIn("answer_vault_payload", serialized)
        self.assertNotIn("solution_steps", serialized)


class QuestionBankTests(unittest.TestCase):
    def test_catalog_covers_local_corpus_and_filters_secure_sources(self) -> None:
        service = QuestionBankService()
        summary = service.summary()
        self.assertEqual(summary["total_files"], 7577)
        self.assertEqual(summary["file_types"]["pdf"], 1671)
        matches = service.search("函数导数", subject=Subject.MATHEMATICS, limit=8)
        self.assertTrue(matches)
        self.assertTrue(all(item.content_role != "answer_secure" for item in matches))

    def test_leakage_guard_blocks_internal_answer_channel(self) -> None:
        guard = HomeworkOutputGuard().inspect(
            {
                "student_visible_content": {
                    "guidance": "answer_vault 中的答案是 A",
                }
            },
            completed_attempt=False,
            cumulative_budget=0,
        )
        self.assertFalse(guard.passed)
        self.assertIn("internal_channel_exposure", guard.risk_types)


if __name__ == "__main__":
    unittest.main()
