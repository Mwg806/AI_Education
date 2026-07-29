from __future__ import annotations

import unittest

from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.domain.enums import ActorType, StandardStatus
from ai_education.domain.protocols import AgentRequest, Operator
from tests.fixtures import planner_payload


class PlannerAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.agent = PersonalizedLearningPlannerAgent()

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

    async def test_unregistered_physics_module_is_rejected(self) -> None:
        payload = planner_payload()
        payload["student_profile"]["curriculum_versions"] = {"physics": "people_education"}
        payload["student_profile"]["class_progress"] = {"physics": "invented_module"}
        response = await self.agent.ainvoke(self.request("initialize_plan", payload))
        self.assertEqual(response.status, StandardStatus.FAILED)
        self.assertEqual(response.errors[0].code, "INPUT_VALIDATION_ERROR")

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
