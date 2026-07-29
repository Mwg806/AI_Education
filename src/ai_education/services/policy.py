"""Configuration-driven exam-policy resolution and validation."""

from __future__ import annotations

import json
from datetime import date
from importlib.resources import files
from typing import Any

from ai_education.core.errors import PolicyConflictError
from ai_education.domain.models import ExamProfile, StudentAcademicProfile
from ai_education.services.curriculum_catalog import CurriculumCatalogService

SUBJECT_ALIASES = {
    "politics": "ideology_politics",
    "technology": "technology",
}


class ExamPolicyService:
    """Resolve policy facts from a versioned configuration, never from a prompt."""

    def __init__(
        self,
        policies: list[dict[str, Any]] | None = None,
        catalog: CurriculumCatalogService | None = None,
    ) -> None:
        if policies is None:
            resource = files("ai_education").joinpath("resources/exam_policies.json")
            policies = json.loads(resource.read_text(encoding="utf-8"))["policies"]
        self._profiles = [ExamProfile.model_validate(item) for item in policies]
        self.catalog = catalog or CurriculumCatalogService()

    def resolve(
        self,
        province_code: str,
        school_entry_year: int,
        expected_gaokao_year: int,
    ) -> ExamProfile:
        match = next(
            (
                profile
                for profile in self._profiles
                if profile.province_code == province_code
                and profile.cohort_entry_year == school_entry_year
                and profile.exam_year == expected_gaokao_year
            ),
            None,
        )
        if match is not None:
            return match.model_copy(deep=True)
        route = self.catalog.province_route(province_code)
        return self._profile_from_route(route, school_entry_year, expected_gaokao_year)

    def _profile_from_route(
        self, route: dict[str, Any], school_entry_year: int, exam_year: int
    ) -> ExamProfile:
        def subjects(values: list[str]) -> list[str]:
            return [SUBJECT_ALIASES.get(value, value) for value in values]

        first = subjects(route.get("first_choice_subjects", []))
        second = subjects(route.get("second_choice_subjects", []))
        elective = subjects(route.get("elective_subjects", first + second))
        all_scored = ["chinese", "mathematics", "foreign_language", *elective, *first, *second]
        score_rules = {
            subject: "raw_score"
            if subject in {"chinese", "mathematics", "foreign_language"}
            else "province_configured"
            for subject in dict.fromkeys(all_scored)
        }
        basis_year = self.catalog.scope_year
        return ExamProfile.model_validate(
            {
                "exam_profile_id": (f"NEW_GAOKAO_NATIONAL_I_{exam_year}_{route['slug'].upper()}"),
                "province_code": route["code"],
                "cohort_entry_year": school_entry_year,
                "exam_year": exam_year,
                "subject_model": route["exam_mode"].replace("+", "_plus_"),
                "compulsory_subjects": ["chinese", "mathematics", "foreign_language"],
                "first_choice_subjects": first,
                "second_choice_subjects": second,
                "elective_subjects": elective,
                "score_rules": score_rules,
                "policy_version": f"national_i_scope_{basis_year}_07_{route['slug']}",
                "effective_date": date(basis_year, 7, 1),
                "expires_at": None,
                "status": "active",
                "route_basis_year": basis_year,
                "source_urls": [route["official_url"]],
                "requires_annual_reconfirmation": exam_year != basis_year,
                "verification_note": (
                    f"按{basis_year}年知识库范围配置；{exam_year}年组卷与计分细则须以当年考试院通知复核"
                ),
            }
        )

    def validate(
        self,
        exam_profile: ExamProfile,
        student_profile: StudentAcademicProfile,
    ) -> list[str]:
        errors: list[str] = []
        if not exam_profile.is_current:
            errors.append("考试政策已过期或未激活")
        if student_profile.province_code != exam_profile.province_code:
            errors.append("学生省份与考试政策不一致")
        selected = set(student_profile.selected_subjects)
        if (
            student_profile.subject_selection_confirmed
            and exam_profile.subject_model == "3_plus_1_plus_2"
        ):
            first_count = len(selected.intersection(exam_profile.first_choice_subjects))
            second_count = len(selected.intersection(exam_profile.second_choice_subjects))
            if first_count != 1 or second_count != 2 or len(selected) != 3:
                errors.append("选科组合必须包含一门首选科目和两门再选科目")
        elif (
            student_profile.subject_selection_confirmed and exam_profile.subject_model == "3_plus_3"
        ):
            allowed = set(exam_profile.elective_subjects)
            if len(selected) != 3 or not selected.issubset(allowed):
                errors.append("3+3选科必须从本省已配置的选考科目中选择三门")
        if errors:
            raise PolicyConflictError("考试配置校验失败", details={"errors": errors})
        return errors
