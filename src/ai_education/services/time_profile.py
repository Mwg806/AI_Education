"""Time capacity, efficiency, subject budget and elastic buffer modeling."""

from __future__ import annotations

from ai_education.domain.enums import Grade, Subject
from ai_education.domain.models import DailyAvailability, TimeProfile


class TimeProfileService:
    def build(
        self,
        student_id: str,
        grade: Grade,
        daily_capacity: list[DailyAvailability],
        subjects: list[Subject],
        subject_factors: dict[str, dict[str, float]],
        *,
        efficiency_factor: float = 0.9,
        execution_reliability: float = 0.9,
        max_focus_minutes: int = 45,
        new_plan: bool = True,
    ) -> TimeProfile:
        natural = sum(day.available_minutes for day in daily_capacity)
        effective = round(
            sum(
                day.available_minutes
                * day.energy_coefficient
                * efficiency_factor
                * execution_reliability
                for day in daily_capacity
            )
            - max(len(daily_capacity) - 1, 0) * 5
        )
        effective = max(effective, 0)
        buffer_ratio = 0.22 if new_plan else 0.18 if grade != Grade.GRADE_12 else 0.15
        buffer = round(effective * buffer_ratio)
        scheduled = effective - buffer
        budgets = self.allocate_subject_budgets(subjects, subject_factors, scheduled)
        return TimeProfile(
            student_id=student_id,
            weekly_natural_minutes=natural,
            weekly_effective_minutes=effective,
            recommended_scheduled_minutes=scheduled,
            buffer_minutes=buffer,
            subject_budgets=budgets,
            daily_capacity=daily_capacity,
            efficiency_by_task_type={"default": efficiency_factor},
            max_focus_minutes=max_focus_minutes,
        )

    def allocate_subject_budgets(
        self,
        subjects: list[Subject],
        factors: dict[str, dict[str, float]],
        scheduled_minutes: int,
    ) -> dict[str, int]:
        unique = list(dict.fromkeys(subjects))
        raw: dict[str, float] = {}
        for subject in unique:
            values = factors.get(subject.value, {})
            raw[subject.value] = (
                max(values.get("goal_priority", 0.5), 0.05)
                * max(values.get("score_gap", 0.5), 0.05)
                * max(values.get("expected_score_gain", 0.5), 0.05)
                * max(values.get("urgency", 0.5), 0.05)
                * max(values.get("knowledge_dependency", 0.5), 0.05)
            )
        if not raw:
            return {}
        minimum = min(30, scheduled_minutes // len(raw))
        remaining = max(scheduled_minutes - minimum * len(raw), 0)
        total = sum(raw.values())
        budgets = {key: minimum + int(remaining * value / total) for key, value in raw.items()}
        unallocated = scheduled_minutes - sum(budgets.values())
        for key in sorted(budgets, key=lambda item: raw[item], reverse=True)[:unallocated]:
            budgets[key] += 1
        return budgets
