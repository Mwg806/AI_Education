from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from ai_education.agents.teacher_preparation import TeacherPreparationAgent
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus, Subject
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.llm.teacher_preparation import StructuredTeacherPreparationGenerator
from ai_education.services.teacher_preparation import TeacherPreparationService
from ai_education.services.teacher_preparation_knowledge import TeachingKnowledgeBase
from ai_education.teacher_preparation_repository import TeacherPreparationRepository


def request(intent: str, payload: dict, actor: ActorType = ActorType.TEACHER) -> AgentRequest:
    return AgentRequest(
        student_id="teacher:teacher_04",
        actor=Operator(type=actor, id="teacher_04"),
        intent=intent,
        payload=payload,
    )


class TeachingKnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = TeachingKnowledgeBase()

    def test_nine_subject_catalog_and_checksums_are_complete(self) -> None:
        catalog = self.knowledge.catalog()
        integrity = self.knowledge.verify_integrity()
        self.assertEqual(catalog["resource_count"], 27)
        self.assertEqual(catalog["subject_count"], 9)
        self.assertTrue(all(item["resource_count"] == 3 for item in catalog["subjects"]))
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["verified_count"], 27)

    def test_search_returns_grounded_chemistry_references(self) -> None:
        resources = self.knowledge.search(
            "氧化还原反应 证据推理",
            subject=Subject.CHEMISTRY,
            limit=3,
        )
        self.assertEqual(len(resources), 3)
        self.assertTrue(all(item.subject == Subject.CHEMISTRY for item in resources))
        self.assertTrue(all(item.checksum_verified for item in resources))
        self.assertTrue(all(item.source_organization for item in resources))
        self.assertTrue(any(item.excerpt for item in resources))


class TeacherPreparationAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = TeacherPreparationRepository()
        self.service = TeacherPreparationService(
            self.repository,
            TeachingKnowledgeBase(),
            StructuredTeacherPreparationGenerator(None),
        )
        self.agent = TeacherPreparationAgent(self.service)
        members = [
            {
                "student_id": "secret-account",
                "student_name": "张同学",
                "latest_diagnosis": {
                    "state_version": 8,
                    "diagnosis_status": "stable",
                    "knowledge_states": [
                        {
                            "dimension_id": "redox",
                            "dimension_label": "氧化还原电子转移",
                            "mastery_level": "needs_support",
                        }
                    ],
                    "stable_error_patterns": [{"description": "氧化剂与还原剂判断混淆"}],
                },
            },
            {
                "student_id": "another-secret",
                "student_name": "李同学",
                "latest_diagnosis": None,
            },
        ]
        diagnosis = self.service.aggregate_class_diagnosis(members)
        self.payload = {
            "classroom_id": 7,
            "subject": "chemistry",
            "lesson_type": "new_lesson",
            "topic": "氧化还原反应",
            "lesson_request": "用证据推理组织概念形成与课堂检测",
            "duration_minutes": 45,
            "teaching_stage": "日常教学",
            "textbook_version": "人教版选择性必修",
            "exam_year": 2027,
            "available_equipment": ["投影仪"],
            "classroom": {
                "id": 7,
                "grade": "grade_11",
                "subject": "chemistry",
                "student_count": 2,
            },
            "diagnosis_summary": diagnosis,
        }

    async def test_create_is_private_grounded_feasible_and_aligned(self) -> None:
        response = await self.agent.ainvoke(request("create_lesson_plan", self.payload))
        self.assertEqual(response.agent_role, AgentRole.TEACHER_PREPARATION)
        self.assertEqual(response.status, StandardStatus.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(response.lifecycle_status, "teacher_review")
        plan = response.result["lesson_plan"]
        self.assertEqual(plan["generation_mode"], "reference_template")
        self.assertEqual(len(plan["resources"]), 3)
        self.assertTrue(all(item["checksum_verified"] for item in plan["resources"]))
        self.assertTrue(all(row["status"] == "pass" for row in plan["alignment_matrix"]))
        self.assertLessEqual(
            sum(item["duration_minutes"] for item in plan["activities"]),
            plan["context"]["duration_minutes"] - plan["context"]["buffer_minutes"],
        )
        diagnosis_json = json.dumps(plan["context"]["diagnosis_summary"], ensure_ascii=False)
        self.assertNotIn("张同学", diagnosis_json)
        self.assertNotIn("secret-account", diagnosis_json)
        self.assertEqual(
            plan["context"]["diagnosis_summary"]["privacy_mode"],
            "anonymous_aggregate_only",
        )

    async def test_slow_model_falls_back_before_request_timeout(self) -> None:
        class SlowGenerator:
            @property
            def available(self) -> bool:
                return True

            async def generate(self, **_: object) -> None:
                await asyncio.sleep(1)

        service = TeacherPreparationService(
            TeacherPreparationRepository(),
            TeachingKnowledgeBase(),
            SlowGenerator(),
        )
        agent = TeacherPreparationAgent(service)
        with patch(
            "ai_education.services.teacher_preparation.TEACHER_GENERATION_TIMEOUT_SECONDS",
            0.01,
        ):
            response = await agent.ainvoke(request("create_lesson_plan", self.payload))

        plan = response.result["lesson_plan"]
        self.assertEqual(response.status, StandardStatus.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(plan["generation_mode"], "reference_template")

    async def test_review_plan_can_restore_any_earlier_version(self) -> None:
        created = await self.agent.ainvoke(request("create_lesson_plan", self.payload))
        first = created.result["lesson_plan"]
        revised = await self.agent.ainvoke(
            request(
                "revise_lesson_plan",
                {
                    "lesson_plan_id": first["lesson_plan_id"],
                    "expected_version": 1,
                    "component": "activities",
                    "revision_request": "将课堂活动改为小组实验并增加证据记录",
                    "locked_component_ids": [],
                },
            )
        )
        second = revised.result["lesson_plan"]
        restored = await self.agent.ainvoke(
            request(
                "rollback_lesson_plan",
                {
                    "lesson_plan_id": first["lesson_plan_id"],
                    "expected_version": 2,
                    "target_version": 1,
                },
            )
        )
        third = restored.result["lesson_plan"]
        self.assertEqual(third["version"], 3)
        self.assertEqual(third["parent_version"], 2)
        self.assertEqual(third["status"], "teacher_review")
        self.assertEqual(third["activities"], first["activities"])
        self.assertEqual(third["title"], first["title"])
        self.assertEqual(second["version"], 2)
        self.assertIn("回退至第 1 版", third["change_summary"][0])

        history = await self.agent.ainvoke(
            request(
                "list_lesson_plan_versions",
                {"lesson_plan_id": first["lesson_plan_id"]},
            )
        )
        self.assertEqual(
            [item["version"] for item in history.result["versions"]],
            [3, 2, 1],
        )

    async def test_lock_revision_approval_publication_and_feedback_are_versioned(
        self,
    ) -> None:
        created = await self.agent.ainvoke(request("create_lesson_plan", self.payload))
        first = created.result["lesson_plan"]
        locked_text = first["objectives"][0]["description"]
        lesson_plan_id = first["lesson_plan_id"]

        revised = await self.agent.ainvoke(
            request(
                "revise_lesson_plan",
                {
                    "lesson_plan_id": lesson_plan_id,
                    "expected_version": 1,
                    "component": "full",
                    "revision_request": "增加实验现象解释并保留第一个教学目标",
                    "locked_component_ids": ["obj_1"],
                },
            )
        )
        second = revised.result["lesson_plan"]
        self.assertEqual(second["version"], 2)
        self.assertEqual(second["objectives"][0]["description"], locked_text)
        self.assertIn("obj_1", second["locked_component_ids"])

        approved = await self.agent.ainvoke(
            request(
                "approve_lesson_plan",
                {"lesson_plan_id": lesson_plan_id, "expected_version": 2},
            )
        )
        self.assertEqual(approved.result["lesson_plan"]["version"], 3)
        self.assertEqual(approved.result["lesson_plan"]["status"], "approved")
        self.assertFalse(approved.messages)

        published = await self.agent.ainvoke(
            request(
                "publish_lesson_plan",
                {"lesson_plan_id": lesson_plan_id, "expected_version": 3},
            )
        )
        self.assertEqual(published.result["lesson_plan"]["version"], 4)
        self.assertEqual(published.result["lesson_plan"]["status"], "published")
        self.assertEqual(len(published.messages), 2)
        self.assertEqual(
            {item.recipient for item in published.messages},
            {AgentRole.LEARNING_DIAGNOSIS, AgentRole.HOMEWORK_TUTOR},
        )

        feedback = await self.agent.ainvoke(
            request(
                "record_post_lesson_feedback",
                {
                    "lesson_plan_id": lesson_plan_id,
                    "lesson_version": 4,
                    "actual_duration_minutes": 46,
                    "completed_activity_ids": [
                        item["activity_id"]
                        for item in published.result["lesson_plan"]["activities"]
                    ],
                    "class_check_accuracy": 0.76,
                    "teacher_rating": 4,
                    "teacher_notes": "概念辨析有效，下次增加学生互评时间。",
                },
            )
        )
        self.assertEqual(feedback.result["lesson_plan"]["version"], 5)
        self.assertEqual(feedback.result["lesson_plan"]["status"], "feedback_recorded")
        self.assertEqual(feedback.result["feedback"]["lesson_version"], 4)

    async def test_lab_plan_without_equipment_input_keeps_teacher_confirmation(self) -> None:
        payload = {**self.payload, "lesson_type": "lab"}
        payload.pop("available_equipment", None)
        response = await self.agent.ainvoke(request("create_lesson_plan", payload))
        plan = response.result["lesson_plan"]
        self.assertEqual(plan["quality_report"]["feasibility_status"], "pass")
        self.assertTrue(
            any(
                item["code"] == "LAB_SETUP_TEACHER_CONFIRMATION"
                for item in plan["quality_report"]["issues"]
            )
        )

    async def test_student_actor_is_rejected(self) -> None:
        response = await self.agent.ainvoke(
            request("create_lesson_plan", self.payload, ActorType.STUDENT)
        )
        self.assertEqual(response.status, StandardStatus.NEED_MORE_INFORMATION)
        self.assertEqual(response.errors[0].code, "TEACHER_PREPARATION_INPUT_INVALID")
