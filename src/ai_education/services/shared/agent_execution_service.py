"""Compatibility wrapper adding shared context, events and traces to legacy agents."""

from __future__ import annotations

import json
import logging
from time import perf_counter

from ai_education.domain.enums import ActorType, AgentRole
from ai_education.domain.multi_agent import AgentExecutionTrace, AgentHandoff, LearningEvent
from ai_education.domain.protocols import AgentRequest, AgentResponse
from ai_education.orchestration.bus import AgentMessageBus
from ai_education.orchestration.registry import AgentRegistry
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.model_router import ModelRouter
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository

LOGGER = logging.getLogger("ai_education.agent_execution")


class AgentExecutionService:
    def __init__(
        self,
        registry: AgentRegistry,
        profile_service: StudentProfileService,
        event_service: LearningEventService,
        repository: SharedLearningRepository,
        model_router: ModelRouter,
        bus: AgentMessageBus,
    ) -> None:
        self.registry = registry
        self.profile_service = profile_service
        self.event_service = event_service
        self.repository = repository
        self.model_router = model_router
        self.bus = bus

    async def invoke(
        self,
        role: AgentRole,
        request: AgentRequest,
        *,
        handoff: AgentHandoff | None = None,
    ) -> tuple[AgentResponse, list[LearningEvent]]:
        is_student = request.actor.type == ActorType.STUDENT
        if is_student:
            profile = await self.profile_service.get_profile(request.student_id)
            recent_events = await self.event_service.get_recent_events(request.student_id, 50)
            shared_context = {
                "unified_student_profile": profile.model_dump(mode="json"),
                "recent_learning_events": [item.model_dump(mode="json") for item in recent_events],
            }
        else:
            shared_context = {
                "actor_context": {
                    "type": request.actor.type.value,
                    "id": request.actor.id,
                    "student_profile_access": False,
                },
                "recent_learning_events": [],
            }
        enriched = request.model_copy(
            update={
                "context": {
                    **request.context,
                    **shared_context,
                    "handoff": handoff.model_dump(mode="json") if handoff else None,
                }
            }
        )
        started = perf_counter()
        status = "failed"
        error: str | None = None
        events: list[LearningEvent] = []
        try:
            response = await self.registry.get(role).ainvoke(enriched)
            for message in response.messages:
                await self.bus.publish(message)
            events = (
                await self.event_service.capture_agent_response(enriched, response)
                if is_student
                else []
            )
            status = response.status.value
            return response, events
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            selection = self.model_router.select(f"agent:{role.value}")
            trace = AgentExecutionTrace(
                request_id=request.request_id,
                trace_id=request.trace_id,
                user_id=request.student_id,
                actor_type=request.actor.type.value,
                session_id=str(request.context.get("session_id") or "") or None,
                agent=role,
                model=selection.model_name,
                model_capability=selection.capability,
                latency_ms=max(0, int((perf_counter() - started) * 1_000)),
                status=status,
                error=error,
                handoff=handoff.model_dump(mode="json") if handoff else None,
                event_count=len(events),
            )
            payload = trace.model_dump(mode="json")
            self.repository.save_trace(payload)
            LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))
