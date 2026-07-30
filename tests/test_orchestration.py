from __future__ import annotations

import unittest

from ai_education.agents.base import BaseEducationAgent
from ai_education.agents.homework_tutoring import HomeworkTutoringAgent
from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.core.errors import DataConflictError, InputValidationError
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus
from ai_education.domain.protocols import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    CollaborationRequest,
    CollaborationTask,
    Operator,
)
from ai_education.orchestration.coordinator import MultiAgentCoordinator
from ai_education.orchestration.global_state import GlobalStateStore
from ai_education.orchestration.registry import AgentRegistry


class EchoAgent(BaseEducationAgent):
    def __init__(self, role: AgentRole, intent: str) -> None:
        self.role = role
        self.intent = intent

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id=f"test_{self.role}",
            role=self.role,
            version="1.0.0",
            description="test agent",
            capabilities={self.intent},
            accepted_intents={self.intent},
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=self.role,
            status=StandardStatus.SUCCESS,
            lifecycle_status="COMPLETED",
            result={
                "handled_intent": request.intent,
                "dependency_results": request.context.get("dependency_results", {}),
            },
        )


class MultiAgentCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_planner_and_homework_agent_intents_do_not_conflict(self) -> None:
        registry = AgentRegistry()
        planner = PersonalizedLearningPlannerAgent()
        homework = HomeworkTutoringAgent()
        registry.register(planner)
        registry.register(homework)
        self.assertEqual(registry.find_by_intent("initialize_plan"), [planner])
        self.assertEqual(registry.find_by_intent("homework_turn"), [homework])
        self.assertEqual(len(registry), 2)

    async def test_seven_agents_route_without_framework_changes(self) -> None:
        roles = [
            AgentRole.PERSONALIZED_LEARNING_PLANNER,
            AgentRole.TEACHING_EXPLAINER,
            AgentRole.QUESTION_GENERATOR,
            AgentRole.ASSESSMENT_GRADER,
            AgentRole.LEARNING_COMPANION,
            AgentRole.CAREER_PLANNER,
            AgentRole.TEACHER_ASSISTANT,
        ]
        registry = AgentRegistry()
        tasks = []
        for index, role in enumerate(roles):
            intent = f"intent_{index}"
            registry.register(EchoAgent(role, intent))
            tasks.append(
                CollaborationTask(
                    task_id=f"task_{index}",
                    intent=intent,
                    preferred_agent=role,
                    depends_on={f"task_{index - 1}"} if index else set(),
                )
            )
        self.assertEqual(len(registry), 7)
        coordinator = MultiAgentCoordinator(registry, max_parallelism=4)
        request = CollaborationRequest(
            student_id="student_multi",
            actor=Operator(type=ActorType.SYSTEM, id="test"),
            tasks=tasks,
        )
        response = await coordinator.coordinate(request)
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        self.assertEqual(len(response.task_results), 7)
        self.assertEqual(response.global_state_revision, 1)
        self.assertEqual(len(coordinator.bus.history(trace_id=request.trace_id)), 15)
        last = response.task_results["task_6"].result
        self.assertIn("task_5", last["dependency_results"])

    async def test_cycle_is_rejected_before_execution(self) -> None:
        registry = AgentRegistry()
        registry.register(EchoAgent(AgentRole.TEACHING_EXPLAINER, "explain"))
        coordinator = MultiAgentCoordinator(registry)
        request = CollaborationRequest(
            student_id="student_cycle",
            actor=Operator(type=ActorType.SYSTEM, id="test"),
            tasks=[
                CollaborationTask(
                    task_id="a",
                    intent="explain",
                    preferred_agent=AgentRole.TEACHING_EXPLAINER,
                    depends_on={"b"},
                ),
                CollaborationTask(
                    task_id="b",
                    intent="explain",
                    preferred_agent=AgentRole.TEACHING_EXPLAINER,
                    depends_on={"a"},
                ),
            ],
        )
        with self.assertRaises(InputValidationError):
            await coordinator.coordinate(request)


class GlobalStateTests(unittest.TestCase):
    def test_compare_and_swap_prevents_lost_updates(self) -> None:
        store = GlobalStateStore()
        revision, _ = store.compare_and_swap(
            "s1", expected_revision=0, updates={"plan": {"version": 1}}
        )
        self.assertEqual(revision, 1)
        with self.assertRaises(DataConflictError):
            store.compare_and_swap("s1", expected_revision=0, updates={"plan": {"version": 2}})


if __name__ == "__main__":
    unittest.main()
