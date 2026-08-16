"""Progressive natural-language supervisor over the existing education agents."""

from __future__ import annotations

import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from ai_education.domain.enums import ActorType, AgentRole, StandardStatus
from ai_education.domain.multi_agent import (
    AgentHandoff,
    AgentTask,
    CollaborationMemorySnapshot,
    EducationAgentState,
    OrchestrationInput,
    OrchestrationPlan,
    OrchestrationResult,
    ProfileChange,
    RoutingDecision,
    UnifiedStudentProfile,
)
from ai_education.domain.protocols import Operator, utc_now
from ai_education.orchestration.capability_adapters import (
    AdapterContext,
    CapabilityAdapterRegistry,
)
from ai_education.orchestration.intent_router import IntentRouter
from ai_education.services.shared.academic_integrity_policy import AcademicIntegrityPolicy
from ai_education.services.shared.agent_execution_service import AgentExecutionService
from ai_education.services.shared.collaboration_memory_service import CollaborationMemoryService
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.response_synthesizer import ResponseSynthesizer
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository

SUCCESS_STATUSES = {StandardStatus.SUCCESS.value, StandardStatus.PARTIAL_SUCCESS.value}


class ProgressiveAgentOrchestrator:
    def __init__(
        self,
        intent_router: IntentRouter,
        execution_service: AgentExecutionService,
        profile_service: StudentProfileService,
        event_service: LearningEventService,
        repository: SharedLearningRepository,
        adapter_registry: CapabilityAdapterRegistry | None = None,
    ) -> None:
        self.intent_router = intent_router
        self.execution_service = execution_service
        self.profile_service = profile_service
        self.event_service = event_service
        self.repository = repository
        self.response_synthesizer = ResponseSynthesizer(execution_service.model_router)
        self.academic_integrity = AcademicIntegrityPolicy()
        self.collaboration_memory_service = CollaborationMemoryService(repository)
        self.adapters = adapter_registry or CapabilityAdapterRegistry()
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
        operator = actor or Operator(type=ActorType.STUDENT, id=user_id)
        policy = self.academic_integrity.inspect(body.message)
        collaboration_memory: CollaborationMemorySnapshot | None = None
        memory_context: dict[str, Any] = {}
        if operator.type == ActorType.STUDENT:
            initial_profile = await self.profile_service.get_profile(user_id)
            initial_events = await self.event_service.get_recent_events(user_id, 300)
            collaboration_memory = await self.collaboration_memory_service.begin_interaction(
                user_id=user_id,
                session_id=body.session_id,
                run_id=run_id,
                message=body.message,
                subject=body.subject,
                profile=initial_profile,
                recent_events=initial_events,
                extract_profile_signals=not policy.blocked,
            )
            memory_context = self.collaboration_memory_service.context_for_agents(
                collaboration_memory
            )
        initial: EducationAgentState = {
            "run_id": run_id,
            "user_id": user_id,
            "session_id": body.session_id,
            "trace_id": trace_id,
            "messages": [{"role": "user", "content": body.message}],
            "current_task": {
                "message": body.message,
                "subject": body.subject,
                "context": {**body.context, "collaboration_memory": memory_context},
                "actor": operator.model_dump(mode="json"),
            },
            "agent_results": {},
            "task_results": {},
            "learning_events": [],
            "handoffs": [],
            "errors": [],
            "collaboration_memory": (
                collaboration_memory.model_dump(mode="json") if collaboration_memory else {}
            ),
            "status": "running",
        }
        self._save_run(initial, created_at=now, updated_at=now)
        if operator.type == ActorType.STUDENT and policy.blocked:
            result = await self._academic_integrity_result(
                initial, body, operator, policy.code, policy.message
            )
            result = await self._complete_collaboration_memory(result, collaboration_memory, body)
            completed = {
                **initial,
                "status": result.status,
                "result": result.model_dump(mode="json"),
            }
            self._save_run(completed, created_at=now, updated_at=utc_now())
            return result
        final = await self.graph.ainvoke(initial)
        routing = RoutingDecision.model_validate(final["routing"])
        plan = OrchestrationPlan.model_validate(final["orchestration_plan"])
        profile = (
            await self.profile_service.get_profile(user_id)
            if operator.type == ActorType.STUDENT
            else UnifiedStudentProfile(
                user_id=user_id, basic_profile={"actor_type": operator.type.value}
            )
        )
        changes = (
            self._profile_changes(final.get("initial_profile", {}), profile)
            if operator.type == ActorType.STUDENT
            else []
        )
        requires_confirmation, confirmation = self._confirmation(final.get("task_results", {}))
        result = OrchestrationResult(
            run_id=run_id,
            trace_id=trace_id,
            session_id=body.session_id,
            routing=routing,
            plan=plan,
            handoffs=[AgentHandoff.model_validate(item) for item in final.get("handoffs", [])],
            agent_results=final.get("agent_results", {}),
            task_results=final.get("task_results", {}),
            final_response=final["final_response"],
            response_generation_mode=final.get("response_generation_mode", "rule_summary"),
            profile_version=profile.profile_version,
            profile_changes=changes,
            event_count=len(final.get("learning_events", [])),
            requires_confirmation=requires_confirmation,
            confirmation=confirmation,
            status=final["status"],
            evidence_summary=(
                collaboration_memory.source_summary.get("cross_module_evidence", {})
                if collaboration_memory
                else {}
            ),
        )
        result = await self._complete_collaboration_memory(result, collaboration_memory, body)
        completed = {**final, "status": result.status, "result": result.model_dump(mode="json")}
        self._save_run(completed, created_at=now, updated_at=utc_now())
        return result

    async def _complete_collaboration_memory(
        self,
        result: OrchestrationResult,
        snapshot: CollaborationMemorySnapshot | None,
        body: OrchestrationInput,
    ) -> OrchestrationResult:
        if snapshot is None:
            return result
        updated = await self.collaboration_memory_service.record_response(
            snapshot,
            session_id=body.session_id,
            run_id=result.run_id,
            subject=body.subject,
            response=result.final_response,
            status=result.status,
            agents=[item.value for item in result.routing.required_agents],
        )
        profile = await self.profile_service.update_profile(
            snapshot.user_id,
            self.collaboration_memory_service.profile_projection(updated),
        )
        sources = ["explicit_user_input", "unified_student_profile"]
        if updated.source_summary.get("learning_event_count", 0):
            sources.append("unified_learning_events")
        if updated.interaction_count > 1:
            sources.append("collaboration_history")
        return result.model_copy(
            update={
                "profile_version": profile.profile_version,
                "personalization_mode": snapshot.personalization_mode,
                "memory_version": updated.memory_version,
                "memory_sources": sources,
            }
        )

    async def _academic_integrity_result(
        self,
        initial: EducationAgentState,
        body: OrchestrationInput,
        operator: Operator,
        code: str,
        message: str,
    ) -> OrchestrationResult:
        profile = await self.profile_service.get_profile(initial["user_id"])
        routing = RoutingDecision(
            intents=["academic_integrity_judgment_only"],
            primary_agent=AgentRole.SUPERVISOR,
            required_agents=[AgentRole.SUPERVISOR],
            execution_mode="single",
            reason="请求涉及可直接提交的作业内容，先执行学术诚信边界判断",
            confidence=1.0,
        )
        task = AgentTask(
            agent=AgentRole.SUPERVISOR,
            intent="enforce_academic_integrity",
            objective="阻止代写和直接答案请求，并引导学生提交自己的尝试供判断",
            subject=body.subject,
            payload={"policy_code": code, "actor_type": operator.type.value},
            status="success",
            status_message="已执行学术诚信边界：仅提供判断、诊断和渐进提示",
            latency_ms=0,
        )
        plan = OrchestrationPlan(
            goal="在不替学生完成作业的前提下提供学习判断",
            execution_mode="single",
            tasks=[task],
            stop_conditions=["不得生成最终答案、完整解题过程或可直接提交内容"],
        )
        task_result = {
            "agent_role": AgentRole.SUPERVISOR.value,
            "status": StandardStatus.SUCCESS.value,
            "lifecycle_status": "policy_enforced",
            "result": {"message": message, "policy_code": code},
            "warnings": [
                {
                    "code": code,
                    "message": "智能协作不提供代写或可直接提交的答案",
                }
            ],
            "errors": [],
        }
        return OrchestrationResult(
            run_id=initial["run_id"],
            trace_id=initial["trace_id"],
            session_id=body.session_id,
            routing=routing,
            plan=plan,
            task_results={task.task_id: task_result},
            agent_results={AgentRole.SUPERVISOR.value: task_result},
            final_response=message,
            response_generation_mode="rule_summary",
            profile_version=profile.profile_version,
            event_count=0,
            status=StandardStatus.SUCCESS.value,
        )

    def _build_graph(self):
        graph = StateGraph(EducationAgentState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("route", self._route)
        graph.add_node("build_plan", self._build_plan)
        graph.add_node("execute", self._execute)
        graph.add_node("refresh_profile", self._refresh_profile)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "load_context")
        graph.add_edge("load_context", "route")
        graph.add_edge("route", "build_plan")
        graph.add_edge("build_plan", "execute")
        graph.add_edge("execute", "refresh_profile")
        graph.add_edge("refresh_profile", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def _load_context(self, state: EducationAgentState) -> dict[str, Any]:
        actor = Operator.model_validate(state["current_task"]["actor"])
        if actor.type == ActorType.STUDENT:
            profile = await self.profile_service.get_profile(state["user_id"])
            events = await self.event_service.get_recent_events(state["user_id"], 300)
        else:
            profile = UnifiedStudentProfile(
                user_id=state["user_id"], basic_profile={"actor_type": actor.type.value}
            )
            events = []
        dumped = profile.model_dump(mode="json")
        cross_module_evidence = self.collaboration_memory_service.cross_module_evidence(events)
        return {
            "initial_profile": dumped,
            "user_profile": dumped,
            "retrieved_context": [item.model_dump(mode="json") for item in events],
            "learning_context": {
                "weak_points": profile.weak_points,
                "recent_learning_summary": profile.recent_learning_summary,
                "event_count": len(events),
                "cross_module_evidence": cross_module_evidence,
                "collaboration_memory": state.get("collaboration_memory", {}),
            },
        }

    async def _route(self, state: EducationAgentState) -> dict[str, Any]:
        profile = UnifiedStudentProfile.model_validate(state["user_profile"])
        task = state["current_task"]
        actor = Operator.model_validate(task["actor"])
        routing = await self.intent_router.route(
            task["message"], profile, {**task["context"], "actor_type": actor.type.value}
        )
        return {
            "intent": routing.intents,
            "routing": routing.model_dump(mode="json"),
            "confidence": routing.confidence,
        }

    def _adapter_context(
        self, state: EducationAgentState, *, subject: str | None = None
    ) -> AdapterContext:
        task = state["current_task"]
        return AdapterContext(
            user_id=state["user_id"],
            message=task["message"],
            subject=subject or task["subject"],
            request_context=task["context"],
            profile=UnifiedStudentProfile.model_validate(state["user_profile"]),
            actor=Operator.model_validate(task["actor"]),
        )

    def _build_plan(self, state: EducationAgentState) -> dict[str, Any]:
        routing = RoutingDecision.model_validate(state["routing"])
        plan = self.adapters.build_plan(routing, self._adapter_context(state))
        registered = self.execution_service.registry
        checked: list[AgentTask] = []
        for task in plan.tasks:
            agent = registered.get(task.agent)
            if not agent.supports(task.intent):
                checked.append(
                    task.model_copy(
                        update={
                            "status": "failed",
                            "status_message": (
                                f"{task.agent.value} 未声明支持原生意图 {task.intent}"
                            ),
                        }
                    )
                )
            else:
                checked.append(task)
        plan = plan.model_copy(update={"tasks": checked})
        return {"orchestration_plan": plan.model_dump(mode="json")}

    async def _execute(self, state: EducationAgentState) -> dict[str, Any]:
        plan = OrchestrationPlan.model_validate(state["orchestration_plan"])
        task_map = {item.task_id: item for item in plan.tasks}
        pending = set(task_map)
        task_results: dict[str, dict[str, Any]] = {}
        agent_results: dict[str, dict[str, Any]] = {}
        handoffs: list[dict[str, Any]] = []
        generated_events: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        completed_tasks: dict[str, AgentTask] = {}

        while pending:
            ready = sorted(
                task_id
                for task_id in pending
                if set(task_map[task_id].depends_on) <= task_results.keys()
            )
            if not ready:
                for task_id in sorted(pending):
                    completed_tasks[task_id] = task_map[task_id].model_copy(
                        update={"status": "failed", "status_message": "任务依赖无法推进"}
                    )
                    task_results[task_id] = self._synthetic_result(
                        task_map[task_id], "failed", "任务依赖无法推进"
                    )
                break

            runnable: list[str] = []
            for task_id in ready:
                task = task_map[task_id]
                if task.status == "failed":
                    completed_tasks[task_id] = task
                    task_results[task_id] = self._synthetic_result(
                        task, "failed", task.status_message
                    )
                    continue
                failed_dependencies = [
                    dependency
                    for dependency in task.depends_on
                    if task_results[dependency].get("status") not in SUCCESS_STATUSES
                ]
                if failed_dependencies and task.required:
                    message = "依赖任务未成功：" + "、".join(failed_dependencies)
                    completed_tasks[task_id] = task.model_copy(
                        update={"status": "skipped", "status_message": message}
                    )
                    task_results[task_id] = self._synthetic_result(task, "skipped", message)
                    continue
                if task.missing_context:
                    message = task.missing_context[0].prompt
                    completed_tasks[task_id] = task.model_copy(
                        update={"status": "needs_input", "status_message": message}
                    )
                    task_results[task_id] = self._synthetic_result(
                        task,
                        StandardStatus.NEED_MORE_INFORMATION.value,
                        message,
                        missing=[item.model_dump(mode="json") for item in task.missing_context],
                    )
                    continue
                runnable.append(task_id)

            outcomes = await asyncio.gather(
                *(self._invoke_task(state, task_map[item], task_results) for item in runnable)
            )
            for task_id, task, result, events, handoff, caught_errors in outcomes:
                completed_tasks[task_id] = task
                task_results[task_id] = result
                generated_events.extend(events)
                handoffs.append(handoff)
                errors.extend(caught_errors)
                role_key = task.agent.value
                if role_key in agent_results:
                    role_key = f"{role_key}:{task.subject or task_id[-6:]}"
                agent_results[role_key] = result
            pending.difference_update(ready)

        final_tasks = [completed_tasks.get(item.task_id, item) for item in plan.tasks]
        updated_plan = plan.model_copy(update={"tasks": final_tasks})
        return {
            "orchestration_plan": updated_plan.model_dump(mode="json"),
            "agent_results": agent_results,
            "task_results": task_results,
            "handoffs": handoffs,
            "learning_events": generated_events,
            "errors": errors,
        }

    async def _invoke_task(
        self,
        state: EducationAgentState,
        task: AgentTask,
        task_results: dict[str, dict[str, Any]],
    ) -> tuple[
        str, AgentTask, dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]
    ]:
        dependency_results = {key: task_results[key] for key in task.depends_on}
        from_agent = AgentRole.SUPERVISOR
        if task.depends_on:
            from_agent = AgentRole(task_map_agent(task.depends_on[-1], state["orchestration_plan"]))
        handoff = AgentHandoff(
            from_agent=from_agent,
            to_agent=task.agent,
            reason=(
                "总编排器根据用户目标分派原生能力任务"
                if not task.depends_on
                else "传递已验证的上游结构化结果"
            ),
            payload={
                "task_id": task.task_id,
                "intent": task.intent,
                "depends_on": task.depends_on,
                "subject": task.subject,
            },
        )
        context = self._adapter_context(state, subject=task.subject)
        request = self.adapters.build_request(
            task,
            context,
            dependency_results,
            state.get("retrieved_context", []),
            trace_id=state["trace_id"],
            run_id=state["run_id"],
            session_id=state["session_id"],
        )
        if task.agent == AgentRole.LEARNING_DIAGNOSIS and not request.payload.get("records"):
            message = (
                "当前没有足够的真实作答记录，暂时不能判断薄弱点。请先完成至少 3 次独立练习或诊断。"
            )
            completed = task.model_copy(
                update={"status": "needs_input", "status_message": message, "latency_ms": 0}
            )
            return (
                task.task_id,
                completed,
                self._synthetic_result(
                    task,
                    StandardStatus.NEED_MORE_INFORMATION.value,
                    message,
                    missing=[
                        {
                            "field": "learning_evidence",
                            "prompt": message,
                            "reason": "诊断结论必须来自独立、可核验学习证据",
                            "accepted_sources": ["作业提交", "英语阅读", "代码练习", "诊断卷"],
                        }
                    ],
                ),
                [],
                handoff.model_dump(mode="json"),
                [],
            )
        started = perf_counter()
        try:
            response, events = await self.execution_service.invoke(
                task.agent, request, handoff=handoff
            )
            status_map = {
                StandardStatus.SUCCESS: "success",
                StandardStatus.PARTIAL_SUCCESS: "partial_success",
                StandardStatus.NEED_MORE_INFORMATION: "needs_input",
            }
            completed = task.model_copy(
                update={
                    "status": status_map.get(response.status, "failed"),
                    "status_message": self._result_message(response.model_dump(mode="json")),
                    "latency_ms": max(0, int((perf_counter() - started) * 1_000)),
                }
            )
            return (
                task.task_id,
                completed,
                response.model_dump(mode="json"),
                [item.model_dump(mode="json") for item in events],
                handoff.model_dump(mode="json"),
                [item.model_dump(mode="json") for item in response.errors],
            )
        except Exception as exc:
            message = f"{task.agent.value} 执行失败：{type(exc).__name__}"
            completed = task.model_copy(
                update={
                    "status": "failed",
                    "status_message": message,
                    "latency_ms": max(0, int((perf_counter() - started) * 1_000)),
                }
            )
            error = {"code": "AGENT_EXECUTION_FAILED", "message": message, "retryable": True}
            return (
                task.task_id,
                completed,
                self._synthetic_result(task, "failed", message),
                [],
                handoff.model_dump(mode="json"),
                [error],
            )

    async def _refresh_profile(self, state: EducationAgentState) -> dict[str, Any]:
        actor = Operator.model_validate(state["current_task"]["actor"])
        if actor.type != ActorType.STUDENT:
            return {
                "user_profile": state["user_profile"],
                "learning_context": state.get("learning_context", {}),
            }
        summary = await self.event_service.summarize_recent_learning(state["user_id"])
        profile = await self.profile_service.get_profile(state["user_id"])
        return {
            "user_profile": profile.model_dump(mode="json"),
            "learning_context": {**state.get("learning_context", {}), "summary": summary},
        }

    async def _finalize(self, state: EducationAgentState) -> dict[str, Any]:
        results = state.get("task_results", {})
        plan = OrchestrationPlan.model_validate(state["orchestration_plan"])
        needs_input = [item for item in plan.tasks if item.status == "needs_input"]
        failed = [item for item in plan.tasks if item.status == "failed"]
        skipped = [item for item in plan.tasks if item.status == "skipped"]
        succeeded = [item for item in plan.tasks if item.status in {"success", "partial_success"}]
        parts: list[str] = []
        for item in plan.tasks:
            result = results.get(item.task_id, {})
            message = self._result_message(result)
            if message and message not in parts:
                parts.append(message)
        if needs_input:
            prompts = list(dict.fromkeys(item.status_message for item in needs_input))
            parts.append(
                "继续完成前，我还需要你补充：\n" + "\n".join(f"- {item}" for item in prompts)
            )
        if not parts:
            parts.append("本次请求尚未形成可验证结果，请根据执行步骤中的提示补充信息。")
        if failed and succeeded:
            status = "partial_success"
        elif failed and not succeeded:
            status = "failed"
        elif needs_input and not succeeded:
            status = "need_more_information"
        elif needs_input:
            status = "partial_success"
        elif skipped and not succeeded:
            status = "need_more_information"
        else:
            status = "success"
        fallback = "\n\n".join(parts)
        generated = await self.response_synthesizer.synthesize(
            {
                "user_goal": plan.goal,
                "task_statuses": [
                    {
                        "agent": item.agent.value,
                        "objective": item.objective,
                        "status": item.status,
                        "status_message": item.status_message,
                    }
                    for item in plan.tasks
                ],
                "verified_results": {
                    task_id: {
                        "status": value.get("status"),
                        "result": value.get("result", {}),
                        "warnings": value.get("warnings", []),
                        "errors": value.get("errors", []),
                    }
                    for task_id, value in results.items()
                },
                "missing_context": [
                    detail.model_dump(mode="json")
                    for task in needs_input
                    for detail in task.missing_context
                ],
                "formal_plan_requires_confirmation": True,
                "verified_cross_module_evidence": state.get("learning_context", {}).get(
                    "cross_module_evidence", {}
                ),
                "personalization_context": state.get("collaboration_memory", {}),
            }
        )
        if generated:
            final_response = generated
            generation_mode = "llm"
        else:
            final_response = (
                "综合回复模型当前不可用。以下内容为各 Agent 已验证结果的结构化汇总：\n\n" + fallback
            )
            generation_mode = "rule_summary"
        return {
            "final_response": final_response,
            "response_generation_mode": generation_mode,
            "status": status,
        }

    @staticmethod
    def _result_message(result: dict[str, Any]) -> str:
        payload = result.get("result") or {}
        candidates = (
            payload.get("message"),
            payload.get("student_message"),
            payload.get("reply"),
            (payload.get("plan_adaptation") or {}).get("student_message"),
            (payload.get("diagnosis_report") or {}).get("student_summary"),
            (payload.get("student_visible_content") or {}).get("guidance"),
        )
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
        if result.get("errors"):
            return str(result["errors"][0].get("message") or "任务执行失败")
        return ""

    @staticmethod
    def _synthetic_result(
        task: AgentTask,
        status: str,
        message: str,
        *,
        missing: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "agent_role": task.agent.value,
            "status": status,
            "lifecycle_status": "waiting_for_data" if status == "need_more_information" else status,
            "result": {"message": message, "missing_context": missing or []},
            "warnings": [],
            "errors": []
            if status == "need_more_information"
            else [{"code": "ORCHESTRATION_TASK_STOPPED", "message": message}],
        }

    @staticmethod
    def _profile_changes(
        before: dict[str, Any], after: UnifiedStudentProfile
    ) -> list[ProfileChange]:
        dumped = after.model_dump(mode="json")
        changes: list[ProfileChange] = []
        for field in ("weak_points", "strengths", "recent_learning_summary", "current_plan"):
            if before.get(field) != dumped.get(field):
                changes.append(
                    ProfileChange(field=field, before=before.get(field), after=dumped.get(field))
                )
        before_mastery = before.get("knowledge_mastery", {})
        for key, value in dumped.get("knowledge_mastery", {}).items():
            old = before_mastery.get(key)
            if old != value:
                changes.append(
                    ProfileChange(field=f"knowledge_mastery.{key}", before=old, after=value)
                )
        return changes[:20]

    @staticmethod
    def _confirmation(
        task_results: dict[str, dict[str, Any]],
    ) -> tuple[bool, dict[str, Any] | None]:
        for result in task_results.values():
            adaptation = (result.get("result") or {}).get("plan_adaptation") or {}
            if adaptation.get("requires_confirmation"):
                return True, {
                    "type": "open_planning_center",
                    "label": "前往规划中心确认",
                    "mutation_applied": bool(adaptation.get("mutation_applied")),
                    "notice": "建议尚未覆盖正式计划，需要你在规划中心确认。",
                }
        return False, None

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
                "actor_type": state.get("current_task", {}).get("actor", {}).get("type", "student"),
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


def task_map_agent(task_id: str, plan_payload: dict[str, Any]) -> str:
    plan = OrchestrationPlan.model_validate(plan_payload)
    for item in plan.tasks:
        if item.task_id == task_id:
            return item.agent.value
    return AgentRole.SUPERVISOR.value
