"""Minimal-information onboarding session workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.domain.models import OnboardingSession
from ai_education.repositories import PlannerRepository

QUESTION_ORDER: tuple[tuple[str, str], ...] = (
    ("grade", "你目前是高一、高二还是高三？"),
    ("school_term", "你当前处于哪个学期？"),
    ("province_code", "你所在省份的行政区划代码是什么？"),
    ("school_entry_year", "你的高中入学年份是什么？"),
    ("expected_gaokao_year", "预计参加高考的年份是什么？"),
    ("subject_selection", "请确认选科组合；高一未确定时请填写选科意向。"),
    ("curriculum_versions", "请提供主要科目的教材版本和学校教学进度。"),
    ("goal_text", "你最希望提升哪一科，准备哪次考试？"),
    ("current_level", "最近成绩或当前大致水平是多少？"),
    ("weekly_availability", "每周可安排多少自主学习时间？"),
    ("evidence_choice", "请选择读取历史数据、上传试卷、诊断测评或自我评估。"),
)


class OnboardingService:
    def __init__(self, repository: PlannerRepository) -> None:
        self.repository = repository

    def create(self, student_id: str) -> OnboardingSession:
        return self.repository.save_onboarding(OnboardingSession(student_id=student_id))

    def next_questions(self, onboarding_id: str) -> list[dict[str, str]]:
        session = self.repository.get_onboarding(onboarding_id)
        if not session:
            raise InputValidationError("首次使用会话不存在")
        missing = [item for item in QUESTION_ORDER if item[0] not in session.answers]
        return [{"field": field, "question": question} for field, question in missing[:2]]

    def submit_answers(self, onboarding_id: str, answers: dict[str, Any]) -> OnboardingSession:
        session = self.repository.get_onboarding(onboarding_id)
        if not session:
            raise InputValidationError("首次使用会话不存在")
        if not answers:
            raise InputValidationError("答案不能为空")
        session.answers.update(answers)
        session.updated_at = datetime.now().astimezone()
        session.data_version += 1
        session.status = self._derive_status(session)
        return self.repository.save_onboarding(session)

    def confirm_exam_profile(self, onboarding_id: str, exam_profile_id: str) -> OnboardingSession:
        session = self.repository.get_onboarding(onboarding_id)
        if not session:
            raise InputValidationError("首次使用会话不存在")
        session.confirmed_exam_profile_id = exam_profile_id
        session.status = "POLICY_RESOLVED"
        session.data_version += 1
        session.updated_at = datetime.now().astimezone()
        return self.repository.save_onboarding(session)

    def completeness(self, answers: dict[str, Any]) -> float:
        components = {
            "exam": (0.20, all(k in answers for k in ("province_code", "expected_gaokao_year"))),
            "goal": (0.20, "goal_text" in answers),
            "knowledge": (
                0.25,
                any(k in answers for k in ("current_level", "history", "diagnostic")),
            ),
            "time": (0.20, "weekly_availability" in answers),
            "progress": (0.10, "curriculum_versions" in answers),
            "preference": (0.05, "learning_preference" in answers),
        }
        return round(sum(weight for weight, complete in components.values() if complete), 2)

    def _derive_status(self, session: OnboardingSession) -> str:
        if self.completeness(session.answers) >= 0.75:
            return "SUMMARY_CONFIRMATION"
        if all(field in session.answers for field, _ in QUESTION_ORDER):
            return "SUMMARY_CONFIRMATION"
        return "GOAL_COLLECTING" if "goal_text" not in session.answers else "HISTORY_CHECKING"
