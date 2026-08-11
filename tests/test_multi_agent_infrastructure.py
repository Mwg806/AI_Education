from __future__ import annotations

import unittest

from ai_education.config import PROJECT_ROOT
from ai_education.domain.enums import AgentRole
from ai_education.domain.multi_agent import LearningEvent, LearningEventType
from ai_education.domain.retrieval import (
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
    SourceCitation,
)
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.retrieval_evaluator import evaluate_rankings
from scripts.apply_migrations import migration_files, statements


class MigrationInfrastructureTests(unittest.TestCase):
    def test_additive_schema_contains_reliability_tables(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        for table in (
            "schema_migrations",
            "learning_event_outbox",
            "actor_orchestration_runs",
            "actor_execution_traces",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)

    def test_migrations_are_ordered_and_rollback_is_not_executed(self) -> None:
        files = migration_files(PROJECT_ROOT / "migrations")
        names = [item.name for item in files]
        self.assertEqual(names, sorted(names))
        self.assertLess(
            names.index("20260811_progressive_multi_agent.sql"),
            names.index("20260811_remediation_v1.sql"),
        )
        self.assertFalse(any(name.endswith(".rollback.sql") for name in names))

    def test_sql_splitter_ignores_comments(self) -> None:
        self.assertEqual(
            statements("-- note\nCREATE TABLE sample(id INT);\nSELECT 1;"),
            ["CREATE TABLE sample(id INT)", "SELECT 1"],
        )


class RetrievalContractTests(unittest.TestCase):
    def test_unified_retrieval_contract_hides_restricted_answer(self) -> None:
        query = RetrievalQuery(
            query="函数单调性",
            agent_role="homework_tutor",
            subject="mathematics",
        )
        citation = SourceCitation(
            source_id="curriculum_math_function",
            title="函数单调性课程标准材料",
            source_type="curriculum_knowledge",
            authority_level="A",
            license_status="owned",
        )
        response = RetrievalResponse(
            query=query,
            results=[
                RetrievalResult(
                    result_id="result_1",
                    text="单调性判断的公开知识摘要",
                    score=0.92,
                    citation=citation,
                    contains_restricted_answer=False,
                )
            ],
            index_version="test-v1",
        )
        self.assertFalse(response.results[0].contains_restricted_answer)
        self.assertEqual(response.results[0].citation.source_id, "curriculum_math_function")

    def test_recall_mrr_and_citation_accuracy(self) -> None:
        metrics = evaluate_rankings(
            [["a", "x", "b"], ["z", "c"]],
            [{"a", "b"}, {"c"}],
            k=3,
        )
        self.assertEqual(metrics.recall_at_k, 1.0)
        self.assertEqual(metrics.mean_reciprocal_rank, 0.75)
        self.assertEqual(metrics.citation_accuracy, 0.6)
        self.assertEqual(metrics.query_count, 2)


class OutboxReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_event_is_replayed_and_marked_processed(self) -> None:
        event = LearningEvent(
            event_type=LearningEventType.QUESTION_WRONG,
            user_id="student_replay",
            agent=AgentRole.HOMEWORK_TUTOR,
            subject="mathematics",
            knowledge_point="function.monotonicity",
            score=0.0,
            metadata={"source_item_id": "independent_homework_1"},
        )

        class Repository:
            processed: list[str] = []

            def list_pending_event_outbox(self, limit: int = 100):
                return [{"event_id": event.event_id, "payload": event.model_dump(mode="json")}]

            def mark_event_processed(self, event_id: str) -> None:
                self.processed.append(event_id)

            def mark_event_failed(self, event_id: str, error: str) -> None:
                raise AssertionError(error)

        class ProfileService:
            applied: list[str] = []

            async def apply_event(self, item: LearningEvent) -> None:
                self.applied.append(item.event_id)

        repository = Repository()
        profile = ProfileService()
        result = await LearningEventService(repository, profile).replay_pending_outbox()
        self.assertEqual(result, {"examined": 1, "processed": 1, "failed": []})
        self.assertEqual(repository.processed, [event.event_id])
        self.assertEqual(profile.applied, [event.event_id])


if __name__ == "__main__":
    unittest.main()
