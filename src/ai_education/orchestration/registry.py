"""Thread-safe-enough in-process registry with no fixed agent-count ceiling."""

from __future__ import annotations

from ai_education.agents.base import BaseEducationAgent
from ai_education.core.errors import AgentNotFoundError, DataConflictError
from ai_education.domain.enums import AgentRole


class AgentRegistry:
    """Register agents by role; replacing an agent requires an explicit flag."""

    def __init__(self) -> None:
        self._agents: dict[AgentRole, BaseEducationAgent] = {}

    def register(self, agent: BaseEducationAgent, *, replace: bool = False) -> None:
        role = agent.metadata.role
        if role in self._agents and not replace:
            raise DataConflictError(
                f"Agent role already registered: {role}",
                details={"role": role},
            )
        self._agents[role] = agent

    def get(self, role: AgentRole) -> BaseEducationAgent:
        try:
            return self._agents[role]
        except KeyError as exc:
            raise AgentNotFoundError(
                f"No agent registered for role: {role}",
                details={"role": role},
            ) from exc

    def find_by_intent(self, intent: str) -> list[BaseEducationAgent]:
        return [agent for agent in self._agents.values() if agent.supports(intent)]

    def roles(self) -> tuple[AgentRole, ...]:
        return tuple(self._agents)

    def __len__(self) -> int:
        return len(self._agents)
