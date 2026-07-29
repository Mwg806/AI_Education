"""Configuration-driven exam-policy resolution and validation."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from ai_education.core.errors import PolicyConflictError, PolicyUnavailableError
from ai_education.domain.models import ExamProfile, StudentAcademicProfile


class ExamPolicyService:
    """Resolve policy facts from a versioned configuration, never from a prompt."""

    def __init__(self, policies: list[dict[str, Any]] | None = None) -> None:
        if policies is None:
            resource = files("ai_education").joinpath("resources/exam_policies.json")
            policies = json.loads(resource.read_text(encoding="utf-8"))["policies"]
        self._profiles = [ExamProfile.model_validate(item) for item in policies]

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
        if match is None:
            raise PolicyUnavailableError(
                "未找到经核验的省级考试政策，禁止生成正式高考计划",
                details={
                    "province_code": province_code,
                    "school_entry_year": school_entry_year,
                    "expected_gaokao_year": expected_gaokao_year,
                },
            )
        return match.model_copy(deep=True)

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
        if student_profile.subject_selection_confirmed:
            first_count = len(selected.intersection(exam_profile.first_choice_subjects))
            second_count = len(selected.intersection(exam_profile.second_choice_subjects))
            if first_count != 1 or second_count != 2 or len(selected) != 3:
                errors.append("选科组合必须包含一门首选科目和两门再选科目")
        if errors:
            raise PolicyConflictError("考试配置校验失败", details={"errors": errors})
        return errors
