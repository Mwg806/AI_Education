from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from ai_education.api.app import AppContainer, create_app
from ai_education.domain.enums import ActorType, AgentRole
from ai_education.domain.multi_agent import RoutingDecision, UnifiedStudentProfile
from ai_education.domain.protocols import Operator
from ai_education.orchestration.capability_adapters import (
    AdapterContext,
    CapabilityAdapterRegistry,
)
from ai_education.services.shared.collaboration_memory_service import (
    CollaborationMemoryService,
)
from ai_education.shared_learning_repository import SharedLearningRepository


def seed_message(
    repository: SharedLearningRepository,
    *,
    user_id: str,
    session_id: str,
    sequence: int,
    role: str,
    content: str,
    occurred_at: datetime,
) -> None:
    repository.save_collaboration_message(
        {
            "message_id": f"message_{session_id}_{sequence}",
            "user_id": user_id,
            "session_id": session_id,
            "run_id": f"run_{session_id}",
            "role": role,
            "subject": "general",
            "content": content,
            "metadata": {},
            "created_at": occurred_at,
        }
    )


class PlanningConversationRepositoryTests(unittest.TestCase):
    def test_sessions_are_sorted_summarized_and_isolated_by_student(self) -> None:
        repository = SharedLearningRepository()
        started_at = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)
        for user_id, session_id, offset in (
            ("student_a", "session_older", 0),
            ("student_a", "session_newer", 10),
            ("student_b", "session_private", 20),
        ):
            repository.ensure_collaboration_session(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "context": {"entry": "overall_planning"},
                    "occurred_at": started_at + timedelta(minutes=offset),
                }
            )

        seed_message(
            repository,
            user_id="student_a",
            session_id="session_older",
            sequence=1,
            role="user",
            content="请帮我安排第一周的整体复习计划",
            occurred_at=started_at,
        )
        seed_message(
            repository,
            user_id="student_a",
            session_id="session_newer",
            sequence=1,
            role="user",
            content="我想重新规划英语和数学的学习优先级",
            occurred_at=started_at + timedelta(minutes=10),
        )
        seed_message(
            repository,
            user_id="student_b",
            session_id="session_private",
            sequence=1,
            role="user",
            content="这是另一个学生的私密对话",
            occurred_at=started_at + timedelta(minutes=20),
        )

        sessions = repository.list_collaboration_sessions("student_a")

        self.assertEqual(
            [item["session_id"] for item in sessions],
            ["session_newer", "session_older"],
        )
        self.assertEqual(sessions[0]["title"], "我想重新规划英语和数学的学习优先级")
        self.assertNotIn("私密", str(sessions))
        self.assertEqual(
            [item["session_id"] for item in repository.list_collaboration_messages(
                "student_a", session_id="session_older"
            )],
            ["session_older"],
        )

    def test_general_planning_mode_auto_detects_subject_for_specialist(self) -> None:
        registry = CapabilityAdapterRegistry()
        plan = registry.build_plan(
            RoutingDecision(
                intents=["diagnose_learning_state"],
                primary_agent=AgentRole.LEARNING_DIAGNOSIS,
                required_agents=[AgentRole.LEARNING_DIAGNOSIS],
                execution_mode="single",
                reason="test",
                confidence=1,
            ),
            AdapterContext(
                user_id="student_a",
                message="请分析我最近的英语阅读问题",
                subject="general",
                request_context={},
                profile=UnifiedStudentProfile(user_id="student_a"),
                actor=Operator(type=ActorType.STUDENT, id="student_a"),
            ),
        )

        self.assertEqual(plan.tasks[0].subject, "foreign_language")


class PlanningConversationMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stable_memory_crosses_windows_but_recent_context_does_not(self) -> None:
        repository = SharedLearningRepository()
        service = CollaborationMemoryService(repository)
        profile = UnifiedStudentProfile(user_id="student_memory")

        first = await service.begin_interaction(
            user_id="student_memory",
            session_id="session_goal",
            run_id="run_goal",
            message="我的目标是提高数学成绩，希望规划更简洁",
            subject="general",
            profile=profile,
            recent_events=[],
        )
        await service.record_response(
            first,
            session_id="session_goal",
            run_id="run_goal",
            subject="general",
            response="已记录你的长期目标。",
            status="success",
            agents=["personalized_learning_planner"],
        )
        second = await service.begin_interaction(
            user_id="student_memory",
            session_id="session_weekly",
            run_id="run_weekly",
            message="这周先从哪里开始？",
            subject="general",
            profile=profile,
            recent_events=[],
        )

        self.assertTrue(second.declared_goals)
        self.assertTrue(second.declared_preferences)
        self.assertEqual(
            {item["session_id"] for item in second.recent_messages},
            {"session_goal", "session_weekly"},
        )
        context = service.context_for_agents(second)
        self.assertEqual(
            [item["content"] for item in context["recent_collaboration"]],
            ["这周先从哪里开始？"],
        )


class PlanningConversationApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_student_can_read_own_conversation_list_and_messages(self) -> None:
        container = AppContainer(enable_persistence=False)
        repository = container.shared_learning_repository
        occurred_at = datetime(2026, 9, 9, 9, 0, tzinfo=UTC)
        repository.ensure_collaboration_session(
            {
                "user_id": "student_api",
                "session_id": "session_api",
                "context": {"entry": "overall_planning"},
                "occurred_at": occurred_at,
            }
        )
        seed_message(
            repository,
            user_id="student_api",
            session_id="session_api",
            sequence=1,
            role="user",
            content="读取我的历史规划",
            occurred_at=occurred_at,
        )
        app = create_app(container)

        @app.middleware("http")
        async def inject_student_session(request, call_next):
            request.state.student_profile = {
                "role": "student",
                "studentId": "student_api",
                "studentName": "测试学生",
            }
            return await call_next(request)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            conversations = await client.get("/api/v1/orchestration/conversations")
            messages = await client.get(
                "/api/v1/orchestration/conversations/session_api/messages"
            )

        self.assertEqual(conversations.status_code, 200, conversations.text)
        self.assertEqual(
            conversations.json()["conversations"][0]["session_id"], "session_api"
        )
        self.assertEqual(messages.status_code, 200, messages.text)
        self.assertEqual(messages.json()["messages"][0]["content"], "读取我的历史规划")


if __name__ == "__main__":
    unittest.main()
