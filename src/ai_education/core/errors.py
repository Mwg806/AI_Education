"""Domain exceptions translated into stable protocol errors."""

from __future__ import annotations

from typing import Any


class AIEducationError(Exception):
    """Base error carrying a machine-readable code and safe details."""

    code = "AI_EDUCATION_ERROR"
    retryable = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InputValidationError(AIEducationError):
    code = "INPUT_VALIDATION_ERROR"


class PolicyUnavailableError(AIEducationError):
    code = "POLICY_UNAVAILABLE"
    retryable = True


class PolicyConflictError(AIEducationError):
    code = "POLICY_CONFLICT"


class DataConflictError(AIEducationError):
    code = "DATA_VERSION_CONFLICT"
    retryable = True


class InsufficientInformationError(AIEducationError):
    code = "INSUFFICIENT_INFORMATION"


class PlanValidationError(AIEducationError):
    code = "PLAN_VALIDATION_ERROR"


class AgentNotFoundError(AIEducationError):
    code = "AGENT_NOT_FOUND"


class ToolExecutionError(AIEducationError):
    code = "TOOL_EXECUTION_ERROR"
    retryable = True
