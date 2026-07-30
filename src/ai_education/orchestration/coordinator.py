"""Dependency-aware LangGraph supervisor for six or more education agents."""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ai_education.core.errors import AgentNotFoundError, InputValidationError
from ai_education.domain.enums import AgentRole, MessageType, StandardStatus
from ai_education.domain.protocols import (
    AgentMessage,
    AgentRequest,
    AgentResponse,
    CollaborationRequest,
    CollaborationResponse,
    ErrorDetail,
)
from ai_education.orchestration.aggregator import ResultAggregator
from ai_education.orchestration.bus import AgentMessageBus
from ai_education.orchestration.global_state import GlobalStateStore
from ai_education.orchestration.registry import AgentRegistry


class CoordinatorState(TypedDict, total=False):
    request: dict[str, Any]
    routes: dict[str, str]
    state_revision: int
    global_state: dict[str, Any]
    task_results: dict[str, dict[str, Any]]
    aggregate: dict[str, Any]
    status: str
    evidence: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    next_revision: int


class MultiAgentCoordinator:
    """Route, execute, aggregate and synchronize a collaboration DAG."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        bus: AgentMessageBus | None = None,
        state_store: GlobalStateStore | None = None,
        max_parallelism: int = 8,
    ) -> None:
        self.registry = registry
        self.bus = bus or AgentMessageBus()
        self.state_store = state_store or GlobalStateStore()
        self.aggregator = ResultAggregator()
        self.max_parallelism = max(max_parallelism, 1)
        self.graph = self._build_graph()

    async def coordinate(self, request: CollaborationRequest) -> CollaborationResponse:
        final = await self.graph.ainvoke({"request": request.model_dump(mode="json")})
        return CollaborationResponse(
            collaboration_id=request.collaboration_id,
            trace_id=request.trace_id,
            student_id=request.student_id,
            status=StandardStatus(final["status"]),
            task_results={
                task_id: AgentResponse.model_validate(response)
                for task_id, response in final["task_results"].items()
            },
            aggregate=final["aggregate"],
            evidence=final.get("evidence", []),
            warnings=final.get("warnings", []),
            errors=final.get("errors", []),
            global_state_revision=final["next_revision"],
        )

    def _build_graph(self):
        graph = StateGraph(CoordinatorState)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("aggregate", self._aggregate)
        graph.add_node("sync", self._sync)
        graph.add_edge(START, "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "aggregate")
        graph.add_edge("aggregate", "sync")
        graph.add_edge("sync", END)
        return graph.compile()

    def _route(self, state: CoordinatorState) -> dict[str, Any]:
        request = CollaborationRequest.model_validate(state["request"])
        self._assert_acyclic(request)
        routes: dict[str, str] = {}
        for task in request.tasks:
            if task.preferred_agent:
                agent = self.registry.get(task.preferred_agent)
                if not agent.supports(task.intent):
                    raise AgentNotFoundError(
                        f"指定 Agent 不支持意图 {task.intent}",
                        details={"agent": task.preferred_agent, "task_id": task.task_id},
                    )
            else:
                candidates = self.registry.find_by_intent(task.intent)
                if len(candidates) != 1:
                    raise AgentNotFoundError(
                        "无法唯一确定任务接收 Agent",
                        details={"task_id": task.task_id, "candidate_count": len(candidates)},
                    )
                agent = candidates[0]
            routes[task.task_id] = agent.metadata.role
        revision, global_state = self.state_store.read(request.student_id)
        return {"routes": routes, "state_revision": revision, "global_state": global_state}

    async def _execute(self, state: CoordinatorState) -> dict[str, Any]:
        request = CollaborationRequest.model_validate(state["request"])
        routes = {task_id: AgentRole(role) for task_id, role in state["routes"].items()}
        tasks = {task.task_id: task for task in request.tasks}
        pending = set(tasks)
        results: dict[str, AgentResponse] = {}
        semaphore = asyncio.Semaphore(self.max_parallelism)

        async def invoke(task_id: str) -> tuple[str, AgentResponse]:
            task = tasks[task_id]
            role = routes[task_id]
            agent = self.registry.get(role)
            dependency_results = {
                dependency: results[dependency].result for dependency in task.depends_on
            }
            agent_request = AgentRequest(
                trace_id=request.trace_id,
                student_id=request.student_id,
                actor=request.actor,
                intent=task.intent,
                payload=task.payload,
                context={
                    **request.context,
                    "global_state": state.get("global_state", {}),
                    "dependency_results": dependency_results,
                },
                idempotency_key=f"{request.collaboration_id}:{task_id}",
                data_version=request.data_version,
            )
            await self.bus.publish(
                AgentMessage(
                    trace_id=request.trace_id,
                    correlation_id=request.collaboration_id,
                    message_type=MessageType.COMMAND,
                    sender=AgentRole.SUPERVISOR,
                    recipient=role,
                    student_id=request.student_id,
                    payload={"task_id": task_id, "intent": task.intent},
                )
            )
            async with semaphore:
                response = await agent.ainvoke(agent_request)
            await self.bus.publish(
                AgentMessage(
                    trace_id=request.trace_id,
                    correlation_id=request.collaboration_id,
                    message_type=MessageType.RESULT,
                    sender=role,
                    recipient=AgentRole.SUPERVISOR,
                    student_id=request.student_id,
                    payload={"task_id": task_id, "status": response.status},
                    evidence=response.evidence,
                )
            )
            return task_id, response

        while pending:
            ready = sorted(
                task_id for task_id in pending if tasks[task_id].depends_on <= results.keys()
            )
            if not ready:
                raise InputValidationError("协作任务依赖无法推进")
            runnable = []
            for task_id in ready:
                failed_dependencies = [
                    dependency
                    for dependency in tasks[task_id].depends_on
                    if results[dependency].status
                    not in {StandardStatus.SUCCESS, StandardStatus.PARTIAL_SUCCESS}
                ]
                if failed_dependencies and tasks[task_id].required:
                    results[task_id] = self._skipped_response(
                        request, routes[task_id], task_id, failed_dependencies
                    )
                else:
                    runnable.append(task_id)
            executed = await asyncio.gather(*(invoke(task_id) for task_id in runnable))
            results.update(dict(executed))
            pending.difference_update(ready)
        return {
            "task_results": {
                task_id: response.model_dump(mode="json") for task_id, response in results.items()
            }
        }

    def _aggregate(self, state: CoordinatorState) -> dict[str, Any]:
        results = {
            task_id: AgentResponse.model_validate(response)
            for task_id, response in state["task_results"].items()
        }
        status, aggregate, evidence, warnings, errors = self.aggregator.aggregate(results)
        return {
            "status": status,
            "aggregate": aggregate,
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "warnings": [item.model_dump(mode="json") for item in warnings],
            "errors": [item.model_dump(mode="json") for item in errors],
        }

    async def _sync(self, state: CoordinatorState) -> dict[str, Any]:
        request = CollaborationRequest.model_validate(state["request"])
        updates: dict[str, Any] = {
            "agent_results": state["aggregate"]["agent_results"],
            "last_collaboration_id": request.collaboration_id,
            "last_trace_id": request.trace_id,
        }
        for task_result in state["aggregate"]["agent_results"].values():
            result = task_result.get("result", {})
            for key in (
                "student_profile",
                "exam_profile",
                "knowledge_profile",
                "time_profile",
                "plan",
                "session",
                "question",
                "planner_feedback",
            ):
                if key in result:
                    updates[key] = result[key]
        revision, _ = self.state_store.compare_and_swap(
            request.student_id,
            expected_revision=state["state_revision"],
            updates=updates,
        )
        await self.bus.publish(
            AgentMessage(
                trace_id=request.trace_id,
                correlation_id=request.collaboration_id,
                message_type=MessageType.STATE_SYNC,
                sender=AgentRole.SUPERVISOR,
                student_id=request.student_id,
                payload={"global_state_revision": revision},
            )
        )
        return {"next_revision": revision}

    @staticmethod
    def _assert_acyclic(request: CollaborationRequest) -> None:
        dependencies = {task.task_id: set(task.depends_on) for task in request.tasks}
        resolved: set[str] = set()
        while dependencies:
            ready = {task_id for task_id, needs in dependencies.items() if needs <= resolved}
            if not ready:
                raise InputValidationError("协作任务存在循环依赖")
            resolved.update(ready)
            for task_id in ready:
                dependencies.pop(task_id)

    @staticmethod
    def _skipped_response(
        request: CollaborationRequest,
        role: AgentRole,
        task_id: str,
        failed_dependencies: list[str],
    ) -> AgentResponse:
        return AgentResponse(
            request_id=f"skipped_{task_id}",
            trace_id=request.trace_id,
            agent_role=role,
            status=StandardStatus.FAILED,
            lifecycle_status="FAILED",
            errors=[
                ErrorDetail(
                    code="DEPENDENCY_FAILED",
                    message="依赖任务未成功，已阻止该任务执行",
                    details={"failed_dependencies": failed_dependencies},
                )
            ],
            data_version=request.data_version,
        )
