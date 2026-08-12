"""Sixth LangGraph Agent for student programming learning and growth."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.domain.enums import AgentRole, StandardStatus
from ai_education.domain.programming_learning import (
    ProgrammingCodeReviewInput,
    ProgrammingDiagnosticSubmission,
    ProgrammingInterviewAnswerInput,
    ProgrammingInterviewCreateInput,
    ProgrammingProfileInput,
    ProgrammingProjectHintInput,
    ProgrammingProjectRecommendationInput,
)
from ai_education.domain.protocols import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ErrorDetail,
    Evidence,
)
from ai_education.services.programming_learning import ProgrammingLearningService
from ai_education.tools.programming_learning import ProgrammingLearningToolbox


class ProgrammingLearningState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    profile: dict[str, Any]
    next_node: str
    result: dict[str, Any]
    lifecycle_status: str


class ProgrammingLearningAgent(BaseEducationAgent):
    def __init__(self, service: ProgrammingLearningService) -> None:
        self.service = service
        self.repository = service.repository
        self.toolbox = ProgrammingLearningToolbox()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="student_programming_learning_agent",
            role=AgentRole.PROGRAMMING_LEARNING,
            version="1.0.0",
            description="面向全国一卷高中生的 Python 编程成长、项目实训与专业探索智能体",
            capabilities={
                "student_programming_profile",
                "low_floor_diagnostic",
                "major_direction_exploration",
                "twelve_to_twenty_week_roadmap",
                "python_static_analysis",
                "progressive_hints",
                "student_project_decomposition",
                "project_presentation_practice",
                "evidence_based_mastery",
                "weekly_growth_report",
                "exam_period_load_reduction",
            },
            accepted_intents={
                "get_programming_dashboard",
                "update_programming_profile",
                "create_programming_diagnostic",
                "submit_programming_diagnostic",
                "review_python_code",
                "recommend_programming_project",
                "get_programming_project_hint",
                "create_programming_interview",
                "score_programming_interview_answer",
                "get_programming_weekly_report",
            },
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        cached = self.repository.get_idempotent(request.idempotency_key)
        if cached:
            return AgentResponse.model_validate(cached)
        try:
            final = await self.graph.ainvoke(
                {
                    "request": request.model_dump(mode="json"),
                    "intent": request.intent,
                    "payload": request.payload,
                    "profile": request.context.get("student_profile", {}),
                    "lifecycle_status": "received",
                }
            )
            response = AgentResponse(
                request_id=request.request_id,
                trace_id=request.trace_id,
                agent_role=self.metadata.role,
                status=StandardStatus.SUCCESS,
                lifecycle_status=final.get("lifecycle_status", "completed"),
                result=final.get("result", {}),
                evidence=[
                    Evidence(
                        source_type="programming_curriculum_knowledge",
                        source_id=item["source_id"],
                        description=item["title"],
                        confidence=0.95 if item["authority_level"] == "A" else 0.85,
                    )
                    for item in self.service.knowledge.sources()
                ],
            )
        except (ValidationError, InputValidationError) as exc:
            message = (
                exc.message
                if isinstance(exc, InputValidationError)
                else "编程学习输入未通过结构校验"
            )
            response = self._error_response(request, "PROGRAMMING_INPUT_INVALID", message)
        except AIEducationError as exc:
            response = self._error_response(request, exc.code, exc.message)
        except Exception:
            response = self._error_response(
                request,
                "UNEXPECTED_PROGRAMMING_AGENT_ERROR",
                "编程学习流程出现未预期错误，未写入未经验证的能力结论",
            )
        self.repository.put_idempotent(request.idempotency_key, response.model_dump(mode="json"))
        return response

    def _build_graph(self):
        graph = StateGraph(ProgrammingLearningState)
        graph.add_node("dispatch", self._dispatch)
        handlers = {
            "dashboard": self._dashboard,
            "update_profile": self._update_profile,
            "create_diagnostic": self._create_diagnostic,
            "submit_diagnostic": self._submit_diagnostic,
            "review_code": self._review_code,
            "recommend_project": self._recommend_project,
            "project_hint": self._project_hint,
            "create_interview": self._create_interview,
            "score_interview": self._score_interview,
            "weekly_report": self._weekly_report,
            "unsupported": self._unsupported,
        }
        for name, handler in handlers.items():
            graph.add_node(name, handler)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            lambda state: state["next_node"],
            {name: name for name in handlers},
        )
        for name in handlers:
            graph.add_edge(name, END)
        return graph.compile()

    @staticmethod
    def _dispatch(state: ProgrammingLearningState) -> dict[str, Any]:
        routes = {
            "get_programming_dashboard": "dashboard",
            "update_programming_profile": "update_profile",
            "create_programming_diagnostic": "create_diagnostic",
            "submit_programming_diagnostic": "submit_diagnostic",
            "review_python_code": "review_code",
            "recommend_programming_project": "recommend_project",
            "get_programming_project_hint": "project_hint",
            "create_programming_interview": "create_interview",
            "score_programming_interview_answer": "score_interview",
            "get_programming_weekly_report": "weekly_report",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _dashboard(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.dashboard(state["request"]["student_id"], state["profile"])
        return {"result": result, "lifecycle_status": "programming_profile_ready"}

    def _update_profile(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingProfileInput.model_validate(state["payload"])
        result = self.service.update_profile(state["request"]["student_id"], body, state["profile"])
        return {"result": result, "lifecycle_status": "programming_roadmap_ready"}

    def _create_diagnostic(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.create_diagnostic(state["request"]["student_id"])
        return {"result": result, "lifecycle_status": "programming_diagnostic_in_progress"}

    def _submit_diagnostic(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingDiagnosticSubmission.model_validate(
            {"answers": state["payload"].get("answers", [])}
        )
        result = self.service.submit_diagnostic(
            state["request"]["student_id"],
            str(state["payload"].get("diagnostic_id", "")),
            body,
        )
        return {"result": result, "lifecycle_status": "programming_diagnostic_completed"}

    def _review_code(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingCodeReviewInput.model_validate(state["payload"])
        result = self.service.review_code(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "programming_code_review_ready"}

    def _recommend_project(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingProjectRecommendationInput.model_validate(state["payload"])
        result = self.service.recommend_project(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "programming_project_active"}

    def _project_hint(self, state: ProgrammingLearningState) -> dict[str, Any]:
        payload = dict(state["payload"])
        project_id = str(payload.pop("project_id", ""))
        body = ProgrammingProjectHintInput.model_validate(payload)
        result = self.service.next_project_hint(state["request"]["student_id"], project_id, body)
        return {"result": result, "lifecycle_status": "programming_hint_ready"}

    def _create_interview(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingInterviewCreateInput.model_validate(state["payload"])
        result = self.service.create_interview(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "programming_interview_in_progress"}

    def _score_interview(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = ProgrammingInterviewAnswerInput.model_validate(
            {
                "question_id": state["payload"].get("question_id", ""),
                "answer_text": state["payload"].get("answer_text", ""),
            }
        )
        result = self.service.score_interview_answer(
            state["request"]["student_id"],
            str(state["payload"].get("session_id", "")),
            body,
        )
        return {"result": result, "lifecycle_status": "programming_interview_scored"}

    def _weekly_report(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.weekly_report(state["request"]["student_id"])
        return {"result": result, "lifecycle_status": "programming_weekly_report_ready"}

    @staticmethod
    def _unsupported(state: ProgrammingLearningState) -> dict[str, Any]:
        raise InputValidationError(f"编程学习 Agent 不支持意图：{state['intent']}")

    @staticmethod
    def _error_response(request: AgentRequest, code: str, message: str) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.PROGRAMMING_LEARNING,
            status=StandardStatus.FAILED,
            lifecycle_status="failed",
            errors=[ErrorDetail(code=code, message=message)],
        )
