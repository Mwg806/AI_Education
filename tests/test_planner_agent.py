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


if __name__ == "__main__":
    unittest.main()
