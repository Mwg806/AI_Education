from __future__ import annotations

import unittest

from pydantic import ValidationError

from ai_education.domain.enums import ActorType, AgentRole, MessageType
from ai_education.domain.protocols import AgentMessage, Operator, ToolRequest


class ProtocolTests(unittest.TestCase):
    def test_tool_request_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ToolRequest(
                student_id="s1",
                scenario="initialization",
                operator=Operator(type=ActorType.AGENT, id="planner"),
                unknown=True,
            )

    def test_agent_message_is_versioned(self) -> None:
        message = AgentMessage(
            message_type=MessageType.EVENT,
            sender=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            student_id="s1",
            payload={"event": "PlanGenerated"},
        )
        self.assertEqual(message.protocol_version, "1.0")
        self.assertTrue(message.message_id.startswith("msg_"))


if __name__ == "__main__":
    unittest.main()
