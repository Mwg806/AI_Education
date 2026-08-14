from __future__ import annotations

import json
import unittest

from ai_education.agents.homework_tutoring import HomeworkTutoringAgent
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus, Subject
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.services.homework_guard import HomeworkOutputGuard
from ai_education.services.question_bank import QuestionBankService
from tests.fixtures import FakeStructuredHomeworkTutor


class HomeworkAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.agent = HomeworkTutoringAgent()
        self.fake_tutor = FakeStructuredHomeworkTutor()
        self.agent.structured_tutor = self.fake_tutor
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
        self.assertEqual(
            response.result["tutoring"]["pedagogical_metadata"]["generation_mode"],
            "llm",
        )
        self.assertGreater(len(self.fake_tutor.calls), 0)

    async def test_shared_profile_is_passed_to_personalized_tutoring(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "已知函数 f(x)=x²-2x，求函数的单调区间。",
                    "message": "请根据我现在的基础提示下一步。",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
                context={
                    "unified_student_profile": {
                        "weak_points": ["mathematics.derivative.application"],
                        "strengths": ["mathematics.function.foundation"],
                        "subject_abilities": {
                            "mathematics": {
                                "mathematics.derivative.application": {
                                    "mastery": 0.38,
                                    "confidence": 0.72,
                                    "trend": "declining",
                                    "evidence_count": 4,
                                }
                            }
                        },
                    },
                    "recent_learning_events": [
                        {
                            "subject": "mathematics",
                            "event_type": "question_wrong",
                            "knowledge_point": "derivative.application",
                            "score": 0.2,
                            "confidence": 0.8,
                            "occurred_at": "2026-08-14T08:00:00Z",
                        }
                    ],
                },
            )
        )
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        shared = json.loads(self.fake_tutor.calls[-1]["payload"]["shared_student_context"])
        self.assertIn("mathematics.derivative.application", shared["weak_points"])
        self.assertEqual(
            shared["subject_abilities"]["mathematics.derivative.application"]["evidence_count"],
            4,
        )
        self.assertEqual(len(shared["recent_subject_events"]), 1)

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

    async def test_feedback_reads_the_actual_question_and_current_step(self) -> None:
        first = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "已知函数 f(x)=x²-2x，求函数的单调区间。",
                    "message": "我应该从哪里开始？",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        visible = first.result["tutoring"]["student_visible_content"]
        self.assertIn("导数与函数单调性", visible["guidance"])
        self.assertIn("临界点", visible["guidance"])

        checked = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "student_work": "我求得 f'(x)=2x-2，下一步令导数等于零。",
                    "message": "帮我检查这一步是否正确",
                    "intent": "check_step",
                    "subject": "mathematics",
                },
            )
        )
        checked_visible = checked.result["tutoring"]["student_visible_content"]
        self.assertIn("f'(x)=2x-2", checked_visible["acknowledgement"])
        self.assertIn("导数与函数单调性", checked_visible["guidance"])
        self.assertGreater(len(checked.result["question_bank_matches"]), 0)

    async def test_basic_chat_is_answered_without_creating_a_fake_question(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "你好",
                    "message": "你好",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        self.assertEqual(response.result["tutoring"]["action"], "general_response")
        self.assertIsNone(response.result["question"])
        visible = response.result["tutoring"]["student_visible_content"]
        self.assertIn("你好", visible["acknowledgement"])
        self.assertNotIn("先不用急着计算", json.dumps(visible, ensure_ascii=False))

    async def test_concept_question_uses_curriculum_knowledge(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "什么是导数，为什么它能判断函数单调性？",
                    "message": "什么是导数，为什么它能判断函数单调性？",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        self.assertEqual(response.result["tutoring"]["action"], "knowledge_explanation")
        visible = response.result["tutoring"]["student_visible_content"]
        self.assertIn("导数", visible["guidance"])
        self.assertIn("变化率", visible["guidance"])
        self.assertGreater(len(response.result["knowledge_sources"]), 0)
        self.assertIsNone(response.result["question"])

    async def test_high_confidence_image_gets_subject_specific_guidance(self) -> None:
        response = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "image_text": "质量为 m 的物体在水平面上受恒力 F 作用，求加速度。",
                    "image_data_urls": ["data:image/png;base64,dGVzdA=="],
                    "image_confidence": 0.96,
                    "message": "请分析图片中的题目，我应该先做什么？",
                    "intent": "request_hint",
                    "subject": "physics",
                },
            )
        )
        visible = response.result["tutoring"]["student_visible_content"]
        self.assertEqual(response.result["tutoring"]["action"], "release_hint")
        self.assertIn("原图", visible["acknowledgement"])
        self.assertIn("力与运动", visible["guidance"])
        self.assertIn("研究对象", visible["question_to_student"])
        self.assertGreater(len(response.result["knowledge_sources"]), 0)
        self.assertNotIn("答案是", json.dumps(response.result, ensure_ascii=False))
        self.assertEqual(self.fake_tutor.calls[-1]["image_count"], 1)
        self.assertTrue(response.result["tutoring"]["pedagogical_metadata"]["multimodal"])

    async def test_different_text_questions_receive_different_guidance(self) -> None:
        derivative = await self.agent.ainvoke(
            AgentRequest(
                student_id="student_homework",
                actor=self.operator,
                intent="homework_turn",
                payload={
                    "session_id": self.session_id,
                    "question_text": "已知函数 f(x)=x²-2x，求函数的单调区间。",
                    "message": "这道题从哪里开始？",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        other_agent = HomeworkTutoringAgent()
        other_agent.structured_tutor = FakeStructuredHomeworkTutor()
        created = await other_agent.ainvoke(
            AgentRequest(
                student_id="student_sequence",
                actor=Operator(type=ActorType.STUDENT, id="student_sequence"),
                intent="create_homework_session",
                payload={
                    "student_id": "student_sequence",
                    "grade": "grade_11",
                    "province_code": "43",
                    "target_exam_year": 2027,
                    "subject_hint": "mathematics",
                },
            )
        )
        sequence = await other_agent.ainvoke(
            AgentRequest(
                student_id="student_sequence",
                actor=Operator(type=ActorType.STUDENT, id="student_sequence"),
                intent="homework_turn",
                payload={
                    "session_id": created.result["session"]["session_id"],
                    "question_text": "已知等差数列前 n 项和为 Sn，求通项公式。",
                    "message": "我应该先找什么关系？",
                    "intent": "request_hint",
                    "subject": "mathematics",
                },
            )
        )
        derivative_guidance = derivative.result["tutoring"]["student_visible_content"]["guidance"]
        sequence_guidance = sequence.result["tutoring"]["student_visible_content"]["guidance"]
        self.assertIn("导数", derivative_guidance)
        self.assertIn("数列", sequence_guidance)
        self.assertNotEqual(derivative_guidance, sequence_guidance)

    async def test_missing_model_returns_explicit_error_instead_of_template(self) -> None:
        from ai_education.llm.homework_tutor import StructuredHomeworkTutor

        unavailable = HomeworkTutoringAgent()
        unavailable.structured_tutor = StructuredHomeworkTutor(None)
        created = await unavailable.ainvoke(
            AgentRequest(
                student_id="student_no_model",
                actor=Operator(type=ActorType.STUDENT, id="student_no_model"),
                intent="create_homework_session",
                payload={
                    "student_id": "student_no_model",
                    "grade": "grade_11",
                    "province_code": "43",
                    "target_exam_year": 2027,
                    "subject_hint": "mathematics",
                },
            )
        )
        response = await unavailable.ainvoke(
            AgentRequest(
                student_id="student_no_model",
                actor=Operator(type=ActorType.STUDENT, id="student_no_model"),
                intent="homework_turn",
                payload={
                    "session_id": created.result["session"]["session_id"],
                    "question_text": "你好",
                    "message": "你好",
                    "subject": "mathematics",
                },
            )
        )
        self.assertEqual(response.status, StandardStatus.FAILED)
        self.assertEqual(response.errors[0].code, "HOMEWORK_LLM_UNAVAILABLE")
        self.assertNotIn("tutoring", response.result)


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
