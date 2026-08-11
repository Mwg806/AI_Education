from __future__ import annotations

import unittest
from dataclasses import replace

from ai_education.config import Settings
from ai_education.domain.enums import ActorType, AgentRole
from ai_education.domain.multi_agent import (
    AgentTask,
    LearningEvent,
    LearningEventType,
    OrchestrationPlan,
    RoutingDecision,
    UnifiedStudentProfile,
)
from ai_education.domain.protocols import Operator
from ai_education.orchestration.capability_adapters import (
    AdapterContext,
    CapabilityAdapterRegistry,
)
from ai_education.orchestration.orchestrator import ProgressiveAgentOrchestrator
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.model_router import ModelRouter
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository


class CapabilityAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CapabilityAdapterRegistry()
        self.profile = UnifiedStudentProfile(
            user_id="student_adapter",
            basic_profile={
                "grade": "grade_12",
                "province_code": "43",
                "target_exam_year": 2027,
            },
        )
        self.student = Operator(type=ActorType.STUDENT, id="student_adapter")

    def context(
        self,
        message: str,
        *,
        subject: str = "foreign_language",
        request_context: dict | None = None,
        actor: Operator | None = None,
    ) -> AdapterContext:
        return AdapterContext(
            user_id="student_adapter",
            message=message,
            subject=subject,
            request_context=request_context or {},
            profile=self.profile,
            actor=actor or self.student,
        )

    def test_six_registered_roles_have_native_task_builders(self) -> None:
        scenarios = {
            AgentRole.PERSONALIZED_LEARNING_PLANNER: self.context("查看我的学习计划"),
            AgentRole.HOMEWORK_TUTOR: self.context("我有一道数学作业不会做", subject="mathematics"),
            AgentRole.LEARNING_DIAGNOSIS: self.context("分析最近英语薄弱点"),
            AgentRole.TEACHER_PREPARATION: self.context(
                "搜索函数单调性教学资源",
                subject="mathematics",
                actor=Operator(type=ActorType.TEACHER, id="teacher_adapter"),
            ),
            AgentRole.ENGLISH_READING_LANGUAGE: self.context("查看英语学习进展"),
            AgentRole.PROGRAMMING_LEARNING: self.context("我想学 Python 后端"),
        }
        self.assertEqual(self.registry.roles, set(scenarios))
        for role, context in scenarios.items():
            tasks = self.registry.get(role).tasks(context, [])
            self.assertGreaterEqual(len(tasks), 1)
            self.assertTrue(all(task.agent == role for task in tasks))
            self.assertTrue(all(task.intent for task in tasks))

    def test_composite_subject_diagnosis_runs_in_parallel_before_planner(self) -> None:
        routing = RoutingDecision(
            intents=["diagnose_learning_state", "adapt_learning_plan"],
            primary_agent=AgentRole.LEARNING_DIAGNOSIS,
            required_agents=[
                AgentRole.LEARNING_DIAGNOSIS,
                AgentRole.PERSONALIZED_LEARNING_PLANNER,
            ],
            execution_mode="sequential",
            reason="先诊断两科再规划",
            confidence=0.96,
        )
        plan = self.registry.build_plan(
            routing,
            self.context(
                "帮我分析最近英语和数学的问题，并安排下周学习计划",
                subject="mathematics",
            ),
        )
        diagnoses = [task for task in plan.tasks if task.agent == AgentRole.LEARNING_DIAGNOSIS]
        planner = next(
            task for task in plan.tasks if task.agent == AgentRole.PERSONALIZED_LEARNING_PLANNER
        )
        self.assertEqual({task.subject for task in diagnoses}, {"foreign_language", "mathematics"})
        self.assertEqual(set(planner.depends_on), {task.task_id for task in diagnoses})
        self.assertEqual(plan.execution_mode, "hybrid")

    def test_missing_context_is_explicit_instead_of_fabricated(self) -> None:
        english = self.registry.get(AgentRole.ENGLISH_READING_LANGUAGE).tasks(
            self.context("帮我判断这段话的语法"), []
        )[0]
        project = self.registry.get(AgentRole.PROGRAMMING_LEARNING).tasks(
            self.context("我的项目下一步应该做什么", subject="technology"), []
        )[0]
        teacher = self.registry.get(AgentRole.TEACHER_PREPARATION).tasks(
            self.context("根据本班函数单调性诊断生成复习课", subject="mathematics"), []
        )[0]
        self.assertEqual(english.missing_context[0].field, "source_text")
        self.assertEqual(project.missing_context[0].field, "project_session_id")
        self.assertEqual(teacher.missing_context[0].field, "teacher_authorization")


class EvidenceFusionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = SharedLearningRepository()
        self.profile_service = StudentProfileService(self.repository)
        self.event_service = LearningEventService(self.repository, self.profile_service)

    async def test_same_assessment_does_not_inflate_mastery(self) -> None:
        for index in range(3):
            await self.event_service.emit(
                LearningEvent(
                    event_id=f"repeat_{index}",
                    event_type=LearningEventType.QUESTION_WRONG,
                    user_id="student_repeat",
                    agent=AgentRole.HOMEWORK_TUTOR,
                    subject="mathematics",
                    knowledge_point="functions.monotonicity",
                    score=0,
                    session_id="same_homework_session",
                    metadata={"source_item_id": "same_question"},
                )
            )
        profile = await self.profile_service.get_profile("student_repeat")
        snapshot = profile.knowledge_mastery["mathematics.functions.monotonicity"]
        self.assertEqual(snapshot.independent_assessment_count, 1)
        self.assertEqual(snapshot.error_count, 1)
        self.assertNotIn("mathematics.functions.monotonicity", profile.weak_points)

    async def test_three_independent_assessments_create_stable_signal(self) -> None:
        for index in range(3):
            await self.event_service.emit(
                LearningEvent(
                    event_id=f"independent_{index}",
                    event_type=LearningEventType.GRAMMAR_ERROR,
                    user_id="student_independent",
                    agent=AgentRole.ENGLISH_READING_LANGUAGE,
                    subject="foreign_language",
                    knowledge_point="grammar.relative_clause",
                    score=0,
                    session_id=f"grammar_sentence_{index}",
                    difficulty=0.4 + index * 0.1,
                    confidence=0.8,
                    metadata={"source_reliability": 0.75},
                )
            )
        profile = await self.profile_service.get_profile("student_independent")
        key = "foreign_language.grammar.relative_clause"
        self.assertIn(key, profile.weak_points)
        self.assertEqual(profile.knowledge_mastery[key].independent_assessment_count, 3)


class OrchestrationStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_evidence_with_skipped_dependency_is_not_failure(self) -> None:
        orchestrator = object.__new__(ProgressiveAgentOrchestrator)

        class Synthesizer:
            async def synthesize(self, facts):
                return None

        orchestrator.response_synthesizer = Synthesizer()
        diagnosis = AgentTask(
            agent=AgentRole.LEARNING_DIAGNOSIS,
            intent="ingest_learning_evidence",
            objective="诊断英语阅读",
            status="needs_input",
            status_message="需要真实作答记录",
        )
        planner = AgentTask(
            agent=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            intent="apply_diagnosis_to_plan",
            objective="安排训练",
            depends_on=[diagnosis.task_id],
            status="skipped",
            status_message="依赖诊断尚未完成",
        )
        plan = OrchestrationPlan(
            goal="诊断后规划",
            execution_mode="sequential",
            tasks=[diagnosis, planner],
        )
        result = await orchestrator._finalize(
            {
                "orchestration_plan": plan.model_dump(mode="json"),
                "task_results": {
                    diagnosis.task_id: {
                        "status": "need_more_information",
                        "result": {"message": "需要真实作答记录"},
                    },
                    planner.task_id: {
                        "status": "skipped",
                        "result": {"message": "依赖诊断尚未完成"},
                    },
                },
            }
        )
        self.assertEqual(result["status"], "need_more_information")
        self.assertEqual(result["response_generation_mode"], "rule_summary")


class ModelRouterTests(unittest.TestCase):
    def test_capability_selection_is_observable(self) -> None:
        settings = replace(Settings.from_env(), llm_enabled=False, llm_model="default-test-model")
        router = ModelRouter(settings)
        self.assertEqual(router.select("intent_routing").capability, "routing")
        self.assertEqual(router.select("coding_review").capability, "code")
        self.assertEqual(router.select("homework_image", needs_vision=True).capability, "vision")
        self.assertEqual(router.select("response_synthesis").capability, "synthesis")


if __name__ == "__main__":
    unittest.main()
