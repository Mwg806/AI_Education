"""Natural-language intent routing with structured-model output and safe fallback."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ai_education.domain.enums import AgentRole
from ai_education.domain.multi_agent import RoutingDecision, UnifiedStudentProfile
from ai_education.services.shared.model_router import ModelRouter

ROUTER_SYSTEM = """你是教育多智能体系统的意图路由器。只做路由，不回答学习问题。
可用角色：personalized_learning_planner（规划）、homework_tutor（作业辅导）、
learning_diagnosis（学情诊断）、english_reading_language（英语阅读与语言）、
programming_learning（职业与编程）。如果用户同时要求分析原因并安排训练，必须按
learning_diagnosis -> personalized_learning_planner 顺序执行。输出必须符合给定结构。"""


class IntentRouter:
    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router
        model = model_router.select("intent_routing").model
        self.structured_model = (
            model.with_structured_output(RoutingDecision, method="function_calling")
            if model is not None
            else None
        )

    async def route(
        self,
        message: str,
        profile: UnifiedStudentProfile,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        fallback = self._fallback(message)
        if self.structured_model is None:
            return fallback
        try:
            result = await self.structured_model.ainvoke(
                [
                    SystemMessage(content=ROUTER_SYSTEM),
                    HumanMessage(
                        content=json.dumps(
                            {
                                "message": message,
                                "profile_weak_points": profile.weak_points[:12],
                                "context": context or {},
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            routed = (
                result
                if isinstance(result, RoutingDecision)
                else RoutingDecision.model_validate(result)
            )
            return self._enforce_workflow(message, routed)
        except Exception:
            return fallback

    def _enforce_workflow(self, message: str, decision: RoutingDecision) -> RoutingDecision:
        fallback = self._fallback(message)
        if fallback.execution_mode == "sequential":
            return fallback
        allowed = {
            AgentRole.PERSONALIZED_LEARNING_PLANNER,
            AgentRole.HOMEWORK_TUTOR,
            AgentRole.LEARNING_DIAGNOSIS,
            AgentRole.ENGLISH_READING_LANGUAGE,
            AgentRole.PROGRAMMING_LEARNING,
        }
        agents = [item for item in decision.required_agents if item in allowed]
        if not agents:
            return fallback
        return decision.model_copy(
            update={
                "primary_agent": decision.primary_agent
                if decision.primary_agent in allowed
                else agents[0],
                "required_agents": list(dict.fromkeys(agents)),
            }
        )

    @staticmethod
    def _fallback(message: str) -> RoutingDecision:
        text = message.lower()
        asks_diagnosis = any(
            token in text
            for token in ("分析原因", "诊断", "薄弱", "总是错", "一直不好", "问题在哪")
        )
        asks_plan = any(
            token in text for token in ("安排", "计划", "规划", "怎么练", "学习路线", "复习路线")
        )
        if asks_diagnosis and asks_plan:
            return RoutingDecision(
                intents=["diagnose_learning_state", "adapt_learning_plan"],
                primary_agent=AgentRole.LEARNING_DIAGNOSIS,
                required_agents=[
                    AgentRole.LEARNING_DIAGNOSIS,
                    AgentRole.PERSONALIZED_LEARNING_PLANNER,
                ],
                execution_mode="sequential",
                reason="用户同时要求分析学习问题并安排后续训练，需要先诊断再规划",
                confidence=0.96,
            )
        if any(token in text for token in ("英语", "阅读", "词汇", "语法", "口语")):
            role = (
                AgentRole.LEARNING_DIAGNOSIS
                if asks_diagnosis
                else AgentRole.ENGLISH_READING_LANGUAGE
            )
            return RoutingDecision(
                intents=["diagnose_learning_state" if asks_diagnosis else "english_learning"],
                primary_agent=role,
                required_agents=[role],
                execution_mode="single",
                reason="内容属于英语阅读与语言学习场景",
                confidence=0.9,
            )
        if any(token in text for token in ("代码", "编程", "项目实训", "岗位技能")):
            return RoutingDecision(
                intents=["programming_learning"],
                primary_agent=AgentRole.PROGRAMMING_LEARNING,
                required_agents=[AgentRole.PROGRAMMING_LEARNING],
                execution_mode="single",
                reason="内容属于职业教育与编程学习场景",
                confidence=0.9,
            )
        if any(token in text for token in ("作业", "这道题", "解题", "不会做")):
            return RoutingDecision(
                intents=["homework_tutoring"],
                primary_agent=AgentRole.HOMEWORK_TUTOR,
                required_agents=[AgentRole.HOMEWORK_TUTOR],
                execution_mode="single",
                reason="内容属于具体作业辅导场景",
                confidence=0.86,
            )
        if asks_diagnosis:
            role = AgentRole.LEARNING_DIAGNOSIS
            intent = "diagnose_learning_state"
        else:
            role = AgentRole.PERSONALIZED_LEARNING_PLANNER
            intent = "learning_plan"
        return RoutingDecision(
            intents=[intent],
            primary_agent=role,
            required_agents=[role],
            execution_mode="single",
            reason="根据当前学习诉求选择最接近的专用智能体",
            confidence=0.72,
        )
