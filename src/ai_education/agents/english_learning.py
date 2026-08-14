"""LangGraph Agent for National I English reading and language learning."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.domain.english_learning import (
    EnglishLearnerProfileInput,
    EnglishReadingHintInput,
    EnglishReviewCompletionInput,
    EnglishTaskInput,
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
)
from ai_education.domain.enums import AgentRole, StandardStatus
from ai_education.domain.protocols import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ErrorDetail,
    Evidence,
)
from ai_education.services.english_learning import EnglishLearningService
from ai_education.tools.english_learning import EnglishLearningToolbox


class EnglishLearningState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    profile: dict[str, Any]
    next_node: str
    result: dict[str, Any]
    lifecycle_status: str


class EnglishReadingLanguageAgent(BaseEducationAgent):
    def __init__(self, service: EnglishLearningService) -> None:
        self.service = service
        self.repository = service.repository
        self.toolbox = EnglishLearningToolbox()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="english_reading_language_agent",
            role=AgentRole.ENGLISH_READING_LANGUAGE,
            version="2.0.0",
            description="只面向新高考全国Ⅰ卷考生的阅读、词汇、语法、写作与文本口语主控智能体",
            capabilities={
                "english_text_analysis",
                "curriculum_grounded_retrieval",
                "reading_multiple_choice",
                "seven_of_five",
                "evidence_location",
                "distractor_diagnosis",
                "four_level_reading_hints",
                "mastery_tracking",
                "spaced_review",
                "intent_routing",
                "vocabulary_notebook",
                "grammar_correction",
                "writing_revision",
                "translation",
                "text_speaking_practice",
                "learner_profile",
                "weekly_report",
                "record_deletion",
            },
            accepted_intents={
                "analyze_english_text",
                "create_english_training",
                "submit_english_training",
                "get_english_reading_hint",
                "get_english_dashboard",
                "complete_english_review",
                "execute_english_language_task",
                "update_english_learner_profile",
                "delete_english_learning_record",
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
                    "profile": {
                        **request.context.get("student_profile", {}),
                        "unified_student_profile": request.context.get(
                            "unified_student_profile", {}
                        ),
                        "recent_learning_events": request.context.get("recent_learning_events", [])[
                            -20:
                        ],
                    },
                    "lifecycle_status": "received",
                }
            )
            references = final.get("result", {}).get("source_references", [])
            response = AgentResponse(
                request_id=request.request_id,
                trace_id=request.trace_id,
                agent_role=self.metadata.role,
                status=StandardStatus.SUCCESS,
                lifecycle_status=final.get("lifecycle_status", "completed"),
                result=final.get("result", {}),
                evidence=[
                    Evidence(
                        source_type="english_curriculum_knowledge",
                        source_id=item["source_id"],
                        description=f"{item['title']} · 第 {item.get('page_start') or '待核验'} 页",
                        confidence=0.9 if item.get("authority_level") == "A" else 0.75,
                    )
                    for item in references[:5]
                ],
            )
        except (ValidationError, InputValidationError) as exc:
            message = (
                exc.message
                if isinstance(exc, InputValidationError)
                else "英语学习输入未通过结构校验"
            )
            response = self._error_response(request, "ENGLISH_INPUT_INVALID", message)
        except AIEducationError as exc:
            response = self._error_response(request, exc.code, exc.message)
        except Exception:
            response = self._error_response(
                request,
                "UNEXPECTED_ENGLISH_AGENT_ERROR",
                "英语学习流程出现未预期错误，未写入未经验证的能力结论",
            )
        self.repository.put_idempotent(request.idempotency_key, response.model_dump(mode="json"))
        return response

    def _build_graph(self):
        graph = StateGraph(EnglishLearningState)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("analyze", self._analyze)
        graph.add_node("create_training", self._create_training)
        graph.add_node("submit_training", self._submit_training)
        graph.add_node("reading_hint", self._reading_hint)
        graph.add_node("dashboard", self._dashboard)
        graph.add_node("complete_review", self._complete_review)
        graph.add_node("execute_task", self._execute_task)
        graph.add_node("update_profile", self._update_profile)
        graph.add_node("delete_record", self._delete_record)
        graph.add_node("unsupported", self._unsupported)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            lambda state: state["next_node"],
            {
                "analyze": "analyze",
                "create_training": "create_training",
                "submit_training": "submit_training",
                "reading_hint": "reading_hint",
                "dashboard": "dashboard",
                "complete_review": "complete_review",
                "execute_task": "execute_task",
                "update_profile": "update_profile",
                "delete_record": "delete_record",
                "unsupported": "unsupported",
            },
        )
        for node in (
            "analyze",
            "create_training",
            "submit_training",
            "reading_hint",
            "dashboard",
            "complete_review",
            "execute_task",
            "update_profile",
            "delete_record",
            "unsupported",
        ):
            graph.add_edge(node, END)
        return graph.compile()

    @staticmethod
    def _dispatch(state: EnglishLearningState) -> dict[str, Any]:
        routes = {
            "analyze_english_text": "analyze",
            "create_english_training": "create_training",
            "submit_english_training": "submit_training",
            "get_english_reading_hint": "reading_hint",
            "get_english_dashboard": "dashboard",
            "complete_english_review": "complete_review",
            "execute_english_language_task": "execute_task",
            "update_english_learner_profile": "update_profile",
            "delete_english_learning_record": "delete_record",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _analyze(self, state: EnglishLearningState) -> dict[str, Any]:
        body = EnglishTextAnalysisInput.model_validate(state["payload"])
        result = self.service.analyze(state["request"]["student_id"], body, state["profile"])
        return {"result": result, "lifecycle_status": "analysis_ready"}

    async def _create_training(self, state: EnglishLearningState) -> dict[str, Any]:
        body = EnglishTrainingCreateInput.model_validate(state["payload"])
        result = await self.service.create_training(
            state["request"]["student_id"], body, state["profile"]
        )
        return {"result": result, "lifecycle_status": "training_in_progress"}

    def _submit_training(self, state: EnglishLearningState) -> dict[str, Any]:
        session_id = str(state["payload"].get("session_id", ""))
        body = EnglishTrainingSubmissionInput.model_validate(
            {"answers": state["payload"].get("answers", [])}
        )
        result = self.service.submit_training(state["request"]["student_id"], session_id, body)
        return {"result": result, "lifecycle_status": "training_completed"}

    def _reading_hint(self, state: EnglishLearningState) -> dict[str, Any]:
        session_id = str(state["payload"].get("session_id", ""))
        body = EnglishReadingHintInput.model_validate(
            {
                "question_id": state["payload"].get("question_id"),
                "level": state["payload"].get("level"),
            }
        )
        result = self.service.reading_hint(state["request"]["student_id"], session_id, body)
        return {"result": result, "lifecycle_status": "reading_hint_released"}

    def _dashboard(self, state: EnglishLearningState) -> dict[str, Any]:
        result = self.service.dashboard(state["request"]["student_id"], state["profile"])
        return {"result": result, "lifecycle_status": "profile_ready"}

    def _complete_review(self, state: EnglishLearningState) -> dict[str, Any]:
        review_id = str(state["payload"].get("review_id", ""))
        body = EnglishReviewCompletionInput.model_validate(
            {"result": state["payload"].get("result")}
        )
        result = self.service.complete_review(
            state["request"]["student_id"], review_id, body.result
        )
        return {"result": result, "lifecycle_status": "review_completed"}

    async def _execute_task(self, state: EnglishLearningState) -> dict[str, Any]:
        body = EnglishTaskInput.model_validate(state["payload"])
        result = await self.service.execute_task(
            state["request"]["student_id"], body, state["profile"]
        )
        return {"result": result, "lifecycle_status": "language_task_completed"}

    def _update_profile(self, state: EnglishLearningState) -> dict[str, Any]:
        body = EnglishLearnerProfileInput.model_validate(state["payload"])
        result = self.service.update_learner_profile(
            state["request"]["student_id"], body, state["profile"]
        )
        return {"result": result, "lifecycle_status": "learner_profile_updated"}

    def _delete_record(self, state: EnglishLearningState) -> dict[str, Any]:
        result = self.service.delete_learning_record(
            state["request"]["student_id"],
            str(state["payload"].get("record_type", "")),
            str(state["payload"].get("record_id", "")),
        )
        return {"result": result, "lifecycle_status": "learning_record_deleted"}

    @staticmethod
    def _unsupported(state: EnglishLearningState) -> dict[str, Any]:
        raise InputValidationError(f"英语学习 Agent 不支持意图：{state['intent']}")

    def _error_response(self, request: AgentRequest, code: str, message: str) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=self.metadata.role,
            status=StandardStatus.FAILED,
            lifecycle_status="failed",
            errors=[ErrorDetail(code=code, message=message)],
        )
