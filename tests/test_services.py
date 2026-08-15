from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from ai_education.config import Settings
from ai_education.core.errors import InputValidationError
from ai_education.domain.enums import Subject
from ai_education.domain.models import PracticeEvent, StudentAcademicProfile
from ai_education.llm.factory import create_chat_model
from ai_education.repositories import PlannerRepository
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from ai_education.services.goal import GoalService
from ai_education.services.knowledge import KnowledgeService
from ai_education.services.policy import ExamPolicyService
from ai_education.services.practice import PracticeService
from ai_education.services.time_profile import TimeProfileService


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


class TimeProfileServiceTests(unittest.TestCase):
    def test_six_subjects_each_receive_the_minimum_executable_budget(self) -> None:
        subjects = [
            Subject.CHINESE,
            Subject.MATHEMATICS,
            Subject.FOREIGN_LANGUAGE,
            Subject.PHYSICS,
            Subject.CHEMISTRY,
            Subject.BIOLOGY,
        ]

        budgets = TimeProfileService().allocate_subject_budgets(
            subjects, {}, scheduled_minutes=360
        )

        self.assertEqual(set(budgets), {subject.value for subject in subjects})
        self.assertTrue(all(minutes == 60 for minutes in budgets.values()))

    def test_multi_subject_budget_rejects_silent_under_allocation(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "每科每周至少需要 60 分钟"):
            TimeProfileService().allocate_subject_budgets(
                [Subject.MATHEMATICS, Subject.PHYSICS],
                {},
                scheduled_minutes=119,
            )


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
    def test_catalog_covers_all_local_textbook_pdfs_and_editions(self) -> None:
        service = CurriculumCatalogService()
        catalog = service.onboarding_catalog()
        self.assertEqual(catalog["scope"]["textbook_pdf_count"], 329)
        edition_counts = {item["id"]: len(item["editions"]) for item in catalog["subjects"]}
        self.assertEqual(
            edition_counts,
            {
                "chinese": 1,
                "mathematics": 7,
                "foreign_language": 8,
                "physics": 6,
                "chemistry": 4,
                "biology": 6,
                "ideology_politics": 1,
                "history": 1,
                "geography": 5,
                "technology": 11,
            },
        )
        volumes = [
            volume
            for subject in catalog["subjects"]
            for edition in subject["editions"]
            for volume in edition["volumes"]
        ]
        self.assertEqual(len(volumes), 329)
        self.assertEqual(
            sum(volume["catalog_status"] == "UNREADABLE_PDF" for volume in volumes),
            4,
        )

    def test_unverified_edition_uses_standard_modules_not_invented_chapters(self) -> None:
        service = CurriculumCatalogService()
        edition = service.math_edition("beijing_normal")
        self.assertEqual(edition["volumes"], [])
        self.assertGreaterEqual(len(service.mathematics_standard_modules()), 10)

    def test_all_ten_planning_subjects_have_official_standard_sources(self) -> None:
        subjects = CurriculumCatalogService().onboarding_catalog()["subjects"]
        self.assertEqual(len(subjects), 10)
        self.assertTrue(all(item["standard_modules"] for item in subjects))
        self.assertTrue(all(item["standard_sources"] for item in subjects))

    def test_selected_physics_standard_module_is_valid(self) -> None:
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "physics_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "43",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {"physics": "people_education"},
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {"physics": "PHY-MECHANICS"},
            }
        )
        CurriculumCatalogService().validate_student_profile(profile)

    def test_six_planning_subjects_are_validated_together(self) -> None:
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "six_subject_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "43",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {
                    "chinese": "unified",
                    "mathematics": "people_education_a",
                    "foreign_language": "people_education",
                    "physics": "people_education",
                    "chemistry": "people_education",
                    "biology": "people_education",
                },
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {
                    "chinese": ["CHN-LANG"],
                    "mathematics": ["PEA-E2-C05"],
                    "foreign_language": ["ENG-LANGUAGE"],
                    "physics": ["PHY-MECHANICS"],
                    "chemistry": ["CHEM-CONCEPT"],
                    "biology": ["BIO-CELL"],
                },
            }
        )

        CurriculumCatalogService().validate_student_profile(profile)

    def test_local_pdf_chapter_id_is_accepted(self) -> None:
        service = CurriculumCatalogService()
        mathematics = service.subject_catalog("mathematics")
        edition = next(
            item
            for item in mathematics["editions"]
            if any(volume["chapters"] for volume in item["volumes"])
        )
        progress = next(
            chapter["id"] for volume in edition["volumes"] for chapter in volume["chapters"]
        )
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "pdf_catalog_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "43",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {"mathematics": edition["id"]},
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {"mathematics": progress},
            }
        )
        service.validate_student_profile(profile)

    def test_five_chapter_progress_ids_are_accepted(self) -> None:
        service = CurriculumCatalogService()
        mathematics = service.subject_catalog("mathematics")
        edition = next(
            item
            for item in mathematics["editions"]
            if sum(len(volume["chapters"]) for volume in item["volumes"]) >= 6
        )
        progress_ids = [
            chapter["id"] for volume in edition["volumes"] for chapter in volume["chapters"]
        ][:5]
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "multi_chapter_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "43",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {"mathematics": edition["id"]},
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {"mathematics": progress_ids},
            }
        )

        service.validate_student_profile(profile)

    def test_more_than_five_chapter_progress_ids_are_rejected(self) -> None:
        service = CurriculumCatalogService()
        mathematics = service.subject_catalog("mathematics")
        edition = next(
            item
            for item in mathematics["editions"]
            if sum(len(volume["chapters"]) for volume in item["volumes"]) >= 6
        )
        progress_ids = [
            chapter["id"] for volume in edition["volumes"] for chapter in volume["chapters"]
        ][:6]
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "too_many_chapters_student",
                "grade": "grade_11",
                "school_term": "grade_11_term_1",
                "province_code": "43",
                "school_entry_year": 2024,
                "target_exam_year": 2027,
                "curriculum_versions": {"mathematics": edition["id"]},
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {"mathematics": progress_ids},
            }
        )

        with self.assertRaises(InputValidationError):
            service.validate_student_profile(profile)

    def test_whole_book_progress_is_accepted(self) -> None:
        service = CurriculumCatalogService()
        mathematics = service.subject_catalog("mathematics")
        edition = next(item for item in mathematics["editions"] if item["volumes"])
        profile = StudentAcademicProfile.model_validate(
            {
                "student_id": "whole_book_student",
                "grade": "grade_12",
                "school_term": "grade_12_term_1",
                "province_code": "43",
                "school_entry_year": 2023,
                "target_exam_year": 2026,
                "curriculum_versions": {"mathematics": edition["id"]},
                "selected_subjects": ["physics", "chemistry", "biology"],
                "subject_selection_confirmed": True,
                "class_progress": {"mathematics": "__all_chapters__"},
            }
        )
        service.validate_student_profile(profile)

    def test_every_supported_subject_accepts_a_grounded_progress_id(self) -> None:
        service = CurriculumCatalogService()
        cases = {
            "chinese": ("unified", "CHN-LANG"),
            "mathematics": ("people_education_a", "PEA-E2-C05"),
            "foreign_language": ("people_education", "ENG-LANGUAGE"),
            "physics": ("people_education", "PHY-MECHANICS"),
            "chemistry": ("people_education", "CHEM-CONCEPT"),
            "biology": ("people_education", "BIO-CELL"),
            "history": ("unified", "HIS-CHINA-ANCIENT"),
            "geography": ("people_education", "GEO-PHYSICAL"),
            "ideology_politics": ("unified", "POL-SOCIALISM"),
            "technology": ("school_confirmed", "IT-DATA"),
        }
        selections = {
            "history": ["history", "chemistry", "biology"],
            "geography": ["physics", "geography", "chemistry"],
            "ideology_politics": ["physics", "ideology_politics", "chemistry"],
            "technology": ["physics", "chemistry", "technology"],
        }
        for subject, (edition, progress) in cases.items():
            with self.subTest(subject=subject):
                is_technology = subject == "technology"
                selected = selections.get(subject, ["physics", "chemistry", "biology"])
                profile = StudentAcademicProfile.model_validate(
                    {
                        "student_id": f"{subject}_student",
                        "grade": "grade_11",
                        "school_term": "grade_11_term_1",
                        "province_code": "33" if is_technology else "43",
                        "school_entry_year": 2024,
                        "target_exam_year": 2027,
                        "curriculum_versions": {subject: edition},
                        "selected_subjects": selected,
                        "subject_selection_confirmed": True,
                        "class_progress": {subject: progress},
                    }
                )
                service.validate_student_profile(profile)


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
