"""Goal parsing, clarification, decomposition, feasibility and conflict rules."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ai_education.domain.enums import Subject
from ai_education.domain.models import GoalParseResult, LearningGoal

SUBJECT_ALIASES: dict[str, Subject] = {
    "语文": Subject.CHINESE,
    "数学": Subject.MATHEMATICS,
    "英语": Subject.FOREIGN_LANGUAGE,
    "外语": Subject.FOREIGN_LANGUAGE,
    "物理": Subject.PHYSICS,
    "历史": Subject.HISTORY,
    "政治": Subject.IDEOLOGY_POLITICS,
    "思想政治": Subject.IDEOLOGY_POLITICS,
    "地理": Subject.GEOGRAPHY,
    "化学": Subject.CHEMISTRY,
    "生物": Subject.BIOLOGY,
}


class GoalService:
    """Deterministic goal harness; an optional LLM may enrich, never invent, facts."""

    def parse(
        self,
        text: str,
        *,
        explicit_deadline: date | None = None,
        exam_milestones: dict[str, date] | None = None,
    ) -> GoalParseResult:
        subject = next((value for alias, value in SUBJECT_ALIASES.items() if alias in text), None)
        scores = [float(item) for item in re.findall(r"(\d{2,3}(?:\.\d+)?)\s*分", text)]
        target_match = re.search(r"(?:达到|考到|提高到|目标(?:是|为)?)\s*(\d{2,3}(?:\.\d+)?)", text)
        target = float(target_match.group(1)) if target_match else (scores[-1] if scores else None)
        current = scores[0] if len(scores) >= 2 else None
        daily_match = re.search(
            r"每天(?:最多|大约|可用)?\s*(\d+(?:\.\d+)?)\s*(个?半?小时|分钟)", text
        )
        daily_minutes: int | None = None
        if daily_match:
            value = float(daily_match.group(1))
            daily_minutes = round(value * 60) if "小时" in daily_match.group(2) else round(value)
        event_aliases = {
            "一模": "grade_12_first_mock",
            "二模": "grade_12_second_mock",
            "三模": "grade_12_third_mock",
            "高考": "gaokao",
            "期中": "midterm",
            "期末": "final_exam",
            "月考": "monthly_exam",
        }
        deadline_event = next(
            (event for alias, event in event_aliases.items() if alias in text), None
        )
        deadline = explicit_deadline
        if not deadline and deadline_event and exam_milestones:
            deadline = exam_milestones.get(deadline_event)
        missing: list[str] = []
        if subject is None:
            missing.append("subject")
        if current is None:
            missing.append("current_value")
        if target is None:
            missing.append("target_value")
        if deadline is None:
            missing.append("deadline")
        confidence = {
            "subject": 0.99 if subject else 0.0,
            "current_value": 0.95 if current is not None else 0.0,
            "target_value": 0.98 if target is not None else 0.0,
            "deadline": 1.0 if explicit_deadline else (0.9 if deadline else 0.0),
        }
        goal_type = (
            "mock_exam_subject_score" if deadline_event and "mock" in deadline_event else None
        )
        if deadline_event == "gaokao":
            goal_type = "gaokao_subject_score"
        return GoalParseResult(
            goal_type=goal_type or ("subject_score" if subject else None),
            subject=subject,
            current_value=current,
            target_value=target,
            deadline=deadline,
            deadline_event=deadline_event,
            daily_time_limit_minutes=daily_minutes,
            missing_fields=missing,
            field_confidence=confidence,
            raw_text=text,
        )

    def clarification_questions(self, parsed: GoalParseResult) -> list[dict[str, Any]]:
        questions = {
            "target_value": {"field": "target_value", "type": "number", "text": "希望达到多少分？"},
            "deadline": {
                "field": "deadline",
                "type": "date",
                "text": "目标考试或截止日期是什么时候？",
            },
            "current_value": {
                "field": "current_value",
                "type": "number",
                "text": "最近一次成绩大约是多少？",
            },
            "subject": {"field": "subject", "type": "single_choice", "text": "最希望提升哪一科？"},
        }
        priority = ("target_value", "deadline", "current_value", "subject")
        return [questions[field] for field in priority if field in parsed.missing_fields][:2]

    def decompose(self, goal: LearningGoal) -> dict[str, Any]:
        subject = goal.subject.value if goal.subject else "total"
        return {
            "result_goal": {
                "metric": goal.target.metric,
                "current": goal.target.current_value,
                "target": goal.target.target_value,
                "deadline": goal.deadline.isoformat(),
            },
            "competency_goals": [
                {"subject": subject, "target_mastery": 0.80, "source_goal_id": goal.goal_id}
            ],
            "exam_skill_goals": [{"metric": "time_allocation_stability", "target": 0.80}],
            "process_goals": [
                {"metric": "weekly_plan_completion_rate", "target": 0.85},
                {"metric": "wrong_answer_recovery_rate", "target": 0.80},
            ],
        }

    def feasibility(self, inputs: dict[str, float]) -> dict[str, Any]:
        weights = {
            "time_sufficiency": 0.25,
            "foundation_match": 0.25,
            "historical_improvement": 0.20,
            "target_increment_reasonableness": 0.15,
            "execution_stability": 0.10,
            "resource_availability": 0.05,
        }
        components = {key: min(max(float(inputs.get(key, 0.5)), 0), 1) for key in weights}
        score = round(sum(components[key] * weight for key, weight in weights.items()), 3)
        level = (
            "feasible"
            if score >= 0.75
            else "challenging_but_possible"
            if score >= 0.5
            else "high_risk"
        )
        recommendations = []
        if level != "feasible":
            recommendations.extend(["优先修复高影响知识缺口", "保留周缓冲并在阶段测评后复核目标"])
        if components["time_sufficiency"] < 0.6:
            recommendations.append("增加周有效学习时间或延长截止期限")
        return {
            "score": score,
            "level": level,
            "components": components,
            "recommendations": recommendations,
        }

    def conflicts(
        self,
        goal: LearningGoal,
        *,
        selected_subjects: set[Subject],
        compulsory_subjects: set[Subject],
        required_minutes: int,
        available_minutes: int,
    ) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        if goal.subject and goal.subject not in selected_subjects | compulsory_subjects:
            conflicts.append(
                {"code": "SUBJECT_SELECTION_CONFLICT", "message": "目标科目不在已确认考试科目中"}
            )
        if required_minutes > available_minutes:
            conflicts.append(
                {"code": "TIME_CAPACITY_CONFLICT", "message": "目标所需时间超过有效容量"}
            )
        return conflicts
