"""Rule-based path, task, scheduling, validation and versioning engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from ai_education.core.errors import InputValidationError, PlanValidationError
from ai_education.domain.enums import AdjustmentLevel, Grade, PlanStatus, Subject
from ai_education.domain.models import (
    CompletionRule,
    ExamProfile,
    KnowledgeProfile,
    LearningGoal,
    LearningPlan,
    PlanStage,
    PlanTask,
    PlanValidation,
    StudentAcademicProfile,
    TimeProfile,
)
from ai_education.repositories import PlannerRepository


class PlanService:
    def __init__(self, repository: PlannerRepository) -> None:
        self.repository = repository

    def generate(
        self,
        student: StudentAcademicProfile,
        exam_profile: ExamProfile,
        goals: list[LearningGoal],
        knowledge: KnowledgeProfile,
        time_profile: TimeProfile,
        *,
        plan_start: date | None = None,
    ) -> LearningPlan:
        start = plan_start or date.today() + timedelta(days=1)
        goal_end = min(goal.deadline for goal in goals)
        stage_end = min(goal_end, start + timedelta(days=27))
        stage_name, objective = self._stage_definition(student.grade)
        stage = PlanStage(
            name=stage_name,
            start_date=start,
            end_date=stage_end,
            objective=objective,
            completion_conditions={
                "minimum_completion_rate": 0.85,
                "minimum_core_mastery": 0.70,
                "assessment_required": True,
                "high_risk_prerequisite_gap_allowed": False,
            },
        )
        plan_id = f"plan_{uuid4().hex[:12]}"
        candidates = self._candidate_tasks(plan_id, stage.stage_id, goals, knowledge, time_profile)
        tasks = self._schedule(candidates, time_profile, start, stage_end, student.timezone)
        scheduled = sum(task.planned_duration_minutes for task in tasks)
        plan = LearningPlan(
            plan_id=plan_id,
            student_id=student.student_id,
            goal_ids=[goal.goal_id for goal in goals],
            status=PlanStatus.DRAFT,
            plan_start=start,
            plan_end=goal_end,
            exam_profile_id=exam_profile.exam_profile_id,
            stages=[stage],
            tasks=tasks,
            weekly_capacity_minutes=time_profile.weekly_effective_minutes,
            scheduled_minutes=scheduled,
            buffer_minutes=time_profile.buffer_minutes,
            subject_time_budgets=time_profile.subject_budgets,
            generation_basis={
                "knowledge_profile_version": str(knowledge.profile_version),
                "time_profile_version": str(time_profile.version),
                "goal_version": ",".join(str(goal.version) for goal in goals),
                "policy_version": exam_profile.policy_version,
                "algorithm_version": "planner_rule_v1",
            },
        )
        validation = self.validate(plan, student, exam_profile, knowledge, time_profile)
        plan.validation = validation
        plan.explanations = self.explain(plan, goals, knowledge, validation)
        if validation.valid:
            plan.status = PlanStatus.WAITING_FOR_CONFIRMATION
        return self.repository.save_plan(plan)

    def validate(
        self,
        plan: LearningPlan,
        student: StudentAcademicProfile,
        exam_profile: ExamProfile,
        knowledge: KnowledgeProfile,
        time_profile: TimeProfile,
    ) -> PlanValidation:
        scheduled = sum(task.planned_duration_minutes for task in plan.tasks)
        task_ids = {task.task_id for task in plan.tasks}
        by_id = {task.task_id: task for task in plan.tasks}
        checks = {
            "policy_current": exam_profile.is_current,
            "exam_profile_match": plan.exam_profile_id == exam_profile.exam_profile_id,
            "capacity_within_limit": scheduled <= time_profile.recommended_scheduled_minutes,
            "subject_budgets_respected": self._subject_budgets_respected(
                plan.tasks, time_profile.subject_budgets
            ),
            "buffer_reserved": plan.buffer_minutes >= 0
            and scheduled + plan.buffer_minutes <= plan.weekly_capacity_minutes,
            "focus_limit": all(
                task.planned_duration_minutes <= time_profile.max_focus_minutes
                for task in plan.tasks
            ),
            "content_available": all(bool(task.content_ids) for task in plan.tasks),
            "dates_valid": all(
                plan.plan_start <= task.planned_start.date() <= plan.plan_end for task in plan.tasks
            ),
            "prerequisites_ordered": all(
                prerequisite in task_ids and by_id[prerequisite].planned_start < task.planned_start
                for task in plan.tasks
                for prerequisite in task.prerequisite_task_ids
            ),
            "target_gap_coverage": all(
                any(gap in task.knowledge_ids for task in plan.tasks)
                for gap in knowledge.priority_gaps[: min(5, len(knowledge.priority_gaps))]
            ),
            "spaced_review_included": any(task.task_type == "spaced_review" for task in plan.tasks),
            "timed_training_included": any(
                task.task_type == "timed_training" for task in plan.tasks
            ),
            "assessment_included": any(task.task_type == "stage_assessment" for task in plan.tasks),
            "subject_selection_legal": self._selection_legal(student, exam_profile),
        }
        errors = [name for name, passed in checks.items() if not passed]
        warnings = []
        if knowledge.assessment_quality.get("confidence", 0) < 0.8:
            warnings.append("知识画像置信度低于 0.80，计划需在诊断后复核")
        if not plan.tasks:
            errors.append("没有可排期任务")
        return PlanValidation(valid=not errors, checks=checks, errors=errors, warnings=warnings)

    def confirm(self, plan_id: str, *, expected_version: int) -> LearningPlan:
        current = self.repository.get_plan(plan_id)
        if not current:
            raise InputValidationError("计划不存在")
        if current.version != expected_version:
            raise PlanValidationError("计划版本已变化，请读取最新版本后重试")
        if not current.validation or not current.validation.valid:
            raise PlanValidationError("计划未通过校验，禁止发布")
        published = current.model_copy(deep=True)
        published.version += 1
        published.supersedes_version = current.version
        published.status = PlanStatus.ACTIVE
        return self.repository.save_plan(published)

    def revise(
        self,
        plan_id: str,
        level: AdjustmentLevel,
        *,
        reason: str,
    ) -> LearningPlan:
        current = self.repository.get_plan(plan_id)
        if not current:
            raise InputValidationError("计划不存在")
        revised = current.model_copy(deep=True)
        revised.version += 1
        revised.supersedes_version = current.version
        revised.status = PlanStatus.WAITING_FOR_CONFIRMATION
        shift_days = 1 if level in {AdjustmentLevel.DAILY_SHIFT, AdjustmentLevel.TASK_SWAP} else 2
        if level != AdjustmentLevel.TASK_SWAP:
            movable = [
                task
                for task in revised.tasks
                if task.flexibility != "fixed" and task.status == "scheduled"
            ]
            for task in movable[max(len(movable) // 2, 1) :]:
                task.planned_start += timedelta(days=shift_days)
        revised.explanations["adjustment"] = f"调整级别：{level.value}；原因：{reason}"
        return self.repository.save_plan(revised)

    def adjustment_level(self, metrics: dict[str, float | int | bool]) -> AdjustmentLevel | None:
        if metrics.get("subject_selection_changed") or metrics.get("goal_changed"):
            return AdjustmentLevel.FULL_REPLAN
        if float(metrics.get("weekly_capacity_change_rate", 0)) > 0.20:
            return AdjustmentLevel.WEEKLY_REPLAN
        if (
            int(metrics.get("consecutive_missed_days", 0)) >= 3
            or float(metrics.get("weekly_completion_rate", 1)) < 0.70
        ):
            return AdjustmentLevel.WEEKLY_REPLAN
        if (
            float(metrics.get("critical_mastery_drop", 0)) > 0.10
            and int(metrics.get("independent_evidence_count", 0)) >= 2
        ):
            return AdjustmentLevel.STAGE_REPLAN
        if metrics.get("resource_mismatch"):
            return AdjustmentLevel.TASK_SWAP
        if metrics.get("tomorrow_capacity_changed"):
            return AdjustmentLevel.DAILY_SHIFT
        return None

    def explain(
        self,
        plan: LearningPlan,
        goals: list[LearningGoal],
        knowledge: KnowledgeProfile,
        validation: PlanValidation,
    ) -> dict[str, str]:
        primary = goals[0]
        subject = primary.subject.value if primary.subject else "总分"
        gaps = "、".join(knowledge.priority_gaps[:3]) or "待诊断知识范围"
        student = (
            f"当前首要目标是 {subject} 在 {primary.deadline.isoformat()} 前达到 "
            f"{primary.target.target_value:g} 分。先处理 {gaps}，因为它们是现有证据中"
            f"掌握度较低且影响目标的内容。本周安排 {plan.scheduled_minutes} 分钟，"
            f"保留 {plan.buffer_minutes} 分钟弹性。每项任务均给出完成题量、正确率和提示依赖标准。"
            "若连续未完成、掌握度明显变化、考试或可用时间变化，系统将按任务、日、周或阶段级调整。"
        )
        teacher = (
            f"考试配置 {plan.exam_profile_id}；政策版本 {plan.generation_basis['policy_version']}；"
            f"知识画像版本 {plan.generation_basis['knowledge_profile_version']}；"
            f"时间画像版本 {plan.generation_basis['time_profile_version']}；"
            f"重点缺口 {gaps}；学科预算 {plan.subject_time_budgets}；"
            f"计划校验 {'通过' if validation.valid else '未通过'}，"
            f"算法 {plan.generation_basis['algorithm_version']}。"
        )
        return {"student": student, "teacher": teacher}

    def _candidate_tasks(
        self,
        plan_id: str,
        stage_id: str,
        goals: list[LearningGoal],
        knowledge: KnowledgeProfile,
        time_profile: TimeProfile,
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        goal_ids = [goal.goal_id for goal in goals]
        ordered = sorted(
            knowledge.knowledge_states,
            key=lambda state: (state.mastery_probability, -state.forgetting_risk),
        )
        goal_subject = ordered[0].subject if ordered else None
        subject_budget = (
            time_profile.subject_budgets.get(goal_subject.value, 0) if goal_subject else 0
        )
        remediation_duration = min(time_profile.max_focus_minutes, 30)
        reserved_duration = sum(
            min(duration, time_profile.max_focus_minutes) for duration in (20, 25, 35)
        )
        primary_slots = max((subject_budget - reserved_duration) // remediation_duration, 1)
        for state in ordered[:primary_slots]:
            if state.mastery_probability >= 0.85:
                task_type, difficulty = "spaced_review", 0.70
            elif state.mastery_probability >= 0.70:
                task_type, difficulty = "timed_training", 0.72
            elif state.mastery_probability >= 0.50:
                task_type, difficulty = "variant_practice", 0.60
            elif state.mastery_probability >= 0.30:
                task_type, difficulty = "foundation_practice", 0.42
            else:
                task_type, difficulty = "concept_learning", 0.25
            duration = remediation_duration
            candidates.append(
                {
                    "plan_id": plan_id,
                    "stage_id": stage_id,
                    "subject": state.subject,
                    "task_type": task_type,
                    "knowledge_ids": [state.knowledge_id],
                    "duration": duration,
                    "difficulty": difficulty,
                    "exam_relevance": 0.85,
                    "goal_ids": goal_ids,
                    "rationale": (
                        f"当前掌握度 {state.mastery_probability:.2f}，按阈值安排 {task_type}"
                    ),
                }
            )
        if ordered:
            key_ids = [state.knowledge_id for state in ordered[:5]]
            candidates.extend(
                [
                    {
                        "plan_id": plan_id,
                        "stage_id": stage_id,
                        "subject": ordered[0].subject,
                        "task_type": "spaced_review",
                        "knowledge_ids": key_ids,
                        "duration": min(20, time_profile.max_focus_minutes),
                        "difficulty": 0.55,
                        "exam_relevance": 0.75,
                        "goal_ids": goal_ids,
                        "rationale": "按遗忘风险插入关键知识间隔复习",
                    },
                    {
                        "plan_id": plan_id,
                        "stage_id": stage_id,
                        "subject": ordered[0].subject,
                        "task_type": "timed_training",
                        "knowledge_ids": key_ids,
                        "duration": min(25, time_profile.max_focus_minutes),
                        "difficulty": 0.62,
                        "exam_relevance": 0.90,
                        "goal_ids": goal_ids,
                        "rationale": "建立考试时间分配与稳定性证据",
                    },
                ]
            )
            candidates.append(
                {
                    "plan_id": plan_id,
                    "stage_id": stage_id,
                    "subject": ordered[0].subject,
                    "task_type": "stage_assessment",
                    "knowledge_ids": key_ids,
                    "duration": min(35, time_profile.max_focus_minutes),
                    "difficulty": 0.65,
                    "exam_relevance": 0.95,
                    "goal_ids": goal_ids,
                    "rationale": "验证阶段知识目标并为下一版本提供独立证据",
                }
            )
        return candidates

    def _schedule(
        self,
        candidates: list[dict[str, object]],
        time_profile: TimeProfile,
        start: date,
        end: date,
        timezone: str,
    ) -> list[PlanTask]:
        daily_template = {item.weekday: item for item in time_profile.daily_capacity}
        used: defaultdict[date, int] = defaultdict(int)
        subject_used: defaultdict[str, int] = defaultdict(int)
        tasks: list[PlanTask] = []
        cursor = start
        for candidate in candidates:
            duration = int(candidate["duration"])
            candidate_subject = Subject(candidate["subject"])
            subject_budget = time_profile.subject_budgets.get(candidate_subject.value, 0)
            if subject_used[candidate_subject.value] + duration > subject_budget:
                continue
            attempts = 0
            while attempts <= 7:
                template = daily_template.get(cursor.isoweekday())
                if template and used[cursor] + duration <= template.available_minutes:
                    break
                cursor += timedelta(days=1)
                attempts += 1
            if cursor > min(end, start + timedelta(days=6)) or attempts > 7:
                break
            period = daily_template[cursor.isoweekday()].preferred_period
            hour = {"morning": 6, "noon": 12, "evening": 19, "flexible": 19}[period]
            planned_start = datetime.combine(cursor, time(hour, 0), ZoneInfo(timezone)) + timedelta(
                minutes=used[cursor]
            )
            task_type = str(candidate["task_type"])
            knowledge_ids = list(candidate["knowledge_ids"])
            subject = Subject(candidate["subject"])
            tasks.append(
                PlanTask(
                    plan_id=str(candidate["plan_id"]),
                    stage_id=str(candidate["stage_id"]),
                    subject=subject,
                    task_type=task_type,
                    knowledge_ids=knowledge_ids,
                    content_ids=[f"curated:{subject.value}:{knowledge_ids[0]}:{task_type}"],
                    planned_start=planned_start,
                    planned_duration_minutes=duration,
                    difficulty=float(candidate["difficulty"]),
                    exam_relevance=float(candidate["exam_relevance"]),
                    completion_rule=CompletionRule(
                        minimum_item_count=0 if "learning" in task_type else 5,
                        minimum_accuracy=0.70 if "assessment" not in task_type else 0.75,
                        maximum_hint_dependency=0.30,
                    ),
                    rationale=str(candidate["rationale"]),
                    goal_ids=list(candidate["goal_ids"]),
                )
            )
            used[cursor] += duration
            subject_used[subject.value] += duration
        return tasks

    @staticmethod
    def _stage_definition(grade: Grade) -> tuple[str, str]:
        if grade == Grade.GRADE_10:
            return "校内同步与单元闭环", "适应高中课程、夯实基础并识别选科倾向"
        if grade == Grade.GRADE_11:
            return "同步学习与专题提升", "完成核心课程并修复高一遗留漏洞"
        return "高三阶段复习", "稳定基础和中档题，结合专题、限时训练与阶段测评"

    @staticmethod
    def _selection_legal(student: StudentAcademicProfile, profile: ExamProfile) -> bool:
        if not student.subject_selection_confirmed:
            return student.grade == Grade.GRADE_10
        selected = set(student.selected_subjects)
        return (
            len(selected) == 3
            and len(selected.intersection(profile.first_choice_subjects)) == 1
            and len(selected.intersection(profile.second_choice_subjects)) == 2
        )

    @staticmethod
    def _subject_budgets_respected(tasks: list[PlanTask], subject_budgets: dict[str, int]) -> bool:
        used: defaultdict[str, int] = defaultdict(int)
        for task in tasks:
            used[task.subject.value] += task.planned_duration_minutes
        return all(minutes <= subject_budgets.get(subject, 0) for subject, minutes in used.items())
