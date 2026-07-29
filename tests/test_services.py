from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from ai_education.config import Settings
from ai_education.domain.enums import Subject
from ai_education.domain.models import PracticeEvent, StudentAcademicProfile
from ai_education.llm.factory import create_chat_model
from ai_education.repositories import PlannerRepository
from ai_education.services.curriculum_catalog import CurriculumCatalogService
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

    def test_all_national_i_scope_provinces_resolve(self) -> None:
        service = ExamPolicyService()
        catalog = CurriculumCatalogService().onboarding_catalog()
        resolved = [service.resolve(item["code"], 2025, 2028) for item in catalog["provinces"]]
        self.assertEqual(len(resolved), 11)
        self.assertTrue(
            all(profile.national_paper_type == "national_paper_i" for profile in resolved)
        )
        self.assertTrue(all(profile.requires_annual_reconfirmation for profile in resolved))

    def test_zhejiang_three_plus_three_allows_technology(self) -> None:
        service = ExamPolicyService()
        profile = service.resolve("33", 2024, 2027)
        student = StudentAcademicProfile.model_validate(
            {
                "student_id": "zj_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "33",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {"mathematics": "people_education_a"},
                "selected_subjects": ["physics", "chemistry", "technology"],
                "subject_selection_confirmed": True,
                "class_progress": {"mathematics": "PEA-E2-C05"},
            }
        )
        self.assertEqual(profile.subject_model, "3_plus_3")
        self.assertIn("technology", profile.elective_subjects)
        self.assertEqual(service.validate(profile, student), [])


class CurriculumCatalogServiceTests(unittest.TestCase):
    def test_catalog_has_complete_verified_pep_math_chapters(self) -> None:
        service = CurriculumCatalogService()
        catalog = service.onboarding_catalog()
        editions = {item["id"]: item for item in catalog["mathematics"]["editions"]}
        self.assertEqual(
            sum(len(volume["chapters"]) for volume in editions["people_education_a"]["volumes"]),
            18,
        )
        self.assertEqual(
            sum(len(volume["chapters"]) for volume in editions["people_education_b"]["volumes"]),
            17,
        )

    def test_unverified_edition_uses_standard_modules_not_invented_chapters(self) -> None:
        service = CurriculumCatalogService()
        edition = service.math_edition("beijing_normal")
        self.assertEqual(edition["volumes"], [])
        self.assertGreaterEqual(len(service.mathematics_standard_modules()), 10)


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
