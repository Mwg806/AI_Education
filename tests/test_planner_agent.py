from __future__ import annotations

import unittest
from dataclasses import replace

from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.domain.enums import ActorType, StandardStatus
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from tests.fixtures import (
    FakeStructuredPlanNarrator,
    diagnostic_evidence,
    diagnostic_planning_evidence,
    planner_payload,
)


class PlannerAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.agent = PersonalizedLearningPlannerAgent()
        self.agent.plan_narrator = FakeStructuredPlanNarrator()

    def request(self, intent: str, payload: dict, key: str | None = None) -> AgentRequest:
        return AgentRequest(
            student_id="student_10001",
            actor=Operator(type=ActorType.STUDENT, id="student_10001"),
            intent=intent,
            payload=payload,
            idempotency_key=key,
        )

    async def test_initialize_confirm_and_version_plan(self) -> None:
        initialized = await self.agent.ainvoke(
            self.request("initialize_plan", planner_payload(), "initialize-001")
        )
        self.assertEqual(initialized.status, StandardStatus.SUCCESS, initialized.errors)
        plan = initialized.result["plan"]
        self.assertEqual(plan["generation_basis"]["narrative_generation_mode"], "llm")
        self.assertEqual(plan["generation_basis"]["llm_model"], self.agent.settings.llm_model)
        self.assertEqual(plan["generation_basis"]["diagnostic_attempt_count"], "1")
        self.assertEqual(plan["generation_basis"]["diagnostic_question_evidence_count"], "10")
        narrator_attempt = self.agent.plan_narrator.calls[-1][
            "diagnostic_attempts_by_subject"
        ]["mathematics"]
        self.assertEqual(len(narrator_attempt["questions"]), 10)
        self.assertIn("selected_answer", narrator_attempt["questions"][0])
        self.assertIn("correct_answer", narrator_attempt["questions"][0])
        self.assertIn("模型", plan["explanations"]["student"])
        self.assertEqual(len(self.agent.plan_narrator.calls), 1)
        self.assertEqual(plan["status"], "waiting_for_confirmation")
        self.assertTrue(plan["validation"]["valid"])
        self.assertGreater(len(plan["tasks"]), 0)
        task_types = {task["task_type"] for task in plan["tasks"]}
        self.assertTrue({"spaced_review", "timed_training", "stage_assessment"} <= task_types)
        subject_minutes: dict[str, int] = {}
        for task in plan["tasks"]:
            subject_minutes[task["subject"]] = (
                subject_minutes.get(task["subject"], 0) + task["planned_duration_minutes"]
            )
        self.assertTrue(
            all(
                minutes <= plan["subject_time_budgets"][subject]
                for subject, minutes in subject_minutes.items()
            )
        )
        self.assertLessEqual(
            plan["scheduled_minutes"] + plan["buffer_minutes"],
            plan["weekly_capacity_minutes"],
        )

        confirmed = await self.agent.ainvoke(
            self.request(
                "confirm_plan",
                {"plan_id": plan["plan_id"], "expected_version": plan["version"]},
                "confirm-001",
            )
        )
        self.assertEqual(confirmed.status, StandardStatus.SUCCESS, confirmed.errors)
        self.assertEqual(confirmed.result["plan"]["version"], 2)
        self.assertEqual(confirmed.result["plan"]["status"], "active")

        restored = await self.agent.ainvoke(self.request("get_plan", {"scope": "latest"}))
        self.assertEqual(restored.status, StandardStatus.SUCCESS, restored.errors)
        self.assertEqual(restored.result["plan"]["plan_id"], plan["plan_id"])
        self.assertEqual(restored.result["plan"]["version"], 2)
        self.assertEqual(restored.result["student_profile"]["student_id"], "student_10001")
        self.assertTrue(restored.result["knowledge_profile"]["knowledge_states"])
        self.assertGreater(restored.result["time_profile"]["weekly_effective_minutes"], 0)

    async def test_self_assessment_only_creates_unconfirmable_provisional_plan(self) -> None:
        payload = planner_payload()
        payload["knowledge_evidence"] = [
            {
                "knowledge_id": "PEA-E2-C05_foundation",
                "score": 0.9,
                "weight": 0.95,
                "source_type": "student_self_assessment",
                "source_id": "self_foundation",
            },
            {
                "knowledge_id": "PEA-E2-C05_application",
                "score": 0.85,
                "weight": 0.95,
                "source_type": "student_self_assessment",
                "source_id": "self_application",
            },
        ]
        payload["prerequisite_edges"] = []

        initialized = await self.agent.ainvoke(self.request("initialize_plan", payload))

        self.assertEqual(initialized.status, StandardStatus.PARTIAL_SUCCESS)
        plan = initialized.result["plan"]
        self.assertEqual(plan["status"], "provisional")
        self.assertEqual(
            plan["generation_basis"]["evidence_status"],
            "provisional",
        )
        self.assertFalse(
            initialized.result["knowledge_profile"]["assessment_quality"]["evidence_sufficient"]
        )
        confirmation = await self.agent.ainvoke(
            self.request(
                "confirm_plan",
                {"plan_id": plan["plan_id"], "expected_version": plan["version"]},
            )
        )
        self.assertEqual(confirmation.status, StandardStatus.FAILED)

    async def test_idempotent_initialization_returns_same_plan(self) -> None:
        request = self.request("initialize_plan", planner_payload(), "same-key")
        first = await self.agent.ainvoke(request)
        second = await self.agent.ainvoke(request)
        self.assertEqual(first.result["plan"]["plan_id"], second.result["plan"]["plan_id"])

    async def test_missing_evidence_stops_before_plan(self) -> None:
        payload = planner_payload()
        payload.pop("knowledge_evidence")
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))
        self.assertEqual(response.status, StandardStatus.NEED_MORE_INFORMATION)
        self.assertNotIn("plan", response.result)

    async def test_unknown_policy_requires_manual_review(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["province_code"] = "99"
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))
        self.assertEqual(response.status, StandardStatus.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(response.errors[0].code, "POLICY_UNAVAILABLE")

    async def test_multi_chapter_scope_is_preserved_in_plan_generation(self) -> None:
        service = CurriculumCatalogService()
        mathematics = service.subject_catalog("mathematics")
        edition = next(
            item
            for item in mathematics["editions"]
            if sum(len(volume["chapters"]) for volume in item["volumes"]) >= 3
        )
        chapter_ids = [
            chapter["id"] for volume in edition["volumes"] for chapter in volume["chapters"]
        ][:3]
        payload = planner_payload()
        payload["student_profile"]["curriculum_versions"] = {"mathematics": edition["id"]}
        payload["student_profile"]["class_progress"] = {"mathematics": chapter_ids}
        payload["knowledge_evidence"] = diagnostic_evidence(
            [f"{chapter_id}_foundation" for chapter_id in chapter_ids]
        )
        payload["prerequisite_edges"] = []

        response = await self.agent.ainvoke(
            self.request("initialize_plan", payload, "multi-chapter-plan")
        )

        self.assertEqual(response.status, StandardStatus.SUCCESS, response.errors)
        self.assertEqual(
            self.agent.plan_narrator.calls[-1]["student"]["class_progress"]["mathematics"],
            chapter_ids,
        )
        task_knowledge_ids = {
            knowledge_id
            for task in response.result["plan"]["tasks"]
            for knowledge_id in task["knowledge_ids"]
        }
        self.assertTrue(
            all(
                any(knowledge_id.startswith(chapter_id) for knowledge_id in task_knowledge_ids)
                for chapter_id in chapter_ids
            )
        )

    async def test_unregistered_math_chapter_is_rejected(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["class_progress"]["mathematics"] = "invented_chapter"
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))
        self.assertEqual(response.status, StandardStatus.FAILED)
        self.assertEqual(response.errors[0].code, "INPUT_VALIDATION_ERROR")

    async def test_physics_can_be_the_primary_planning_subject(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["curriculum_versions"] = {"physics": "people_education"}
        payload["student_profile"]["class_progress"] = {"physics": "PHY-MECHANICS"}
        payload["goal_text"] = "我物理最近62分，希望高三一模达到80分"
        payload["knowledge_evidence"] = [
            {
                "knowledge_id": "PHY-MECHANICS_foundation",
                "score": 0.58,
                "weight": 0.9,
                "source_type": "student_self_assessment",
                "source_id": "physics_foundation",
            }
        ]
        payload["knowledge_evidence"].extend(
            diagnostic_evidence(["PHY-MECHANICS_foundation", "PHY-MECHANICS_application"])
        )
        payload["prerequisite_edges"] = []
        payload["subject_factors"] = {
            "physics": {"goal_priority": 1, "score_gap": 1, "urgency": 0.8}
        }

        response = await self.agent.ainvoke(self.request("initialize_plan", payload))

        self.assertEqual(response.status, StandardStatus.SUCCESS, response.errors)
        self.assertTrue(response.result["plan"]["tasks"])
        self.assertEqual(
            {task["subject"] for task in response.result["plan"]["tasks"]},
            {"physics"},
        )

    async def test_multi_subject_plan_uses_each_subject_diagnosis_and_budget(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["curriculum_versions"] = {
            "mathematics": "people_education_a",
            "physics": "people_education",
        }
        payload["student_profile"]["class_progress"] = {
            "mathematics": ["PEA-E2-C05"],
            "physics": ["PHY-MECHANICS"],
        }
        payload["goals"] = [
            {
                "subject": "mathematics",
                "current_value": 92,
                "target_value": 120,
                "deadline": "2027-05-20",
                "priority": 1,
                "curriculum_version": "people_education_a",
                "class_progress": ["PEA-E2-C05"],
            },
            {
                "subject": "physics",
                "current_value": 62,
                "target_value": 80,
                "deadline": "2027-05-20",
                "priority": 2,
                "curriculum_version": "people_education",
                "class_progress": ["PHY-MECHANICS"],
            },
        ]
        payload["knowledge_evidence_by_subject"] = {
            "mathematics": diagnostic_evidence(
                ["PEA-E2-C05_foundation", "PEA-E2-C05_application"]
            ),
            "physics": diagnostic_evidence(
                ["PHY-MECHANICS_foundation", "PHY-MECHANICS_application"]
            ),
        }
        payload["diagnostic_attempts_by_subject"] = {
            "mathematics": diagnostic_planning_evidence(
                "mathematics", "函数与导数"
            ),
            "physics": diagnostic_planning_evidence("physics", "运动与力"),
        }
        payload["subject_factors"] = {
            "mathematics": {
                "goal_priority": 1,
                "score_gap": 0.56,
                "expected_score_gain": 1,
                "urgency": 0.8,
                "knowledge_dependency": 1,
            },
            "physics": {
                "goal_priority": 0.75,
                "score_gap": 0.45,
                "expected_score_gain": 1,
                "urgency": 0.7,
                "knowledge_dependency": 1,
            },
        }
        payload["daily_capacity"] = [
            {
                "weekday": day,
                "available_minutes": 120,
                "preferred_period": "evening",
                "energy_coefficient": 0.9,
            }
            for day in range(1, 8)
        ]

        response = await self.agent.ainvoke(
            self.request("initialize_plan", payload, "multi-subject-plan")
        )

        self.assertEqual(response.status, StandardStatus.SUCCESS, response.errors)
        plan = response.result["plan"]
        self.assertEqual(set(plan["subject_time_budgets"]), {"mathematics", "physics"})
        self.assertEqual(
            {item["subject"] for item in plan["subject_goals"]},
            {"mathematics", "physics"},
        )
        self.assertEqual(
            set(response.result["knowledge_profiles_by_subject"]),
            {"mathematics", "physics"},
        )
        for subject in ("mathematics", "physics"):
            subject_tasks = [task for task in plan["tasks"] if task["subject"] == subject]
            self.assertTrue(subject_tasks)
            self.assertTrue(
                {"spaced_review", "timed_training", "stage_assessment"}.issubset(
                    {task["task_type"] for task in subject_tasks}
                )
            )
            self.assertTrue(
                all(
                    state["subject"] == subject
                    for state in response.result["knowledge_profiles_by_subject"][subject][
                        "knowledge_states"
                    ]
                )
            )
        self.assertTrue(plan["validation"]["checks"]["all_goal_subjects_scheduled"])
        self.assertTrue(plan["validation"]["checks"]["subject_core_tasks_included"])
        self.assertEqual(
            set(self.agent.plan_narrator.calls[-1]["knowledge_profiles_by_subject"]),
            {"mathematics", "physics"},
        )
        narrator_attempts = self.agent.plan_narrator.calls[-1][
            "diagnostic_attempts_by_subject"
        ]
        self.assertEqual(set(narrator_attempts), {"mathematics", "physics"})
        self.assertTrue(
            all(
                "函数与导数" in item["knowledge_focus"]
                for item in narrator_attempts["mathematics"]["questions"]
            )
        )
        self.assertTrue(
            all(
                "运动与力" in item["knowledge_focus"]
                for item in narrator_attempts["physics"]["questions"]
            )
        )

    async def test_multi_subject_plan_requires_diagnosis_for_every_subject(self) -> None:
        payload = planner_payload()
        payload["goals"] = [
            {
                "subject": "mathematics",
                "current_value": 92,
                "target_value": 120,
                "deadline": "2027-05-20",
            },
            {
                "subject": "physics",
                "current_value": 62,
                "target_value": 80,
                "deadline": "2027-05-20",
            },
        ]
        payload["knowledge_evidence_by_subject"] = {
            "mathematics": diagnostic_evidence(["PEA-E2-C05_foundation"]),
        }

        response = await self.agent.ainvoke(
            self.request("initialize_plan", payload, "multi-subject-missing-evidence")
        )

        self.assertEqual(response.status, StandardStatus.NEED_MORE_INFORMATION)
        self.assertIn("physics", response.result["questions"][0]["text"])

    async def test_unregistered_physics_module_is_rejected(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["curriculum_versions"] = {"physics": "people_education"}
        payload["student_profile"]["class_progress"] = {"physics": "invented_module"}
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))
        self.assertEqual(response.status, StandardStatus.FAILED)
        self.assertEqual(response.errors[0].code, "INPUT_VALIDATION_ERROR")

    async def test_three_plus_three_selection_can_publish(self) -> None:
        payload = planner_payload()
        payload["student_profile"].update(
            {
                "province_code": "33",
                "selected_subjects": ["physics", "chemistry", "technology"],
            }
        )
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))

        self.assertEqual(response.status, StandardStatus.SUCCESS, response.errors)
        self.assertTrue(response.result["plan"]["validation"]["checks"]["subject_selection_legal"])
        self.assertTrue(response.result["plan"]["validation"]["valid"])

    async def test_single_subject_plan_keeps_required_training_tasks(self) -> None:
        payload = planner_payload()
        payload["daily_capacity"] = [
            {
                "weekday": day,
                "available_minutes": 45 if day <= 5 else 90,
                "preferred_period": "evening" if day <= 5 else "morning",
                "energy_coefficient": 0.9,
            }
            for day in range(1, 8)
        ]
        payload["subject_factors"] = {
            "mathematics": {
                "goal_priority": 1,
                "score_gap": 0.2,
                "expected_score_gain": 1,
                "urgency": 0.85,
                "knowledge_dependency": 1,
            }
        }
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))

        self.assertEqual(response.status, StandardStatus.SUCCESS, response.errors)
        plan = response.result["plan"]
        task_types = {task["task_type"] for task in plan["tasks"]}
        self.assertTrue({"timed_training", "stage_assessment"} <= task_types)
        self.assertEqual(set(plan["subject_time_budgets"]), {"mathematics"})
        self.assertTrue(plan["validation"]["valid"])

    async def test_missing_planner_model_fails_without_saving_template_plan(self) -> None:
        unavailable = PersonalizedLearningPlannerAgent(
            settings=replace(self.agent.settings, llm_enabled=False)
        )
        response = await unavailable.ainvoke(self.request("initialize_plan", planner_payload()))
        self.assertEqual(response.status, StandardStatus.FAILED)
        self.assertEqual(response.errors[0].code, "PLANNER_LLM_UNAVAILABLE")
        self.assertFalse(unavailable.repository.plans)

    def test_single_score_anomaly_does_not_trigger_stage_replan(self) -> None:
        level = self.agent.plan_service.adjustment_level(
            {"critical_mastery_drop": 0.15, "independent_evidence_count": 1}
        )
        self.assertIsNone(level)

    def test_repeated_mastery_drop_triggers_stage_replan(self) -> None:
        level = self.agent.plan_service.adjustment_level(
            {"critical_mastery_drop": 0.15, "independent_evidence_count": 2}
        )
        self.assertEqual(level, "stage_replan")


if __name__ == "__main__":
    unittest.main()
