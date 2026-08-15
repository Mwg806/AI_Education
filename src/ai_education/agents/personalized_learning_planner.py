"""LangGraph implementation of the personalized learning planner agent."""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.config import Settings
from ai_education.core.errors import (
    AIEducationError,
    InputValidationError,
    PlannerModelUnavailableError,
    PolicyConflictError,
    PolicyUnavailableError,
)
from ai_education.domain.enums import (
    AdjustmentLevel,
    AgentLifecycleStatus,
    AgentRole,
    MessageType,
    StandardStatus,
    Subject,
)
from ai_education.domain.models import (
    DailyAvailability,
    GoalTarget,
    LearningGoal,
    PracticeEvent,
    StudentAcademicProfile,
)
from ai_education.domain.protocols import (
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ErrorDetail,
    Evidence,
    WarningDetail,
)
from ai_education.llm.factory import create_chat_model
from ai_education.llm.goal_interpreter import StructuredGoalInterpreter
from ai_education.llm.plan_narrator import StructuredPlanNarrator
from ai_education.repositories import PlannerRepository
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from ai_education.services.goal import GoalService
from ai_education.services.knowledge import KnowledgeService
from ai_education.services.plan import PlanService
from ai_education.services.policy import ExamPolicyService
from ai_education.services.practice import PracticeService
from ai_education.services.time_profile import TimeProfileService
from ai_education.tools.planner import PlannerToolbox


class PlannerState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    lifecycle_status: str
    response_status: str
    student: dict[str, Any]
    exam_profile: dict[str, Any]
    goal_parse: dict[str, Any]
    goals: list[dict[str, Any]]
    knowledge_profile: dict[str, Any]
    knowledge_profiles_by_subject: dict[str, dict[str, Any]]
    time_profile: dict[str, Any]
    plan: dict[str, Any]
    result: dict[str, Any]
    evidence: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    next_node: str


