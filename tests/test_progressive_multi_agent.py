from __future__ import annotations

import unittest
from dataclasses import replace

from ai_education.agents.learning_diagnosis import LearningDiagnosisAgent
from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.config import Settings
from ai_education.diagnosis_repository import DiagnosisRepository
from ai_education.domain.enums import AgentRole
from ai_education.domain.multi_agent import (
    LearningEvent,
    LearningEventType,
    OrchestrationInput,
)
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.orchestration.bus import AgentMessageBus
from ai_education.orchestration.intent_router import IntentRouter
from ai_education.orchestration.orchestrator import ProgressiveAgentOrchestrator
from ai_education.orchestration.registry import AgentRegistry
from ai_education.repositories import PlannerRepository
from ai_education.services.shared.agent_execution_service import AgentExecutionService
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.model_router import ModelRouter
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository


class ProgressiveSharedStateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = SharedLearningRepository()
        self.profile_service = StudentProfileService(self.repository)
        self.event_service = LearningEventService(self.repository, self.profile_service)

    async def test_duplicate_event_is_idempotent(self) -> None:
        event = LearningEvent(
            event_id="learn_evt_duplicate",
            event_type=LearningEventType.QUESTION_WRONG,
            user_id="student_profile",
            agent=AgentRole.HOMEWORK_TUTOR,
            subject="mathematics",
            knowledge_point="functions.monotonicity",
            score=0,
        )
        await self.event_service.emit(event)
        first = await self.profile_service.get_profile("student_profile")
        await self.event_service.emit(event)
        second = await self.profile_service.get_profile("student_profile")
        self.assertEqual(first.profile_version, second.profile_version)
        self.assertEqual(len(await self.event_service.get_recent_events("student_profile")), 1)

    async def test_three_errors_create_weak_point_and_diagnosis_signal(self) -> None:
        for index in range(3):
            await self.event_service.emit(
                LearningEvent(
                    event_id=f"learn_evt_wrong_{index}",
                    event_type=LearningEventType.READING_ERROR,
                    user_id="student_weak",
                    agent=AgentRole.ENGLISH_READING_LANGUAGE,
                    subject="foreign_language",
                    knowledge_point="reading.inference",
                    score=0,
                    session_id=f"reading_session_{index}",
                    metadata={"error_type": "reading_error"},
                )
            )
        profile = await self.profile_service.get_profile("student_weak")
        summary = await self.event_service.summarize_recent_learning("student_weak")
        key = "foreign_language.reading.inference"
        self.assertIn(key, profile.weak_points)
        self.assertEqual(profile.knowledge_mastery[key].error_count, 3)
        self.assertEqual(
            summary["diagnosis_signals"],
            [{"knowledge_point": "reading.inference", "error_count": 3}],
        )

    def test_additive_schema_contains_progressive_tables(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        for table in (
            "unified_student_profiles",
            "unified_learning_events",
            "agent_orchestration_runs",
            "agent_execution_traces",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)


class ProgressiveOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        settings = replace(Settings.from_env(), llm_enabled=False, llm_model="")
        model_router = ModelRouter(settings)
        registry = AgentRegistry()
        registry.register(
            PersonalizedLearningPlannerAgent(
                PlannerRepository(), settings, model_router.default_model
            )
        )
        registry.register(
            LearningDiagnosisAgent(DiagnosisRepository(), settings, model_router.default_model)
        )
        repository = SharedLearningRepository()
        profile_service = StudentProfileService(repository)
        event_service = LearningEventService(repository, profile_service)
        execution = AgentExecutionService(
            registry,
            profile_service,
            event_service,
            repository,
            model_router,
            AgentMessageBus(),
        )
        self.orchestrator = ProgressiveAgentOrchestrator(
            IntentRouter(model_router),
            execution,
            profile_service,
            event_service,
            repository,
        )
        self.profile_service = profile_service
        self.event_service = event_service
        await profile_service.update_profile(
            "student_chain",
            {
                "basic_profile": {
                    "grade": "grade_12",
                    "province_code": "43",
                    "target_exam_year": 2027,
                }
            },
        )
        for index in range(3):
            await event_service.emit(
                LearningEvent(
                    event_id=f"learn_evt_chain_{index}",
                    event_type=LearningEventType.READING_ERROR,
                    user_id="student_chain",
                    agent=AgentRole.ENGLISH_READING_LANGUAGE,
                    subject="foreign_language",
                    knowledge_point="reading.inference",
                    difficulty=0.4 + index * 0.1,
                    score=0,
                    session_id=f"reading_chain_{index}",
                    metadata={
                        "source_item_id": f"reading_question_{index}",
                        "error_type": "reading_error",
                        "question_type": "reading_inference",
                    },
                )
            )

    async def test_english_diagnosis_then_planning(self) -> None:
        result = await self.orchestrator.orchestrate(
            "student_chain",
            OrchestrationInput(
                message="英语阅读一直不好，分析原因然后安排怎么练",
                subject="foreign_language",
            ),
        )
        self.assertEqual(
            result.routing.required_agents,
            [
                AgentRole.LEARNING_DIAGNOSIS,
                AgentRole.PERSONALIZED_LEARNING_PLANNER,
            ],
        )
        self.assertEqual(result.routing.execution_mode, "sequential")
        self.assertEqual(len(result.handoffs), 2)
        self.assertIn("learning_state", result.agent_results["learning_diagnosis"]["result"])
        adaptation = result.agent_results["personalized_learning_planner"]["result"][
            "plan_adaptation"
        ]
        self.assertFalse(adaptation["mutation_applied"])
        self.assertTrue(adaptation["requires_confirmation"])
        self.assertEqual(len(adaptation["seven_day_schedule"]), 7)
        self.assertIn("7 天训练建议", result.final_response)


if __name__ == "__main__":
    unittest.main()
