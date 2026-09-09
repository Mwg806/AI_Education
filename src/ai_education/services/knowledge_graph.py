"""Application service for professional lesson-plan knowledge graphs."""

from __future__ import annotations

from typing import Any

from ai_education.core.errors import KnowledgeGraphModelUnavailableError
from ai_education.domain.knowledge_graph import (
    KnowledgeGraphStatistics,
    ProfessionalKnowledgeGraph,
)


class KnowledgeGraphService:
    def __init__(self, generator: Any, *, model_name: str | None = None) -> None:
        self.generator = generator
        self.model_name = model_name

    @property
    def available(self) -> bool:
        return bool(self.generator and self.generator.available)

    async def generate(
        self,
        *,
        lesson_content: str,
        subject: str,
        graph_name_hint: str,
        detail_level: str,
    ) -> ProfessionalKnowledgeGraph:
        if not self.available:
            raise KnowledgeGraphModelUnavailableError(
                "问鹿AI知识图谱服务暂不可用，请检查大模型配置后重试"
            )
        try:
            graph = await self.generator.generate(
                lesson_content=self._normalize_content(lesson_content),
                subject=subject,
                graph_name_hint=graph_name_hint,
                detail_level=detail_level,
            )
        except Exception as exc:
            raise KnowledgeGraphModelUnavailableError(
                "问鹿AI未能生成符合标准的知识图谱，请稍后重试",
                details={"failure_type": type(exc).__name__},
            ) from exc
        if graph is None:
            raise KnowledgeGraphModelUnavailableError("问鹿AI未返回知识图谱，请稍后重试")
        validated = ProfessionalKnowledgeGraph.model_validate(graph)
        return validated.model_copy(
            update={
                "statistics": KnowledgeGraphStatistics(
                    node_count=len(validated.nodes),
                    edge_count=len(validated.edges),
                )
            }
        )

    @staticmethod
    def _normalize_content(content: str) -> str:
        lines = [line.strip() for line in content.replace("\r\n", "\n").split("\n")]
        return "\n".join(line for line in lines if line).strip()
