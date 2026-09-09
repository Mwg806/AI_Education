"""Strict contract for professional lesson-plan knowledge graphs."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from ai_education.domain.protocols import StrictModel

KnowledgeNodeType = Literal[
    "course",
    "chapter",
    "core_knowledge",
    "knowledge",
    "sub_knowledge",
    "definition",
    "principle",
    "formula",
    "method",
    "example",
    "error",
    "prerequisite",
    "application",
    "ability",
    "question",
]

KnowledgeRelationType = Literal[
    "contains",
    "prerequisite_of",
    "derives",
    "depends_on",
    "applies_to",
    "example_of",
    "confused_with",
    "related_to",
    "supports",
    "assesses",
]

KNOWLEDGE_RELATION_LABELS: dict[str, str] = {
    "contains": "包含",
    "prerequisite_of": "先修于",
    "derives": "推导",
    "depends_on": "依赖",
    "applies_to": "应用于",
    "example_of": "示例",
    "confused_with": "易混淆",
    "related_to": "关联",
    "supports": "支撑",
    "assesses": "评价",
}


class KnowledgeGraphStatistics(StrictModel):
    node_count: int = Field(ge=0, le=80)
    edge_count: int = Field(ge=0, le=240)


class KnowledgeGraphNode(StrictModel):
    id: str = Field(pattern=r"^n[0-9]{3}$")
    name: str = Field(min_length=1, max_length=80)
    type: KnowledgeNodeType
    level: int = Field(ge=0, le=5)
    importance: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    description: str = Field(min_length=2, max_length=800)
    chapter: str = Field(default="", max_length=120)
    keywords: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("name", "description", "chapter")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


class KnowledgeGraphEdge(StrictModel):
    id: str = Field(pattern=r"^e[0-9]{3}$")
    source: str = Field(pattern=r"^n[0-9]{3}$")
    target: str = Field(pattern=r"^n[0-9]{3}$")
    relation: KnowledgeRelationType
    label: str = Field(min_length=1, max_length=40)
    strength: int = Field(ge=1, le=5)
    description: str = Field(default="", max_length=500)

    @model_validator(mode="before")
    @classmethod
    def populate_relation_label(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        label = value.get("label")
        if isinstance(label, str) and label.strip():
            return value
        canonical_label = KNOWLEDGE_RELATION_LABELS.get(str(value.get("relation") or ""))
        if canonical_label:
            return {**value, "label": canonical_label}
        return value

    @field_validator("label", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class ProfessionalKnowledgeGraph(StrictModel):
    graph_name: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=4, max_length=1_200)
    statistics: KnowledgeGraphStatistics
    nodes: list[KnowledgeGraphNode] = Field(min_length=4, max_length=60)
    edges: list[KnowledgeGraphEdge] = Field(min_length=3, max_length=180)

    @field_validator("graph_name", "summary")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_topology(self) -> ProfessionalKnowledgeGraph:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("知识图谱节点 ID 必须唯一")
        normalized_names = [node.name.casefold() for node in self.nodes]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("知识图谱节点名称不得重复")

        known_nodes = set(node_ids)
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("知识图谱关系 ID 必须唯一")
        unknown_nodes = {
            endpoint
            for edge in self.edges
            for endpoint in (edge.source, edge.target)
            if endpoint not in known_nodes
        }
        if unknown_nodes:
            raise ValueError(f"知识图谱关系引用了未知节点：{sorted(unknown_nodes)}")
        if any(edge.source == edge.target for edge in self.edges):
            raise ValueError("知识图谱不得包含自环关系")
        edge_keys = [(edge.source, edge.target, edge.relation) for edge in self.edges]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("知识图谱不得包含重复关系")
        connected_nodes = {
            endpoint for edge in self.edges for endpoint in (edge.source, edge.target)
        }
        isolated_nodes = known_nodes - connected_nodes
        if isolated_nodes:
            raise ValueError(f"知识图谱不得包含孤立节点：{sorted(isolated_nodes)}")
        return self
