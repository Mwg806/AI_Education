"""Versioned message and tool protocols for current and future agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_education.domain.enums import (
    ActorType,
    AgentRole,
    MessageType,
    StandardStatus,
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now().astimezone()


class StrictModel(BaseModel):
    """Base model rejecting accidental fields at trust boundaries."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Operator(StrictModel):
    type: ActorType = ActorType.AGENT
    id: str = Field(min_length=1, max_length=128)


class Evidence(StrictModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WarningDetail(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(StrictModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ToolRequest(StrictModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex}")
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    student_id: str = Field(min_length=1, max_length=128)
    scenario: str = Field(min_length=1, max_length=128)
    operator: Operator
    data_version: str = Field(default="v0", pattern=r"^v[\w.-]+$")
    idempotency_key: str | None = Field(default=None, max_length=256)
    requested_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(StrictModel):
    request_id: str
    status: StandardStatus
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[WarningDetail] = Field(default_factory=list)
    errors: list[ErrorDetail] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    data_version: str = "v0"
    completed_at: datetime = Field(default_factory=utc_now)


class AgentMessage(StrictModel):
    protocol_version: str = "1.0"
    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex}")
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    correlation_id: str | None = None
    message_type: MessageType
    sender: AgentRole
    recipient: AgentRole | None = None
    student_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class AgentRequest(StrictModel):
    protocol_version: str = "1.0"
    request_id: str = Field(default_factory=lambda: f"agent_req_{uuid4().hex}")
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    student_id: str = Field(min_length=1, max_length=128)
    actor: Operator
    intent: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=256)
    data_version: str = "v0"


class AgentResponse(StrictModel):
    protocol_version: str = "1.0"
    request_id: str
    trace_id: str
    agent_role: AgentRole
    status: StandardStatus
    lifecycle_status: str
    result: dict[str, Any] = Field(default_factory=dict)
    messages: list[AgentMessage] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[WarningDetail] = Field(default_factory=list)
    errors: list[ErrorDetail] = Field(default_factory=list)
    data_version: str = "v0"
    completed_at: datetime = Field(default_factory=utc_now)


class AgentMetadata(StrictModel):
    agent_id: str = Field(min_length=1, max_length=128)
    role: AgentRole
    version: str
    description: str
    capabilities: set[str] = Field(default_factory=set)
    accepted_intents: set[str] = Field(default_factory=set)
    max_concurrency: int = Field(default=16, ge=1)

    @field_validator("capabilities", "accepted_intents")
    @classmethod
    def reject_blank_items(cls, value: set[str]) -> set[str]:
        if any(not item.strip() for item in value):
            raise ValueError("blank capability or intent is not allowed")
        return value


class CollaborationTask(StrictModel):
    task_id: str = Field(min_length=1, max_length=128)
    intent: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    preferred_agent: AgentRole | None = None
    depends_on: set[str] = Field(default_factory=set)
    required: bool = True


class CollaborationRequest(StrictModel):
    protocol_version: str = "1.0"
    collaboration_id: str = Field(default_factory=lambda: f"collab_{uuid4().hex}")
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    student_id: str = Field(min_length=1, max_length=128)
    actor: Operator
    tasks: list[CollaborationTask] = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    data_version: str = "v0"

    @field_validator("tasks")
    @classmethod
    def task_ids_must_be_unique(cls, tasks: list[CollaborationTask]) -> list[CollaborationTask]:
        task_ids = [task.task_id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("协作任务 ID 必须唯一")
        known = set(task_ids)
        unknown = {dependency for task in tasks for dependency in task.depends_on - known}
        if unknown:
            raise ValueError(f"存在未知依赖任务：{sorted(unknown)}")
        return tasks


class CollaborationResponse(StrictModel):
    protocol_version: str = "1.0"
    collaboration_id: str
    trace_id: str
    student_id: str
    status: StandardStatus
    task_results: dict[str, AgentResponse]
    aggregate: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[WarningDetail] = Field(default_factory=list)
    errors: list[ErrorDetail] = Field(default_factory=list)
    global_state_revision: int = Field(ge=0)
    completed_at: datetime = Field(default_factory=utc_now)
