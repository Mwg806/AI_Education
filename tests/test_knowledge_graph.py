from __future__ import annotations

import unittest

from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from ai_education.api.app import AppContainer, create_app
from ai_education.domain.knowledge_graph import ProfessionalKnowledgeGraph
from ai_education.services.knowledge_graph import KnowledgeGraphService


def graph_payload() -> dict:
    return {
        "graph_name": "函数单调性专业知识图谱",
        "summary": "围绕定义、判定方法与典型应用建立关联。",
        "statistics": {"node_count": 40, "edge_count": 30},
        "nodes": [
            {
                "id": "n001",
                "name": "函数单调性",
                "type": "course",
                "level": 0,
                "importance": 5,
                "difficulty": 3,
                "description": "本节课的核心主题。",
                "chapter": "函数",
                "keywords": ["单调性"],
            },
            {
                "id": "n002",
                "name": "单调性定义",
                "type": "definition",
                "level": 2,
                "importance": 5,
                "difficulty": 2,
                "description": "使用任意两点的函数值大小刻画增减。",
                "chapter": "函数",
                "keywords": ["定义"],
            },
            {
                "id": "n003",
                "name": "图像判定",
                "type": "method",
                "level": 3,
                "importance": 4,
                "difficulty": 2,
                "description": "依据图像随自变量变化的趋势判断单调区间。",
                "chapter": "函数",
                "keywords": ["图像"],
            },
            {
                "id": "n004",
                "name": "端点遗漏",
                "type": "error",
                "level": 3,
                "importance": 3,
                "difficulty": 3,
                "description": "书写单调区间时容易遗漏定义域端点。",
                "chapter": "函数",
                "keywords": ["易错点"],
            },
        ],
        "edges": [
            {
                "id": "e001",
                "source": "n001",
                "target": "n002",
                "relation": "contains",
                "label": "包含",
                "strength": 5,
                "description": "主题包含核心定义。",
            },
            {
                "id": "e002",
                "source": "n002",
                "target": "n003",
                "relation": "supports",
                "label": "支撑",
                "strength": 4,
                "description": "定义支撑图像判定。",
            },
            {
                "id": "e003",
                "source": "n004",
                "target": "n003",
                "relation": "related_to",
                "label": "关联",
                "strength": 3,
                "description": "易错点与判定过程相关。",
            },
        ],
    }


class FakeKnowledgeGraphGenerator:
    available = True

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(self, **kwargs) -> ProfessionalKnowledgeGraph:
        self.calls.append(kwargs)
        return ProfessionalKnowledgeGraph.model_validate(graph_payload())


class KnowledgeGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_api_returns_canonical_graph_json(self) -> None:
        container = AppContainer(enable_persistence=False)
        generator = FakeKnowledgeGraphGenerator()
        container.knowledge_graph.generator = generator
        app = create_app(container)

        @app.middleware("http")
        async def inject_teacher_session(request, call_next):
            request.state.student_profile = {
                "role": "teacher",
                "teacherId": "teacher_knowledge_graph_test",
            }
            return await call_next(request)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/teacher/knowledge-graphs/generate",
                json={
                    "lesson_content": "这是一份用于接口验证的教案正文。" * 10,
                    "subject": "mathematics",
                    "graph_name_hint": "函数单调性",
                    "detail_level": "标准",
                },
            )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(
            set(payload["knowledge_graph"]),
            {"graph_name", "summary", "statistics", "nodes", "edges"},
        )
        self.assertEqual(payload["knowledge_graph"]["statistics"], {
            "node_count": 4,
            "edge_count": 3,
        })
        self.assertEqual(payload["generation"]["model_alias"], "问鹿AI")

    async def test_service_generates_standard_graph_and_recomputes_statistics(self) -> None:
        generator = FakeKnowledgeGraphGenerator()
        service = KnowledgeGraphService(generator, model_name="configured-model")

        graph = await service.generate(
            lesson_content="  第一行教学内容。\n\n 第二行教学内容。  ",
            subject="mathematics",
            graph_name_hint="函数单调性",
            detail_level="标准",
        )

        self.assertEqual(graph.statistics.node_count, 4)
        self.assertEqual(graph.statistics.edge_count, 3)
        self.assertEqual(generator.calls[0]["lesson_content"], "第一行教学内容。\n第二行教学内容。")
        self.assertEqual(
            {node.type for node in graph.nodes},
            {"course", "definition", "method", "error"},
        )

    async def test_graph_rejects_unknown_relation_endpoint(self) -> None:
        payload = graph_payload()
        payload["edges"][0]["target"] = "n999"
        with self.assertRaisesRegex(ValidationError, "未知节点"):
            ProfessionalKnowledgeGraph.model_validate(payload)
