"""Fourth LangGraph Agent: grounded, teacher-in-the-loop lesson preparation."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.domain.enums import (
    ActorType,
    AgentRole,
    MessageType,
    StandardStatus,
    Subject,
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
from ai_education.services.teacher_preparation import TeacherPreparationService
from ai_education.tools.teacher_preparation import TeacherPreparationToolbox


class TeacherPreparationGraphState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    next_node: str
    final_result: dict[str, Any]
    response_status: StandardStatus
    lifecycle_status: str
    evidence: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class TeacherPreparationAgent(BaseEducationAgent):
    def __init__(self, service: TeacherPreparationService) -> None:
        self.service = service
        self.repository = service.repository
        self.knowledge_base = service.knowledge_base
        self.generator = service.generator
        self.toolbox = TeacherPreparationToolbox()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="teacher_lesson_preparation_agent",
            role=AgentRole.TEACHER_PREPARATION,
            version="1.0.0",
            description="基于班级匿名学情与九科优秀教案的教师在环备课智能体",
            capabilities=set(self.toolbox.capability_manifest()),
            accepted_intents={
                "create_lesson_plan",
                "list_lesson_plans",
                "get_lesson_plan",
                "list_lesson_plan_versions",
                "revise_lesson_plan",
                "rollback_lesson_plan",
                "approve_lesson_plan",
                "publish_lesson_plan",
                "record_post_lesson_feedback",
                "search_teaching_resources",
            },
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        cached = self.repository.get_idempotent(request.idempotency_key)
        if cached:
            return AgentResponse.model_validate(cached)
        initial: TeacherPreparationGraphState = {
            "request": request.model_dump(mode="json"),
            "intent": request.intent,
            "payload": request.payload,
            "warnings": [],
            "errors": [],
            "evidence": [],
            "messages": [],
            "response_status": StandardStatus.SUCCESS,
            "lifecycle_status": "received",
        }
        try:
            self._require_teacher(request)
            final = await self.graph.ainvoke(initial)
            response = self._to_response(request, final)
        except (ValidationError, InputValidationError) as exc:
            details = (
                exc.details
                if isinstance(exc, InputValidationError)
                else {
                    "fields": [
                        ".".join(str(part) for part in error["loc"]) for error in exc.errors()
                    ]
                }
            )
            response = self._error_response(
                request,
                StandardStatus.NEED_MORE_INFORMATION,
                "waiting_for_teacher_input",
                "TEACHER_PREPARATION_INPUT_INVALID",
                exc.message if isinstance(exc, InputValidationError) else "备课请求未通过结构校验",
                details,
            )
        except AIEducationError as exc:
            response = self._error_response(
                request,
                StandardStatus.FAILED,
                "failed",
                exc.code,
                exc.message,
                exc.details,
            )
        except Exception:
            response = self._error_response(
                request,
                StandardStatus.FAILED,
                "failed",
                "UNEXPECTED_TEACHER_PREPARATION_ERROR",
                "教师备课流程出现未预期错误，未发布未经教师确认的内容",
                {},
            )
        self.repository.put_idempotent(request.idempotency_key, response.model_dump(mode="json"))
        return response

    @staticmethod
    def _require_teacher(request: AgentRequest) -> None:
        if request.actor.type not in {ActorType.TEACHER, ActorType.ADMIN}:
            raise InputValidationError("教师备课 Agent 仅接受教师或管理员操作")

    def _build_graph(self):
        graph = StateGraph(TeacherPreparationGraphState)
        for name, node in {
            "dispatch": self._dispatch,
            "create": self._create,
            "list": self._list,
            "get": self._get,
            "versions": self._versions,
            "revise": self._revise,
            "rollback": self._rollback,
            "transition": self._transition,
            "feedback": self._feedback,
            "search": self._search,
            "unsupported": self._unsupported,
        }.items():
            graph.add_node(name, node)
        graph.add_edge(START, "dispatch")
        routes = {
            "create": "create",
            "list": "list",
            "get": "get",
            "versions": "versions",
            "revise": "revise",
            "rollback": "rollback",
            "transition": "transition",
            "feedback": "feedback",
            "search": "search",
            "unsupported": "unsupported",
        }
        graph.add_conditional_edges("dispatch", lambda state: state["next_node"], routes)
        for node in routes:
            graph.add_edge(node, END)
        return graph.compile()

    def _dispatch(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        routes = {
            "create_lesson_plan": "create",
            "list_lesson_plans": "list",
            "get_lesson_plan": "get",
            "list_lesson_plan_versions": "versions",
            "revise_lesson_plan": "revise",
            "rollback_lesson_plan": "rollback",
            "approve_lesson_plan": "transition",
            "publish_lesson_plan": "transition",
            "record_post_lesson_feedback": "feedback",
            "search_teaching_resources": "search",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    async def _create(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        teacher_id = state["request"]["actor"]["id"]
        plan = await self.service.create_plan(teacher_id=teacher_id, payload=state["payload"])
        return self._plan_result(plan)

    def _list(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        teacher_id = state["request"]["actor"]["id"]
        classroom_id = state["payload"].get("classroom_id")
        plans = self.repository.list_teacher(
            teacher_id,
            classroom_id=int(classroom_id) if classroom_id else None,
        )
        return {
            "final_result": {
                "lesson_plans": [
                    item.model_dump(mode="json", exclude={"resources"}) for item in plans
                ]
            },
            "lifecycle_status": "listed",
        }

    def _get(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        teacher_id = state["request"]["actor"]["id"]
        version = state["payload"].get("version")
        plan = self.repository.get(
            str(state["payload"].get("lesson_plan_id", "")),
            teacher_id,
            int(version) if version else None,
        )
        return {
            "final_result": {"lesson_plan": plan.model_dump(mode="json")},
            "lifecycle_status": plan.status.value,
            "evidence": self._resource_evidence(plan),
        }

    def _versions(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        teacher_id = state["request"]["actor"]["id"]
        versions = self.repository.versions(
            str(state["payload"].get("lesson_plan_id", "")),
            teacher_id,
        )
        return {
            "final_result": {
                "versions": [
                    {
                        "lesson_plan_id": item.lesson_plan_id,
                        "version": item.version,
                        "parent_version": item.parent_version,
                        "status": item.status.value,
                        "title": item.title,
                        "created_at": item.created_at.isoformat(),
                        "generation_mode": item.generation_mode,
                        "change_summary": list(item.change_summary),
                        **self._revision_audit(item),
                    }
                    for item in reversed(versions)
                ]
            },
            "lifecycle_status": "versions_listed",
        }

    @staticmethod
    def _revision_audit(item: Any) -> dict[str, Any]:
        prompt = item.revision_prompt
        component = item.revision_component
        locked_ids = list(item.revision_locked_component_ids)
        if not prompt:
            for summary in item.change_summary:
                legacy = re.match(r"^局部修订\s+([^：:]+)[：:]([\s\S]+)$", summary)
                if legacy:
                    component = legacy.group(1).strip()
                    prompt = legacy.group(2).strip()
                    locked_ids = list(item.locked_component_ids)
                    break
        return {
            "revision_prompt": prompt,
            "revision_component": component,
            "revision_locked_component_ids": locked_ids,
        }

    def _rollback(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        plan = self.service.rollback_plan(
            teacher_id=state["request"]["actor"]["id"],
            lesson_plan_id=str(state["payload"].get("lesson_plan_id", "")),
            expected_version=int(state["payload"].get("expected_version", 0)),
            target_version=int(state["payload"].get("target_version", 0)),
        )
        return self._plan_result(plan)

    async def _revise(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        plan = await self.service.revise_plan(
            teacher_id=state["request"]["actor"]["id"],
            lesson_plan_id=str(state["payload"].get("lesson_plan_id", "")),
            payload=state["payload"],
        )
        return self._plan_result(plan)

    def _transition(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        action = "approve" if state["intent"] == "approve_lesson_plan" else "publish"
        plan = self.service.transition(
            teacher_id=state["request"]["actor"]["id"],
            lesson_plan_id=str(state["payload"].get("lesson_plan_id", "")),
            expected_version=int(state["payload"].get("expected_version", 0)),
            action=action,
            note=str(state["payload"].get("note", "")),
        )
        messages = self._published_messages(state, plan) if action == "publish" else []
        return {
            "final_result": {"lesson_plan": plan.model_dump(mode="json")},
            "lifecycle_status": plan.status.value,
            "messages": [item.model_dump(mode="json") for item in messages],
            "evidence": self._resource_evidence(plan),
        }

    def _feedback(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        feedback, plan = self.service.record_feedback(
            teacher_id=state["request"]["actor"]["id"],
            lesson_plan_id=str(state["payload"].get("lesson_plan_id", "")),
            payload=state["payload"],
        )
        return {
            "final_result": {
                "feedback": feedback.model_dump(mode="json"),
                "lesson_plan": plan.model_dump(mode="json"),
            },
            "lifecycle_status": plan.status.value,
        }

    def _search(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        resources = self.knowledge_base.search(
            str(state["payload"].get("query", "")),
            subject=Subject(state["payload"].get("subject", Subject.MATHEMATICS)),
            limit=int(state["payload"].get("limit", 3)),
        )
        return {
            "final_result": {
                "resources": [item.model_dump(mode="json") for item in resources],
                "resource_count": len(resources),
            },
            "lifecycle_status": "resources_retrieved",
        }

    def _unsupported(self, state: TeacherPreparationGraphState) -> dict[str, Any]:
        return {
            "response_status": StandardStatus.FAILED,
            "lifecycle_status": "failed",
            "errors": [
                ErrorDetail(
                    code="UNSUPPORTED_TEACHER_PREPARATION_INTENT",
                    message=f"教师备课 Agent 不支持意图：{state['intent']}",
                ).model_dump(mode="json")
            ],
            "final_result": {},
        }

    def _plan_result(self, plan) -> dict[str, Any]:
        warnings = [
            WarningDetail(
                code=issue.code,
                message=issue.message,
                details={
                    "severity": issue.severity,
                    "component_id": issue.component_id,
                },
            )
            for issue in plan.quality_report.issues
        ]
        return {
            "final_result": {"lesson_plan": plan.model_dump(mode="json")},
            "response_status": StandardStatus.MANUAL_REVIEW_REQUIRED,
            "lifecycle_status": plan.status.value,
            "warnings": [item.model_dump(mode="json") for item in warnings],
            "evidence": self._resource_evidence(plan),
        }

    @staticmethod
    def _resource_evidence(plan) -> list[dict[str, Any]]:
        return [
            Evidence(
                source_type="curated_teaching_resource",
                source_id=item.resource_id,
                description=f"{item.title}｜{item.source_organization}",
                confidence=1.0 if item.checksum_verified else 0.7,
                metadata={
                    "subject": item.subject.value,
                    "source_location": item.source_location,
                    "copyright_status": item.copyright_status,
                    "checksum_verified": item.checksum_verified,
                },
            ).model_dump(mode="json")
            for item in plan.resources
        ]

    @staticmethod
    def _published_messages(state: TeacherPreparationGraphState, plan) -> list[AgentMessage]:
        assessment_items = [
            {
                "question_id": item.question_id,
                "knowledge_tags": item.knowledge_tags,
                "ability_tags": item.ability_tags,
                "difficulty": item.difficulty,
                "common_error_tags": item.common_error_tags,
                "max_score": len(item.scoring_rubric),
            }
            for item in plan.assessments
        ]
        common = {
            "lesson_plan_id": plan.lesson_plan_id,
            "lesson_version": plan.version,
            "class_id": str(plan.context.classroom_id),
            "subject": plan.context.subject.value,
        }
        return [
            AgentMessage(
                trace_id=state["request"]["trace_id"],
                message_type=MessageType.EVENT,
                sender=AgentRole.TEACHER_PREPARATION,
                recipient=AgentRole.LEARNING_DIAGNOSIS,
                student_id=state["request"]["student_id"],
                payload={
                    **common,
                    "event_type": "assessment.blueprint.published",
                    "assessment_items": assessment_items,
                },
            ),
            AgentMessage(
                trace_id=state["request"]["trace_id"],
                message_type=MessageType.EVENT,
                sender=AgentRole.TEACHER_PREPARATION,
                recipient=AgentRole.HOMEWORK_TUTOR,
                student_id=state["request"]["student_id"],
                payload={
                    **common,
                    "event_type": "homework.blueprint.published",
                    "layers": [item.model_dump(mode="json") for item in plan.differentiation_plan],
                    "assessment_items": [
                        item
                        for item in assessment_items
                        if item["question_id"].startswith("q_home_")
                    ],
                },
            ),
        ]

    @staticmethod
    def _to_response(request: AgentRequest, state: TeacherPreparationGraphState) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.TEACHER_PREPARATION,
            status=state.get("response_status", StandardStatus.SUCCESS),
            lifecycle_status=state.get("lifecycle_status", "completed"),
            result=state.get("final_result", {}),
            messages=state.get("messages", []),
            evidence=state.get("evidence", []),
            warnings=state.get("warnings", []),
            errors=state.get("errors", []),
            data_version=request.data_version,
        )

    @staticmethod
    def _error_response(
        request: AgentRequest,
        status: StandardStatus,
        lifecycle: str,
        code: str,
        message: str,
        details: dict[str, Any],
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.TEACHER_PREPARATION,
            status=status,
            lifecycle_status=lifecycle,
            errors=[ErrorDetail(code=code, message=message, details=details)],
            data_version=request.data_version,
        )