class PersonalizedLearningPlannerAgent(BaseEducationAgent):
    """First production-shaped education agent and future-agent reference implementation."""

    def __init__(
        self,
        repository: PlannerRepository | None = None,
        settings: Settings | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.repository = repository or PlannerRepository()
        self.settings = settings or Settings.from_env()
        self.policy_service = ExamPolicyService()
        self.curriculum_catalog = CurriculumCatalogService()
        self.goal_service = GoalService()
        self.knowledge_service = KnowledgeService()
        self.time_service = TimeProfileService()
        self.practice_service = PracticeService(self.repository)
        self.plan_service = PlanService(self.repository)
        chat_model = chat_model if chat_model is not None else create_chat_model(self.settings)
        self.goal_interpreter = StructuredGoalInterpreter(chat_model)
        self.plan_narrator = StructuredPlanNarrator(chat_model)
        self.toolbox = PlannerToolbox(
            self.policy_service,
            self.goal_service,
            self.knowledge_service,
            self.time_service,
            self.practice_service,
            self.plan_service,
        )
        self.langchain_tools = self.toolbox.as_langchain_tools()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="personalized_learning_planner_agent",
            role=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            version="1.0.0",
            description="面向新高考全国Ⅰ卷高中生的长期个性化学习规划智能体",
            capabilities={
                "onboarding",
                "goal_structuring",
                "knowledge_diagnosis",
                "time_capacity_modeling",
                "plan_generation",
                "practice_feedback",
                "dynamic_replanning",
                "cross_agent_diagnosis_handoff",
                "student_teacher_explanation",
            },
            accepted_intents={
                "initialize_plan",
                "practice_event",
                "daily_update",
                "replan",
                "get_plan",
                "confirm_plan",
                "apply_diagnosis_to_plan",
            },
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        cached = self.repository.get_idempotent(request.idempotency_key)
        if cached:
            return AgentResponse.model_validate(cached)
        initial: PlannerState = {
            "request": request.model_dump(mode="json"),
            "intent": request.intent,
            "payload": request.payload,
            "lifecycle_status": AgentLifecycleStatus.NEW,
            "response_status": StandardStatus.SUCCESS,
            "evidence": [],
            "warnings": [],
            "errors": [],
            "result": {},
        }
        try:
            final = await self.graph.ainvoke(initial)
            response = self._to_response(request, final)
        except ValidationError as exc:
            response = self._error_response(
                request,
                status=StandardStatus.NEED_MORE_INFORMATION,
                lifecycle=AgentLifecycleStatus.WAITING_FOR_DATA,
                code="INPUT_VALIDATION_ERROR",
                message="输入未通过结构校验",
                details={
                    "fields": [
                        ".".join(str(part) for part in error["loc"]) for error in exc.errors()
                    ]
                },
            )
        except PolicyUnavailableError as exc:
            response = self._error_response(
                request,
                status=StandardStatus.MANUAL_REVIEW_REQUIRED,
                lifecycle=AgentLifecycleStatus.MANUAL_REVIEW_REQUIRED,
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        except PolicyConflictError as exc:
            response = self._error_response(
                request,
                status=StandardStatus.CONFLICT,
                lifecycle=AgentLifecycleStatus.DATA_CONFLICT_PENDING,
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        except AIEducationError as exc:
            response = self._error_response(
                request,
                status=StandardStatus.FAILED,
                lifecycle=AgentLifecycleStatus.FAILED,
                code=exc.code,
                message=exc.message,
                details=exc.details,
                retryable=exc.retryable,
            )
        except Exception:
            response = self._error_response(
                request,
                status=StandardStatus.FAILED,
                lifecycle=AgentLifecycleStatus.FAILED,
                code="UNEXPECTED_AGENT_ERROR",
                message="智能体执行出现未预期错误，未生成或覆盖任何正式计划",
            )
        if request.idempotency_key:
            self.repository.put_idempotent(
                request.idempotency_key,
                response.model_dump(mode="json"),
            )
        return response

    def _build_graph(self):
        graph = StateGraph(PlannerState)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("policy", self._policy)
        graph.add_node("goal", self._goal)
        graph.add_node("knowledge", self._knowledge)
        graph.add_node("time", self._time)
        graph.add_node("plan", self._plan)
        graph.add_node("practice", self._practice)
        graph.add_node("adjust", self._adjust)
        graph.add_node("get_plan", self._get_plan)
        graph.add_node("apply_diagnosis", self._apply_diagnosis)
        graph.add_node("confirm", self._confirm)
        graph.add_node("unsupported", self._unsupported)
        graph.add_node("finish", lambda state: state)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            lambda state: state["next_node"],
            {
                "policy": "policy",
                "practice": "practice",
                "adjust": "adjust",
                "get_plan": "get_plan",
                "apply_diagnosis": "apply_diagnosis",
                "confirm": "confirm",
                "unsupported": "unsupported",
            },
        )
        graph.add_edge("policy", "goal")
        graph.add_conditional_edges(
            "goal",
            lambda state: state["next_node"],
            {"knowledge": "knowledge", "finish": "finish"},
        )
        graph.add_conditional_edges(
            "knowledge",
            lambda state: state["next_node"],
            {"time": "time", "finish": "finish"},
        )
        graph.add_conditional_edges(
            "time",
            lambda state: state["next_node"],
            {"plan": "plan", "finish": "finish"},
        )
        for node in (
            "plan",
            "practice",
            "adjust",
            "get_plan",
            "apply_diagnosis",
            "confirm",
            "unsupported",
        ):
            graph.add_edge(node, "finish")
        graph.add_edge("finish", END)
        return graph.compile()

    def _dispatch(self, state: PlannerState) -> dict[str, Any]:
        routes = {
            "initialize_plan": "policy",
            "practice_event": "practice",
            "daily_update": "adjust",
            "replan": "adjust",
            "get_plan": "get_plan",
            "apply_diagnosis_to_plan": "apply_diagnosis",
            "confirm_plan": "confirm",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _policy(self, state: PlannerState) -> dict[str, Any]:
        payload = state["payload"]
        if "student_profile" not in payload:
            raise InputValidationError("缺少 student_profile")
        student = StudentAcademicProfile.model_validate(payload["student_profile"])
        self.curriculum_catalog.validate_student_profile(student)
        exam = self.policy_service.resolve(
            student.province_code,
            student.school_entry_year,
            student.target_exam_year,
        )
        self.policy_service.validate(exam, student)
        student.exam_profile_id = exam.exam_profile_id
        self.repository.save_student(student)
        warnings = list(state.get("warnings", []))
        if exam.requires_annual_reconfirmation:
            warnings.append(
                WarningDetail(
                    code="EXAM_YEAR_RECONFIRMATION_REQUIRED",
                    message=exam.verification_note or "目标考试年份政策需按当年官方通知复核",
                    details={
                        "basis_year": exam.route_basis_year,
                        "target_exam_year": exam.exam_year,
                        "source_urls": exam.source_urls,
                    },
                ).model_dump(mode="json")
            )
        return {
            "student": student.model_dump(mode="json"),
            "exam_profile": exam.model_dump(mode="json"),
            "lifecycle_status": AgentLifecycleStatus.GOAL_COLLECTING,
            "warnings": warnings,
            "evidence": [
                Evidence(
                    source_type="exam_policy_config",
                    source_id=exam.policy_version,
                    description="按省份、入学年份和考试年份解析并校验考试配置",
                    confidence=1.0,
                ).model_dump(mode="json")
            ],
        }

    async def _goal(self, state: PlannerState) -> dict[str, Any]:
        payload = state["payload"]
        structured_goals = payload.get("goals")
        if structured_goals is not None:
            if not isinstance(structured_goals, list) or not 1 <= len(structured_goals) <= 6:
                raise InputValidationError("一次必须选择 1–6 个规划科目")
            student = StudentAcademicProfile.model_validate(state["student"])
            exam = state["exam_profile"]
            allowed_subjects = {
                Subject(item) for item in exam.get("compulsory_subjects", [])
            }
            allowed_subjects.update(student.selected_subjects or student.subject_intentions)
            goals: list[LearningGoal] = []
            seen_subjects: set[Subject] = set()
            feasibility_by_subject: dict[str, dict[str, Any]] = {}
            sub_goals_by_subject: dict[str, dict[str, Any]] = {}
            subject_factors = payload.get("subject_factors", {})
            for raw in structured_goals:
                if not isinstance(raw, dict):
                    raise InputValidationError("规划科目目标格式不正确")
                try:
                    subject = Subject(str(raw.get("subject", "")))
                    current_value = float(raw["current_value"])
                    target_value = float(raw["target_value"])
                    deadline = date.fromisoformat(str(raw["deadline"]))
                    priority = int(raw.get("priority", 1))
                except (KeyError, TypeError, ValueError) as exc:
                    raise InputValidationError("每个规划科目都必须提供当前分、目标分和日期") from exc
                if subject in seen_subjects:
                    raise InputValidationError(f"规划科目重复：{subject.value}")
                if subject not in allowed_subjects:
                    raise PolicyConflictError("规划科目不在当前地区确认的考试科目中")
                if priority not in {1, 2, 3}:
                    raise InputValidationError(
                        f"{subject.value} 的规划优先级必须是 1、2 或 3"
                    )
                score_max = 150 if subject in {
                    Subject.CHINESE,
                    Subject.MATHEMATICS,
                    Subject.FOREIGN_LANGUAGE,
                } else 100
                if current_value < 0 or target_value <= current_value or target_value > score_max:
                    raise InputValidationError(
                        f"{subject.value} 的当前成绩或目标成绩不合理",
                        details={"score_max": score_max},
                    )
                scope = {
                    "curriculum_version": raw.get("curriculum_version"),
                    "class_progress": list(raw.get("class_progress") or []),
                }
                goal = LearningGoal(
                    student_id=student.student_id,
                    goal_type="subject_score",
                    subject=subject,
                    target=GoalTarget(
                        metric=f"{subject.value}_score",
                        current_value=current_value,
                        target_value=target_value,
                    ),
                    deadline=deadline,
                    priority=priority,
                    scope=scope,
                    status="active",
                    confidence=1.0,
                )
                goals.append(goal)
                seen_subjects.add(subject)
                factors = subject_factors.get(subject.value, {})
                score_gap = max(target_value - current_value, 0)
                feasibility_inputs = {
                    "time_sufficiency": min(
                        float(payload.get("weekly_available_minutes", 0))
                        / max(420, 180 * len(structured_goals)),
                        1,
                    ),
                    "foundation_match": min(current_value / score_max, 1),
                    "historical_improvement": float(
                        factors.get("historical_improvement", 0.5)
                    ),
                    "target_increment_reasonableness": max(
                        0, 1 - score_gap / (score_max * 0.4)
                    ),
                    "execution_stability": float(
                        factors.get("execution_stability", 0.5)
                    ),
                    "resource_availability": 0.8,
                }
                feasibility_by_subject[subject.value] = self.goal_service.feasibility(
                    feasibility_inputs
                )
                sub_goals_by_subject[subject.value] = self.goal_service.decompose(goal)
            primary = goals[0]
            return {
                "goals": [goal.model_dump(mode="json") for goal in goals],
                "result": {
                    "goal": primary.model_dump(mode="json"),
                    "goals": [goal.model_dump(mode="json") for goal in goals],
                    "sub_goals": sub_goals_by_subject[primary.subject.value],
                    "sub_goals_by_subject": sub_goals_by_subject,
                    "feasibility": feasibility_by_subject[primary.subject.value],
                    "feasibility_by_subject": feasibility_by_subject,
                },
                "lifecycle_status": AgentLifecycleStatus.GOAL_READY,
                "next_node": "knowledge",
            }
        text = str(payload.get("goal_text", "")).strip()
        if not text:
            return self._need_information(
                state,
                [
                    {
                        "field": "goal_text",
                        "type": "text",
                        "text": "你最希望提升哪一科，准备哪次考试？",
                    }
                ],
            )
        deadline = (
            date.fromisoformat(payload["goal_deadline"]) if payload.get("goal_deadline") else None
        )
        parsed = self.goal_service.parse(text, explicit_deadline=deadline)
        overrides = payload.get("goal_fields", {})
        update: dict[str, Any] = {}
        for field in ("current_value", "target_value", "deadline", "subject", "goal_type"):
            if field in overrides and overrides[field] is not None:
                value = overrides[field]
                if field == "deadline" and isinstance(value, str):
                    value = date.fromisoformat(value)
                if field == "subject":
                    value = Subject(value)
                update[field] = value
        if update:
            parsed = parsed.model_copy(update=update)
        missing = [
            field
            for field in ("subject", "current_value", "target_value", "deadline")
            if getattr(parsed, field) is None
        ]
        parsed = parsed.model_copy(update={"missing_fields": missing})
        if missing:
            if not self.goal_interpreter.available:
                raise PlannerModelUnavailableError(
                    "学习规划大模型尚未配置，已禁止使用规则解析代替模型理解目标",
                    details={
                        "provider": self.settings.llm_provider,
                        "model": self.settings.llm_model,
                    },
                )
            try:
                llm_parsed = await self.goal_interpreter.parse(
                    text,
                    grade=state["student"]["grade"],
                    exam_profile_id=state["exam_profile"]["exam_profile_id"],
                )
                if llm_parsed:
                    safe_updates = {
                        field: getattr(llm_parsed, field)
                        for field in ("subject", "current_value", "target_value")
                        if getattr(parsed, field) is None and getattr(llm_parsed, field) is not None
                    }
                    parsed = parsed.model_copy(update=safe_updates)
                    missing = [
                        field
                        for field in ("subject", "current_value", "target_value", "deadline")
                        if getattr(parsed, field) is None
                    ]
                    parsed = parsed.model_copy(update={"missing_fields": missing})
            except Exception as exc:
                raise PlannerModelUnavailableError(
                    "学习规划大模型目标理解失败，不会降级为规则模板回答",
                    details={
                        "provider": self.settings.llm_provider,
                        "model": self.settings.llm_model,
                        "stage": "goal_interpretation",
                    },
                ) from exc
        if parsed.missing_fields:
            result = self._need_information(
                state,
                self.goal_service.clarification_questions(parsed),
            )
            result["goal_parse"] = parsed.model_dump(mode="json")
            return result
        assert (
            parsed.subject is not None
            and parsed.target_value is not None
            and parsed.deadline is not None
        )
        goal = LearningGoal(
            student_id=state["student"]["student_id"],
            goal_type=parsed.goal_type or "subject_score",
            subject=parsed.subject,
            target=GoalTarget(
                metric=f"{parsed.subject.value}_score",
                current_value=parsed.current_value,
                target_value=parsed.target_value,
            ),
            deadline=parsed.deadline,
            exam_context={
                "exam_profile_id": state["exam_profile"]["exam_profile_id"],
                "deadline_event": parsed.deadline_event,
            },
            status="active",
            confidence=min(value for value in parsed.field_confidence.values() if value > 0),
        )
        feasibility_inputs = payload.get("feasibility_factors", {})
        if not feasibility_inputs:
            score_gap = max(parsed.target_value - float(parsed.current_value or 0), 0)
            feasibility_inputs = {
                "time_sufficiency": min(float(payload.get("weekly_available_minutes", 0)) / 420, 1),
                "foundation_match": min(float(parsed.current_value or 0) / 120, 1),
                "historical_improvement": 0.5,
                "target_increment_reasonableness": max(0, 1 - score_gap / 60),
                "execution_stability": 0.5,
                "resource_availability": 0.8,
            }
        return {
            "goal_parse": parsed.model_dump(mode="json"),
            "goals": [goal.model_dump(mode="json")],
            "result": {
                "goal": goal.model_dump(mode="json"),
                "sub_goals": self.goal_service.decompose(goal),
                "feasibility": self.goal_service.feasibility(feasibility_inputs),
            },
            "lifecycle_status": AgentLifecycleStatus.GOAL_READY,
            "next_node": "knowledge",
        }

    def _knowledge(self, state: PlannerState) -> dict[str, Any]:
        from ai_education.domain.models import KnowledgeProfile

        payload = state["payload"]
        goals = [LearningGoal.model_validate(item) for item in state["goals"]]
        evidence_by_subject = payload.get("knowledge_evidence_by_subject")
        if evidence_by_subject is None and len(goals) == 1:
            evidence_by_subject = {
                goals[0].subject.value: payload.get("knowledge_evidence", [])
            }
        missing_subjects = [
            goal.subject.value
            for goal in goals
            if not isinstance(evidence_by_subject, dict)
            or not evidence_by_subject.get(goal.subject.value)
        ]
        if missing_subjects:
            return self._need_information(
                state,
                [
                    {
                        "field": "knowledge_evidence",
                        "type": "choice",
                        "text": "请为以下科目完成诊断测评：" + "、".join(missing_subjects),
                    }
                ],
                lifecycle=AgentLifecycleStatus.ASSESSMENT_PENDING,
            )
        profiles_by_subject: dict[str, KnowledgeProfile] = {}
        for goal in goals:
            subject_key = goal.subject.value
            edges_by_subject = payload.get("prerequisite_edges_by_subject", {})
            edges = (
                edges_by_subject.get(subject_key, [])
                if isinstance(edges_by_subject, dict)
                else []
            )
            if len(goals) == 1 and not edges:
                edges = payload.get("prerequisite_edges", [])
            profiles_by_subject[subject_key] = self.knowledge_service.build_profile(
                state["student"]["student_id"],
                goal.subject,
                list(evidence_by_subject[subject_key]),
                prerequisite_edges=edges,
            )
        profiles = list(profiles_by_subject.values())
        quality_fields = (
            "coverage",
            "confidence",
            "objective_evidence_ratio",
        )
        combined_quality = {
            field: min(profile.assessment_quality.get(field, 0) for profile in profiles)
            for field in quality_fields
        }
        combined_quality.update(
            {
                "objective_evidence_count": sum(
                    profile.assessment_quality.get("objective_evidence_count", 0)
                    for profile in profiles
                ),
                "self_report_evidence_count": sum(
                    profile.assessment_quality.get("self_report_evidence_count", 0)
                    for profile in profiles
                ),
                "calibration_gap": max(
                    profile.assessment_quality.get("calibration_gap", 0)
                    for profile in profiles
                ),
                "evidence_sufficient": 1.0
                if all(
                    profile.assessment_quality.get("evidence_sufficient", 0) >= 1
                    for profile in profiles
                )
                else 0.0,
                "subject_count": float(len(profiles)),
                "subjects_with_sufficient_evidence": float(
                    sum(
                        profile.assessment_quality.get("evidence_sufficient", 0) >= 1
                        for profile in profiles
                    )
                ),
            }
        )
        mode_rank = {"quick": 0, "standard": 1, "full": 2, "paper_based": 3}
        assessment_mode = max(
            (profile.assessment_mode for profile in profiles),
            key=lambda item: mode_rank[item],
        )
        profile = KnowledgeProfile(
            student_id=state["student"]["student_id"],
            knowledge_states=[
                item for subject_profile in profiles for item in subject_profile.knowledge_states
            ],
            question_type_states=[
                item
                for subject_profile in profiles
                for item in subject_profile.question_type_states
            ],
            exam_skill_states=[
                {**item, "subject": subject}
                for subject, subject_profile in profiles_by_subject.items()
                for item in subject_profile.exam_skill_states
            ],
            priority_gaps=[
                item for subject_profile in profiles for item in subject_profile.priority_gaps
            ],
            prerequisite_gaps=[
                item
                for subject_profile in profiles
                for item in subject_profile.prerequisite_gaps
            ],
            assessment_quality=combined_quality,
            assessment_mode=assessment_mode,
        )
        self.repository.save_knowledge_profile(profile)
        return {
            "knowledge_profile": profile.model_dump(mode="json"),
            "knowledge_profiles_by_subject": {
                subject: subject_profile.model_dump(mode="json")
                for subject, subject_profile in profiles_by_subject.items()
            },
            "lifecycle_status": AgentLifecycleStatus.KNOWLEDGE_PROFILE_READY,
            "next_node": "time",
        }

    def _time(self, state: PlannerState) -> dict[str, Any]:
        raw_capacity = state["payload"].get("daily_capacity", [])
        if not raw_capacity:
            return self._need_information(
                state,
                [
                    {
                        "field": "daily_capacity",
                        "type": "weekly_schedule",
                        "text": "请提供每周自主学习时段。",
                    }
                ],
            )
        student = StudentAcademicProfile.model_validate(state["student"])
        exam = state["exam_profile"]
        goal_subjects = list(
            dict.fromkeys(
                goal.subject
                for item in state["goals"]
                if (goal := LearningGoal.model_validate(item)).subject
            )
        )
        subjects = goal_subjects
        if not subjects:
            subjects = [Subject(item) for item in exam["compulsory_subjects"]]
            subjects.extend(student.selected_subjects or student.subject_intentions)
        profile = self.time_service.build(
            student.student_id,
            student.grade,
            [DailyAvailability.model_validate(item) for item in raw_capacity],
            subjects,
            state["payload"].get("subject_factors", {}),
            efficiency_factor=float(state["payload"].get("efficiency_factor", 0.9)),
            execution_reliability=float(state["payload"].get("execution_reliability", 0.9)),
            max_focus_minutes=int(state["payload"].get("max_focus_minutes", 45)),
        )
        self.repository.save_time_profile(profile)
        return {
            "time_profile": profile.model_dump(mode="json"),
            "lifecycle_status": AgentLifecycleStatus.TIME_PROFILE_READY,
            "next_node": "plan",
        }

    async def _plan(self, state: PlannerState) -> dict[str, Any]:
        student = StudentAcademicProfile.model_validate(state["student"])
        from ai_education.domain.models import ExamProfile, KnowledgeProfile, TimeProfile

        plan = self.plan_service.generate(
            student,
            ExamProfile.model_validate(state["exam_profile"]),
            [LearningGoal.model_validate(item) for item in state["goals"]],
            KnowledgeProfile.model_validate(state["knowledge_profile"]),
            TimeProfile.model_validate(state["time_profile"]),
            plan_start=date.fromisoformat(state["payload"]["plan_start"])
            if state["payload"].get("plan_start")
            else None,
            persist=False,
        )
        if not self.plan_narrator.available:
            raise PlannerModelUnavailableError(
                "学习规划大模型尚未配置，已禁止返回固定模板规划说明",
                details={
                    "provider": self.settings.llm_provider,
                    "model": self.settings.llm_model,
                    "stage": "plan_explanation",
                },
            )
        context = {
            "student": {
                "grade": state["student"]["grade"],
                "province_code": state["student"]["province_code"],
                "target_exam_year": state["student"]["target_exam_year"],
                "class_progress": state["student"].get("class_progress", {}),
            },
            "exam_profile": state["exam_profile"],
            "goal": state["result"]["goal"],
            "goals": state["result"].get("goals", [state["result"]["goal"]]),
            "sub_goals": state["result"]["sub_goals"],
            "sub_goals_by_subject": state["result"].get("sub_goals_by_subject", {}),
            "feasibility": state["result"]["feasibility"],
            "feasibility_by_subject": state["result"].get(
                "feasibility_by_subject", {}
            ),
            "knowledge_profile": state["knowledge_profile"],
            "knowledge_profiles_by_subject": state.get(
                "knowledge_profiles_by_subject", {}
            ),
            "time_profile": state["time_profile"],
            "plan": plan.model_dump(mode="json"),
        }
        try:
            narrative = await self.plan_narrator.explain(context)
        except Exception as exc:
            raise PlannerModelUnavailableError(
                "学习规划大模型生成规划说明失败，不会降级为固定模板回答",
                details={
                    "provider": self.settings.llm_provider,
                    "model": self.settings.llm_model,
                    "stage": "plan_explanation",
                },
            ) from exc
        if narrative is None:
            raise PlannerModelUnavailableError("学习规划大模型没有返回有效的规划说明")
        task_rationales = {item.task_id: item.rationale for item in narrative.task_rationales}
        for task in plan.tasks:
            if task.task_id in task_rationales:
                task.rationale = task_rationales[task.task_id]
        plan.explanations = {
            "student": narrative.student,
            "teacher": narrative.teacher,
            "strategy": narrative.strategy,
        }
        plan.generation_basis.update(
            {
                "narrative_generation_mode": "llm",
                "llm_provider": self.settings.llm_provider,
                "llm_model": self.settings.llm_model,
            }
        )
        plan = self.repository.save_plan(plan)
        is_provisional = plan.status.value == "provisional"
        status = (
            StandardStatus.PARTIAL_SUCCESS
            if is_provisional
            else StandardStatus.SUCCESS
            if plan.validation and plan.validation.valid
            else StandardStatus.CONFLICT
        )
        lifecycle = (
            AgentLifecycleStatus.ASSESSMENT_PENDING
            if is_provisional
            else AgentLifecycleStatus.WAITING_FOR_CONFIRMATION
            if plan.status.value == "waiting_for_confirmation"
            else AgentLifecycleStatus.MANUAL_REVIEW_REQUIRED
        )
        return {
            "plan": plan.model_dump(mode="json"),
            "result": {
                **state.get("result", {}),
                "knowledge_profile": state["knowledge_profile"],
                "knowledge_profiles_by_subject": state.get(
                    "knowledge_profiles_by_subject", {}
                ),
                "time_profile": state["time_profile"],
                "plan": plan.model_dump(mode="json"),
                "next_action": "complete_quick_diagnostic"
                if is_provisional
                else "request_plan_confirmation"
                if status == StandardStatus.SUCCESS
                else "manual_review",
            },
            "response_status": status,
            "lifecycle_status": lifecycle,
        }

    def _practice(self, state: PlannerState) -> dict[str, Any]:
        event = PracticeEvent.model_validate(state["payload"].get("event", state["payload"]))
        update = self.practice_service.ingest(event)
        return {
            "result": {
                "practice_update": update.model_dump(mode="json"),
                "next_action": "evaluate_adjustment"
                if update.replan_check_required
                else "update_status",
            },
            "response_status": StandardStatus.PARTIAL_SUCCESS
            if update.duplicate
            else StandardStatus.SUCCESS,
            "lifecycle_status": AgentLifecycleStatus.PLAN_ACTIVE,
        }

    def _adjust(self, state: PlannerState) -> dict[str, Any]:
        payload = state["payload"]
        plan_id = payload.get("plan_id")
        if not plan_id:
            active = self.repository.active_plan_for_student(state["request"]["student_id"])
            plan_id = active.plan_id if active else None
        if not plan_id:
            raise InputValidationError("没有可调整的活动计划")
        level = (
            AdjustmentLevel(payload["level"])
            if payload.get("level")
            else self.plan_service.adjustment_level(payload.get("metrics", {}))
        )
        if level is None:
            current = self.repository.get_plan(plan_id)
            return {
                "result": {
                    "adjusted": False,
                    "plan": current.model_dump(mode="json") if current else None,
                },
                "lifecycle_status": AgentLifecycleStatus.PLAN_ACTIVE,
            }
        revised = self.plan_service.revise(
            plan_id, level, reason=str(payload.get("reason", "规则触发调整"))
        )
        return {
            "result": {
                "adjusted": True,
                "adjustment_level": level,
                "plan": revised.model_dump(mode="json"),
            },
            "lifecycle_status": AgentLifecycleStatus.WAITING_FOR_CONFIRMATION,
        }

    def _apply_diagnosis(self, state: PlannerState) -> dict[str, Any]:
        payload = state["payload"]
        diagnosis = payload.get("diagnosis", {})
        learning_state = diagnosis.get("learning_state", {})
        if not learning_state:
            raise InputValidationError("缺少可用于规划的结构化诊断结果")
        weak = [
            {
                "knowledge_point": item.get("dimension_label") or item.get("dimension_id"),
                "mastery": item.get("mastery_probability"),
                "confidence": item.get("confidence"),
            }
            for item in learning_state.get("knowledge_states", [])
            if item.get("mastery_level") in {"needs_support", "developing"}
        ]
        if not weak:
            unified = state["request"].get("context", {}).get("unified_student_profile", {})
            weak = [
                {"knowledge_point": item, "mastery": None, "confidence": None}
                for item in unified.get("weak_points", [])[:4]
            ]
        targets = [item["knowledge_point"] for item in weak[:4]]
        target_text = "、".join(targets) if targets else "当前证据较少的英语阅读能力"
        current = self.repository.latest_plan_for_student(state["request"]["student_id"])
        schedule = [
            {"day": 1, "minutes": 20, "task": "复盘近期错题并标注错误类型"},
            {"day": 2, "minutes": 25, "task": f"针对 {target_text} 做基础辨析训练"},
            {"day": 3, "minutes": 25, "task": "完成一组同类题，逐题写出定位依据"},
            {"day": 4, "minutes": 30, "task": "进行变式练习，比较正确与错误思路"},
            {"day": 5, "minutes": 30, "task": "完成跨知识点混合训练并限时"},
            {"day": 6, "minutes": 35, "task": "完成一篇完整阅读并记录各题耗时"},
            {"day": 7, "minutes": 20, "task": "复测薄弱点，根据新证据决定下周安排"},
        ]
        evidence_level = learning_state.get("diagnosis_status", "unknown")
        return {
            "result": {
                "plan_adaptation": {
                    "source_diagnosis_id": learning_state.get("diagnosis_id"),
                    "diagnosis_status": evidence_level,
                    "priority_targets": weak[:4],
                    "seven_day_schedule": schedule,
                    "current_plan_id": current.plan_id if current else None,
                    "current_plan_version": current.version if current else None,
                    "mutation_applied": False,
                    "requires_confirmation": True,
                    "student_message": (
                        f"我先根据你的真实作答记录，把重点放在：{target_text}。"
                        "已生成一份 7 天训练建议：前两天复盘和基础辨析，"
                        "第 3 至 6 天逐步增加变式、混合与限时阅读，第 7 天复测。"
                        "这份建议尚未覆盖你的正式计划，需要你确认后再调整。"
                    ),
                }
            },
            "lifecycle_status": AgentLifecycleStatus.PLAN_ADJUST_PENDING,
        }

    def _get_plan(self, state: PlannerState) -> dict[str, Any]:
        plan_id = state["payload"].get("plan_id")
        plan = (
            self.repository.get_plan(plan_id)
            if plan_id
            else self.repository.latest_plan_for_student(state["request"]["student_id"])
            if state["payload"].get("scope") == "latest"
            else self.repository.active_plan_for_student(state["request"]["student_id"])
        )
        if not plan:
            raise InputValidationError("未找到计划")
        student_id = state["request"]["student_id"]
        student = self.repository.get_student(student_id)
        knowledge = self.repository.get_knowledge_profile(student_id)
        time_profile = self.repository.get_time_profile(student_id)
        return {
            "result": {
                "plan": plan.model_dump(mode="json"),
                "student_profile": student.model_dump(mode="json") if student else None,
                "knowledge_profile": knowledge.model_dump(mode="json") if knowledge else None,
                "time_profile": time_profile.model_dump(mode="json") if time_profile else None,
            },
            "lifecycle_status": AgentLifecycleStatus.PLAN_ACTIVE,
        }

    def _confirm(self, state: PlannerState) -> dict[str, Any]:
        payload = state["payload"]
        plan = self.plan_service.confirm(
            str(payload["plan_id"]), expected_version=int(payload["expected_version"])
        )
        return {
            "result": {"plan": plan.model_dump(mode="json"), "event": "PlanPublished"},
            "lifecycle_status": AgentLifecycleStatus.PLAN_ACTIVE,
        }

    def _unsupported(self, state: PlannerState) -> dict[str, Any]:
        return {
            "response_status": StandardStatus.FAILED,
            "lifecycle_status": AgentLifecycleStatus.FAILED,
            "errors": [
                ErrorDetail(
                    code="UNSUPPORTED_INTENT", message=f"不支持的意图：{state['intent']}"
                ).model_dump(mode="json")
            ],
        }

    @staticmethod
    def _need_information(
        state: PlannerState,
        questions: list[dict[str, Any]],
        *,
        lifecycle: AgentLifecycleStatus = AgentLifecycleStatus.WAITING_FOR_DATA,
    ) -> dict[str, Any]:
        return {
            "response_status": StandardStatus.NEED_MORE_INFORMATION,
            "lifecycle_status": lifecycle,
            "result": {
                **state.get("result", {}),
                "questions": questions,
                "next_action": "collect_information",
            },
            "next_node": "finish",
        }

    def _to_response(self, request: AgentRequest, state: PlannerState) -> AgentResponse:
        status = StandardStatus(state.get("response_status", StandardStatus.SUCCESS))
        messages = []
        if state.get("result"):
            messages.append(
                AgentMessage(
                    trace_id=request.trace_id,
                    message_type=MessageType.RESULT,
                    sender=AgentRole.PERSONALIZED_LEARNING_PLANNER,
                    student_id=request.student_id,
                    payload={"intent": request.intent, "status": status},
                )
            )
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            status=status,
            lifecycle_status=str(state.get("lifecycle_status", AgentLifecycleStatus.FAILED)),
            result=state.get("result", {}),
            messages=messages,
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            warnings=[WarningDetail.model_validate(item) for item in state.get("warnings", [])],
            errors=[ErrorDetail.model_validate(item) for item in state.get("errors", [])],
            data_version=request.data_version,
        )

    def _error_response(
        self,
        request: AgentRequest,
        *,
        status: StandardStatus,
        lifecycle: AgentLifecycleStatus,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            status=status,
            lifecycle_status=lifecycle,
            errors=[
                ErrorDetail(code=code, message=message, details=details or {}, retryable=retryable)
            ],
            data_version=request.data_version,
        )
