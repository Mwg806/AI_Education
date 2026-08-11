"""Shared contracts for progressive multi-agent orchestration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, TypedDict
from uuid import uuid4

from pydantic import Field

from ai_education.domain.enums import AgentRole
from ai_education.domain.protocols import StrictModel, utc_now


class LearningEventType(StrEnum):
    QUESTION_CORRECT = "QUESTION_CORRECT"
    QUESTION_WRONG = "QUESTION_WRONG"
    KNOWLEDGE_MASTERED = "KNOWLEDGE_MASTERED"
    KNOWLEDGE_WEAK = "KNOWLEDGE_WEAK"
    READING_ERROR = "READING_ERROR"
    GRAMMAR_ERROR = "GRAMMAR_ERROR"
    WRITING_ERROR = "WRITING_ERROR"
    SPEAKING_ERROR = "SPEAKING_ERROR"
    PROJECT_SCORE = "PROJECT_SCORE"
    SKILL_SCORE = "SKILL_SCORE"
    PLAN_UPDATED = "PLAN_UPDATED"
    PLAN_COMPLETED = "PLAN_COMPLETED"
    PLAN_FAILED = "PLAN_FAILED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    DIAGNOSIS_UPDATED = "DIAGNOSIS_UPDATED"


class LearningEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: f"learn_evt_{uuid4().hex[:20]}")
    event_type: LearningEventType
    user_id: str = Field(min_length=1, max_length=128)
    agent: AgentRole
    subject: str | None = Field(default=None, max_length=64)
    knowledge_point: str | None = Field(default=None, max_length=256)
    difficulty: float | None = Field(default=None, ge=0, le=1)
    score: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    session_id: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)


class MasterySnapshot(StrictModel):
    knowledge_point: str
    subject: str
    mastery: float = Field(default=0.5, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.2, ge=0, le=1)
    last_event_at: datetime | None = None
    trend: Literal["improving", "stable", "declining"] = "stable"
    error_types: list[str] = Field(default_factory=list)


class UnifiedStudentProfile(StrictModel):
    user_id: str
    basic_profile: dict[str, Any] = Field(default_factory=dict)
    learning_goal: dict[str, Any] = Field(default_factory=dict)
    subject_abilities: dict[str, dict[str, MasterySnapshot]] = Field(default_factory=dict)
    knowledge_mastery: dict[str, MasterySnapshot] = Field(default_factory=dict)
    weak_points: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recent_errors: list[dict[str, Any]] = Field(default_factory=list)
    learning_preferences: dict[str, Any] = Field(default_factory=dict)
    current_plan: dict[str, Any] = Field(default_factory=dict)
    recent_learning_summary: dict[str, Any] = Field(default_factory=dict)
    profile_version: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=utc_now)


class RoutingDecision(StrictModel):
    intents: list[str] = Field(min_length=1, max_length=8)
    primary_agent: AgentRole
    required_agents: list[AgentRole] = Field(min_length=1, max_length=6)
    execution_mode: Literal["single", "sequential", "parallel"]
    reason: str = Field(min_length=1, max_length=1_000)
    confidence: float = Field(ge=0, le=1)


class AgentHandoff(StrictModel):
    handoff_id: str = Field(default_factory=lambda: f"handoff_{uuid4().hex[:18]}")
    from_agent: AgentRole
    to_agent: AgentRole
    reason: str = Field(min_length=1, max_length=1_000)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    created_at: datetime = Field(default_factory=utc_now)


class OrchestrationInput(StrictModel):
    message: str = Field(min_length=2, max_length=5_000)
    subject: str = Field(default="foreign_language", max_length=64)
    session_id: str = Field(default_factory=lambda: f"orchestrator_session_{uuid4().hex[:16]}")
    context: dict[str, Any] = Field(default_factory=dict)


class OrchestrationResult(StrictModel):
    run_id: str
    trace_id: str
    session_id: str
    routing: RoutingDecision
    handoffs: list[AgentHandoff] = Field(default_factory=list)
    agent_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    final_response: str
    profile_version: int
    event_count: int = Field(ge=0)
    status: str


class AgentExecutionTrace(StrictModel):
    trace_record_id: str = Field(default_factory=lambda: f"agent_trace_{uuid4().hex[:20]}")
    request_id: str
    trace_id: str
    user_id: str
    session_id: str | None = None
    agent: AgentRole
    node: str = "agent_graph"
    model: str | None = None
    tool: str | None = None
    latency_ms: int = Field(ge=0)
    status: str
    error: str | None = None
    handoff: dict[str, Any] | None = None
    event_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class EducationAgentState(TypedDict, total=False):
    run_id: str
    user_id: str
    session_id: str
    trace_id: str
    messages: list[dict[str, Any]]
    intent: list[str]
    routing: dict[str, Any]
    current_agent: str | None
    user_profile: dict[str, Any]
    learning_context: dict[str, Any]
    current_task: dict[str, Any]
    retrieved_context: list[dict[str, Any]]
    agent_results: dict[str, dict[str, Any]]
    learning_events: list[dict[str, Any]]
    handoffs: list[dict[str, Any]]
    next_action: str | None
    confidence: float
    errors: list[dict[str, Any]]
    final_response: str
    status: str
