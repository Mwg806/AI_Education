"""Serializable global state shared by LangGraph orchestration graphs."""

from __future__ import annotations

from typing import Any, TypedDict


class GlobalAgentState(TypedDict, total=False):
    request: dict[str, Any]
    active_agent: str
    lifecycle_status: str
    student_profile: dict[str, Any]
    exam_profile: dict[str, Any]
    goals: list[dict[str, Any]]
    knowledge_profile: dict[str, Any]
    time_profile: dict[str, Any]
    plan: dict[str, Any]
    events: list[dict[str, Any]]
    agent_results: dict[str, dict[str, Any]]
    evidence: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    next_action: str
    revision: int

