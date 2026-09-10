"""Structured LLM boundary for lesson-plan knowledge graph generation."""

from __future__ import annotations

from typing import Any

from ai_education.domain.knowledge_graph import (
    KNOWLEDGE_GRAPH_NODE_RANGES,
    ProfessionalKnowledgeGraph,
)
from ai_education.prompts.knowledge_graph import KNOWLEDGE_GRAPH_PROMPT


class StructuredKnowledgeGraphGenerator:
    def __init__(self, model: Any | None) -> None:
        self.model = model
        self.chain = (
            KNOWLEDGE_GRAPH_PROMPT
            | model.with_structured_output(
                ProfessionalKnowledgeGraph,
                method="function_calling",
            )
            if model is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self.chain is not None

    async def generate(
        self,
        *,
        lesson_content: str,
        subject: str,
        graph_name_hint: str,
        detail_level: str,
    ) -> ProfessionalKnowledgeGraph | None:
        if self.chain is None:
            return None
        minimum_nodes, maximum_nodes = KNOWLEDGE_GRAPH_NODE_RANGES.get(
            detail_level, KNOWLEDGE_GRAPH_NODE_RANGES["标准"]
        )
        return await self.chain.ainvoke(
            {
                "lesson_content": lesson_content,
                "subject": subject,
                "graph_name_hint": graph_name_hint or "由教案内容自动概括",
                "detail_level": detail_level,
                "node_range": f"{minimum_nodes}-{maximum_nodes} 个节点",
            }
        )
