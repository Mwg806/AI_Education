"""Progressive natural-language supervisor over the existing education agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from ai_education.domain.enums import ActorType, AgentRole, StandardStatus
from ai_education.domain.multi_agent import (
    AgentHandoff,
    EducationAgentState,
    LearningEventType,
    OrchestrationInput,
    OrchestrationResult,
    RoutingDecision,
)
from ai_education.domain.protocols import AgentRequest, Operator, utc_now
from ai_education.orchestration.intent_router import IntentRouter
from ai_education.services.shared.agent_execution_service import AgentExecutionService
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository

ERROR_TYPES = {
    LearningEventType.QUESTION_WRONG.value,
    LearningEventType.KNOWLEDGE_WEAK.value,
    LearningEventType.READING_ERROR.value,
    LearningEventType.GRAMMAR_ERROR.value,
    LearningEventType.WRITING_ERROR.value,
    LearningEventType.SPEAKING_ERROR.value,
}


class ProgressiveAgentOrchestrator:
    def __init__(
        self,
        intent_router: IntentRouter,
        execution_service: AgentExecutionService,
        profile_service: StudentProfileService,
        event_service: LearningEventService,
        repository: SharedLearningRepository,
    ) -> None:
        self.intent_router = intent_router
        self.execution_service = execution_service
        self.profile_service = profile_service
        self.event_service = event_service
        self.repository = repository
        self.graph = self._build_graph()

    async def orchestrate(
        self,
        user_id: str,
        body: OrchestrationInput,
        *,
        actor: Operator | None = None,
    ) -> OrchestrationResult:
        now = utc_now()
        run_id = f"agent_run_{uuid4().hex[:20]}"
        trace_id = f"trace_{uuid4().hex}"
        initial: EducationAgentState = {
            "run_id": run_id,
            "user_id": user_id,
            "session_id": body.session_id,
            "trace_id": trace_id,
            "messages": [{"role": "user", "content": body.message}],
            "current_task": {
                "message": body.message,
                "subject": body.subject,
                "context": body.context,
                "actor": (actor or Operator(type=ActorType.STUDENT, id=user_id)).model_dump(
                    mode="json"
                ),
            },
            "agent_results": {},
            "learning_events": [],
            "handoffs": [],
            "errors": [],
            "status": "running",
        }
        self._save_run(initial, created_at=now, updated_at=now)
        final = await self.graph.ainvoke(initial)
        routing = RoutingDecision.model_validate(final["routing"])
        profile = await self.profile_service.get_profile(user_id)
        result = OrchestrationResult(
            run_id=run_id,
            trace_id=trace_id,
            session_id=body.session_id,
            routing=routing,
            handoffs=[AgentHandoff.model_validate(item) for item in final.get("handoffs", [])],
            agent_results=final.get("agent_results", {}),
            final_response=final["final_response"],
            profile_version=profile.profile_version,
            event_count=len(final.get("learning_events", [])),
            status=final["status"],
        )
        completed = {**final, "result": result.model_dump(mode="json")}
        self._save_run(completed, created_at=now, updated_at=utc_now())
        return result

    def _build_graph(self):
        graph = StateGraph(EducationAgentState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("refresh_profile", self._refresh_profile)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "load_context")
        graph.add_edge("load_context", "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "refresh_profile")
        graph.add_edge("refresh_profile", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def _load_context(self, state: EducationAgentState) -> dict[str, Any]:
        profile = await self.profile_service.get_profile(state["user_id"])
        events = await self.event_service.get_recent_events(state["user_id"], 100)
        return {
            "user_profile": profile.model_dump(mode="json"),
            "retrieved_context": [item.model_dump(mode="json") for item in events],
            "learning_context": {
                "weak_points": profile.weak_points,
                "recent_learning_summary": profile.recent_learning_summary,
                "event_count": len(events),
            },
        }

    async def _route(self, state: EducationAgentState) -> dict[str, Any]:
        profile = await self.profile_service.get_profile(state["user_id"])
        task = state["current_task"]
        routing = await self.intent_router.route(task["message"], profile, task["context"])
        return {
            "intent": routing.intents,
            "routing": routing.model_dump(mode="json"),
            "confidence": routing.confidence,
        }

    async def _execute(self, state: EducationAgentState) -> dict[str, Any]:
        routing = RoutingDecision.model_validate(state["routing"])
        task = state["current_task"]
        actor = Operator.model_validate(task["actor"])
        results = dict(state.get("agent_results", {}))
        handoffs = list(state.get("handoffs", []))
        generated_events = list(state.get("learning_events", []))
        errors = list(state.get("errors", []))
        previous_role = AgentRole.SUPERVISOR
        diagnosis_result: dict[str, Any] | None = None

        for role in routing.required_agents:
            handoff = AgentHandoff(
                from_agent=previous_role,
                to_agent=role,
                reason=routing.reason
                if previous_role == AgentRole.SUPERVISOR
                else "传递上一步结构化结果",
                payload={
                    "intents": routing.intents,
                    "dependency_agents": list(results),
                },
            )
            handoffs.append(handoff.model_dump(mode="json"))
            request = self._agent_request(state, role, actor, diagnosis_result)
            if request is None:
                results[role.value] = {
                    "status": StandardStatus.NEED_MORE_INFORMATION.value,
                    "result": {
                        "message": "请先在对应学习模块建立会话或提交学习记录，再进行跨 Agent 分析。"
                    },
                }
                previous_role = role
                continue
            response, events = await self.execution_service.invoke(role, request, handoff=handoff)
            dumped = response.model_dump(mode="json")
            results[role.value] = dumped
            generated_events.extend(item.model_dump(mode="json") for item in events)
            if role == AgentRole.LEARNING_DIAGNOSIS and response.result:
                diagnosis_result = response.result
            if response.status not in {
                StandardStatus.SUCCESS,
                StandardStatus.PARTIAL_SUCCESS,
                StandardStatus.NEED_MORE_INFORMATION,
            }:
                errors.extend(item.model_dump(mode="json") for item in response.errors)
            previous_role = role
        return {
            "agent_results": results,
            "handoffs": handoffs,
            "learning_events": generated_events,
            "errors": errors,
        }

    def _agent_request(
        self,
        state: EducationAgentState,
        role: AgentRole,
        actor: Operator,
        diagnosis_result: dict[str, Any] | None,
    ) -> AgentRequest | None:
        task = state["current_task"]
        common = {
            "trace_id": state["trace_id"],
            "student_id": state["user_id"],
            "actor": actor,
            "context": {
                **task["context"],
                "session_id": state["session_id"],
                "orchestration_run_id": state["run_id"],
            },
            "idempotency_key": f"{state['run_id']}:{role.value}",
        }
        if role == AgentRole.LEARNING_DIAGNOSIS:
            records = self._diagnosis_records(state)
            if records:
                profile = state["user_profile"].get("basic_profile", {})
                payload = {
                    "student_id": state["user_id"],
                    "grade": profile.get("grade", "grade_12"),
                    "province_code": profile.get("province_code", "43"),
                    "subject": task["subject"],
                    "target_exam_year": int(profile.get("target_exam_year", 2027)),
                    "diagnosis_request": task["message"],
                    "diagnosis_window": "unified_recent_events",
                    "records": records,
                }
                return AgentRequest(intent="ingest_learning_evidence", payload=payload, **common)
            return AgentRequest(
                intent="get_learning_state",
                payload={"subject": task["subject"]},
                **common,
            )
        if role == AgentRole.PERSONALIZED_LEARNING_PLANNER:
            if diagnosis_result:
                return AgentRequest(
                    intent="apply_diagnosis_to_plan",
                    payload={
                        "diagnosis": diagnosis_result,
                        "student_request": task["message"],
                        "subject": task["subject"],
                    },
                    **common,
                )
            return AgentRequest(intent="get_plan", payload={"scope": "latest"}, **common)
        if role == AgentRole.ENGLISH_READING_LANGUAGE:
            return AgentRequest(intent="get_english_dashboard", payload={}, **common)
        if role == AgentRole.PROGRAMMING_LEARNING:
            return AgentRequest(intent="v1_dashboard", payload={}, **common)
        if role == AgentRole.HOMEWORK_TUTOR and task["context"].get("homework_session_id"):
            return AgentRequest(
                intent="get_homework_session",
                payload={"session_id": task["context"]["homework_session_id"]},
                **common,
            )
        return None

    @staticmethod
    def _diagnosis_records(state: EducationAgentState) -> list[dict[str, Any]]:
        subject = state["current_task"]["subject"]
        selected = [
            item
            for item in state.get("retrieved_context", [])
            if item.get("knowledge_point")
            and (not item.get("subject") or item.get("subject") == subject)
            and item.get("event_type")
            not in {
                LearningEventType.PLAN_UPDATED.value,
                LearningEventType.DIAGNOSIS_UPDATED.value,
            }
        ][:50]
        records: list[dict[str, Any]] = []
        for item in selected:
            metadata = item.get("metadata", {})
            is_error = item["event_type"] in ERROR_TYPES
            occurred = item.get("occurred_at")
            date_key = str(occurred)[:10] if occurred else "recent"
            records.append(
                {
                    "evidence_id": item["event_id"],
                    "assessment_id": str(
                        item.get("session_id") or f"unified-{date_key}-{item['event_id'][-6:]}"
                    )[:128],
                    "assessment_type": "homework"
                    if item.get("agent") == AgentRole.HOMEWORK_TUTOR.value
                    else "practice",
                    "question_id": str(metadata.get("source_item_id") or item["event_id"])[:128],
                    "knowledge_tags": [str(item["knowledge_point"])[:128]],
                    "question_type": str(
                        metadata.get("question_type")
                        or metadata.get("error_type")
                        or item["event_type"].lower()
                    )[:80],
                    "ability_tags": ["reading_comprehension"]
                    if item["event_type"] == LearningEventType.READING_ERROR.value
                    else [],
                    "difficulty": float(item.get("difficulty") or 0.5),
                    "score": float(
                        item["score"] if item.get("score") is not None else 0.0 if is_error else 1.0
                    ),
                    "max_score": 1.0,
                    "error_tags": [str(metadata.get("error_type") or "reading_error")[:80]]
                    if is_error
                    else [],
                    "source_id": item["event_id"],
                    "occurred_at": occurred,
                }
            )
        return records

    async def _refresh_profile(self, state: EducationAgentState) -> dict[str, Any]:
        summary = await self.event_service.summarize_recent_learning(state["user_id"])
        profile = await self.profile_service.get_profile(state["user_id"])
        return {
            "user_profile": profile.model_dump(mode="json"),
            "learning_context": {**state.get("learning_context", {}), "summary": summary},
        }

    @staticmethod
    def _finalize(state: EducationAgentState) -> dict[str, Any]:
        results = state.get("agent_results", {})
        parts: list[str] = []
        diagnosis = results.get(AgentRole.LEARNING_DIAGNOSIS.value, {}).get("result", {})
        narrative = diagnosis.get("diagnosis_report", {})
        if narrative.get("student_summary"):
            parts.append(str(narrative["student_summary"]))
        elif diagnosis.get("learning_state"):
            learning_state = diagnosis["learning_state"]
            weak = [
                item.get("dimension_label") or item.get("dimension_id")
                for item in learning_state.get("knowledge_states", [])
                if item.get("mastery_level") in {"needs_support", "developing"}
            ]
            parts.append(
                "诊断已完成。当前需要优先关注："
                + ("、".join(weak[:4]) if weak else "证据仍不足，需要继续积累作答记录")
                + "。"
            )
        planner = results.get(AgentRole.PERSONALIZED_LEARNING_PLANNER.value, {}).get("result", {})
        adaptation = planner.get("plan_adaptation", {})
        if adaptation.get("student_message"):
            parts.append(str(adaptation["student_message"]))
        for role in (
            AgentRole.ENGLISH_READING_LANGUAGE,
            AgentRole.PROGRAMMING_LEARNING,
            AgentRole.HOMEWORK_TUTOR,
        ):
            item = results.get(role.value, {})
            if item.get("result", {}).get("message"):
                parts.append(str(item["result"]["message"]))
        if not parts:
            parts.append("已完成意图识别，但现有学习证据不足。请先完成或提交一次对应练习。")
        statuses = [item.get("status") for item in results.values()]
        status = (
            "failed"
            if statuses and all(item == StandardStatus.FAILED.value for item in statuses)
            else "partial_success"
            if any(
                item not in {StandardStatus.SUCCESS.value, StandardStatus.PARTIAL_SUCCESS.value}
                for item in statuses
            )
            else "success"
        )
        return {"final_response": "\n\n".join(parts), "status": status}

    def _save_run(
        self,
        state: EducationAgentState,
        *,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self.repository.save_run(
            {
                "run_id": state["run_id"],
                "user_id": state["user_id"],
                "session_id": state["session_id"],
                "trace_id": state["trace_id"],
                "status": state.get("status", "running"),
                "routing": state.get("routing"),
                "result": state.get("result"),
                "payload": dict(state),
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
