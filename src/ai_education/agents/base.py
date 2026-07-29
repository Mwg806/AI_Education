"""Standard agent interface required by the collaboration scheduler."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ai_education.domain.protocols import AgentMetadata, AgentRequest, AgentResponse


class BaseEducationAgent(ABC):
    """Every education agent must implement one typed async entrypoint."""

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Declare identity, capabilities and accepted intents."""

    @abstractmethod
    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        """Handle one request without mutating the caller's object."""

    def supports(self, intent: str) -> bool:
        """Return whether this agent explicitly accepts an intent."""

        return intent in self.metadata.accepted_intents
