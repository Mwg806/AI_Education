from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from ai_education.config import Settings
from ai_education.domain.enums import Subject
from ai_education.domain.models import PracticeEvent
from ai_education.llm.factory import create_chat_model
from ai_education.repositories import PlannerRepository
from ai_education.services.goal import GoalService
from ai_education.services.knowledge import KnowledgeService
from ai_education.services.policy import ExamPolicyService
from ai_education.services.practice import PracticeService


class GoalServiceTests(unittest.TestCase):
    def test_parse_does_not_invent_deadline(self) -> None:
        result = GoalService().parse("数学从92分提高到120分")
        self.assertEqual(result.subject, Subject.MATHEMATICS)
        self.assertEqual(result.current_value, 92)
        self.assertEqual(result.target_value, 120)
        self.assertIsNone(result.deadline)
        self.assertIn("deadline", result.missing_fields)

    def test_clarification_is_limited_to_two_questions(self) -> None:
        parsed = GoalService().parse("我想提高")
        self.assertLessEqual(len(GoalService().clarification_questions(parsed)), 2)


class PolicyServiceTests(unittest.TestCase):
    def test_resolve_versioned_policy(self) -> None:
        profile = ExamPolicyService().resolve("43", 2024, 2027)
        self.assertEqual(profile.national_paper_type, "national_paper_i")
        self.assertEqual(profile.policy_version, "policy_2026_07")


class ModelFactoryTests(unittest.TestCase):
    def test_openai_compatible_model_uses_environment_without_network(self) -> None:
        environment = {
            "AI_EDUCATION_LLM_ENABLED": "true",
            "AI_EDUCATION_LLM_PROVIDER": "openai",
            "AI_EDUCATION_LLM_MODEL": "test-model",
            "OPENAI_API_KEY": "test-only-placeholder",
            "OPENAI_BASE_URL": "https://example.invalid/v1",
        }
        with patch.dict("os.environ", environment, clear=False):
            model = create_chat_model(Settings.from_env())
        self.assertEqual(model.model_name, "test-model")


class PracticeServiceTests(unittest.TestCase):
    def test_duplicate_event_does_not_update_twice(self) -> None:
        repository = PlannerRepository()
        profile = KnowledgeService().build_profile(
            "s1",
            Subject.MATHEMATICS,
            [{"knowledge_id": "k1", "score": 0.5, "weight": 0.8}],
        )
        repository.save_knowledge_profile(profile)
        service = PracticeService(repository)
        event = PracticeEvent(
            event_id="evt_1",
            student_id="s1",
            session_id="session_1",
            item_id="item_1",
            subject=Subject.MATHEMATICS,
            knowledge_ids=["k1"],
            event_type="answer_submitted",
            timestamp=datetime.now().astimezone(),
            response={"correct": True, "score": 5, "max_score": 5, "difficulty": 0.6},
            behavior={"response_time_seconds": 300, "expected_time_seconds": 300},
        )
        first = service.ingest(event)
        count_after_first = repository.knowledge_profiles["s1"].knowledge_states[0].evidence_count
        second = service.ingest(event)
        count_after_second = repository.knowledge_profiles["s1"].knowledge_states[0].evidence_count
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(count_after_first, count_after_second)


if __name__ == "__main__":
    unittest.main()
