"""LangGraph mode router for the complete Agent 6 V1 specification."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_education.agents.programming_learning import (
    ProgrammingLearningAgent,
    ProgrammingLearningState,
)
from ai_education.domain.career_education import (
    CareerChatInput,
    CareerCodingNextInput,
    CareerCodingSubmissionInput,
    CareerEducationOnboardingInput,
    CareerProjectAnswerInput,
    CareerProjectChatInput,
    CareerProjectStartInput,
)
from ai_education.domain.enums import AgentRole
from ai_education.domain.protocols import AgentMetadata


class CareerEducationV1Agent(ProgrammingLearningAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="career_education_agent_v1",
            role=AgentRole.PROGRAMMING_LEARNING,
            version="3.2.0",
            description="岗位技能、项目实训、代码练习三模式职业教育 Agent",
            capabilities={
                "controlled_job_onboarding",
                "career_context_chat",
                "task_decomposition",
                "llm_multi_turn_career_conversation",
                "llm_project_training_conversation",
                "project_template_bank",
                "project_markdown_documents",
                "project_submission_evaluation",
                "database_coding_question_bank",
                "sandbox_judge",
                "progressive_hint_policy",
                "shared_skill_evidence",
                "learning_plan",
            },
            accepted_intents={
                "v1_dashboard",
                "v1_onboarding",
                "v1_switch_mode",
                "v1_career_chat",
                "v1_list_projects",
                "v1_start_project",
                "v1_project_chat",
                "v1_get_project",
                "v1_submit_project",
                "v1_evaluate_project",
                "v1_next_question",
                "v1_submit_code",
                "v1_coding_hint",
                "v1_coding_solution",
                "v1_coding_history",
            },
        )

    def _build_graph(self):
        graph = StateGraph(ProgrammingLearningState)
        graph.add_node("dispatch", self._dispatch_v1)
        handlers = {
            "dashboard": self._dashboard,
            "onboarding": self._onboarding,
            "switch_mode": self._switch_mode,
            "career_chat": self._career_chat,
            "list_projects": self._list_projects,
            "start_project": self._start_project,
            "project_chat": self._project_chat,
            "get_project": self._get_project,
            "submit_project": self._submit_project,
            "evaluate_project": self._evaluate_project,
            "next_question": self._next_question,
            "submit_code": self._submit_code,
            "coding_hint": self._coding_hint,
            "coding_solution": self._coding_solution,
            "coding_history": self._coding_history,
            "unsupported": self._unsupported,
        }
        for name, handler in handlers.items():
            graph.add_node(name, handler)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            lambda state: state["next_node"],
            {name: name for name in handlers},
        )
        for name in handlers:
            graph.add_edge(name, END)
        return graph.compile()

    @staticmethod
    def _dispatch_v1(state: ProgrammingLearningState) -> dict[str, Any]:
        routes = {
            "v1_dashboard": "dashboard",
            "v1_onboarding": "onboarding",
            "v1_switch_mode": "switch_mode",
            "v1_career_chat": "career_chat",
            "v1_list_projects": "list_projects",
            "v1_start_project": "start_project",
            "v1_project_chat": "project_chat",
            "v1_get_project": "get_project",
            "v1_submit_project": "submit_project",
            "v1_evaluate_project": "evaluate_project",
            "v1_next_question": "next_question",
            "v1_submit_code": "submit_code",
            "v1_coding_hint": "coding_hint",
            "v1_coding_solution": "coding_solution",
            "v1_coding_history": "coding_history",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _dashboard(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.dashboard(state["request"]["student_id"], state["profile"])
        return {"result": result, "lifecycle_status": "career_education_ready"}

    def _onboarding(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerEducationOnboardingInput.model_validate(state["payload"])
        result = self.service.onboarding(state["request"]["student_id"], body, state["profile"])
        return {"result": result, "lifecycle_status": "career_job_selected"}

    def _switch_mode(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.switch_mode(
            state["request"]["student_id"], str(state["payload"].get("mode", ""))
        )
        return {"result": result, "lifecycle_status": "career_mode_switched"}

    async def _career_chat(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerChatInput.model_validate(state["payload"])
        result = await self.service.career_chat(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "career_guidance_ready"}

    def _list_projects(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.list_project_bank(state["request"]["student_id"])
        return {"result": {"projects": result}, "lifecycle_status": "project_bank_ready"}

    async def _start_project(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerProjectStartInput.model_validate(state["payload"])
        student_id = state["request"]["student_id"]
        result = self.service.start_project(student_id, body)
        opening = await self.service.project_chat(
            student_id,
            CareerProjectChatInput(
                session_id=result["session_id"],
                message=(
                    "我刚开始这个项目。请读取项目需求和方案资料，先概括我要完成什么，"
                    "再告诉我建议从哪里开始，并提出需要我先回答的关键问题。"
                ),
            ),
        )
        result = result | {"mentor_opening": opening}
        return {"result": result, "lifecycle_status": "project_waiting_submission"}

    async def _project_chat(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerProjectChatInput.model_validate(state["payload"])
        result = await self.service.project_chat(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "project_guidance_ready"}

    def _get_project(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.get_project_session(
            state["request"]["student_id"], str(state["payload"].get("session_id", ""))
        )
        return {"result": result, "lifecycle_status": "project_session_ready"}

    def _submit_project(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerProjectAnswerInput.model_validate(state["payload"].get("answer", {}))
        result = self.service.submit_project_answer(
            state["request"]["student_id"],
            str(state["payload"].get("session_id", "")),
            body,
        )
        return {"result": result, "lifecycle_status": "project_submitted"}

    def _evaluate_project(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.evaluate_project(
            state["request"]["student_id"], str(state["payload"].get("session_id", ""))
        )
        return {"result": result, "lifecycle_status": "project_evaluated"}

    def _next_question(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerCodingNextInput.model_validate(state["payload"])
        result = self.service.next_coding_question(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "coding_question_ready"}

    def _submit_code(self, state: ProgrammingLearningState) -> dict[str, Any]:
        payload = dict(state["payload"])
        session_id = str(payload.pop("session_id", ""))
        body = CareerCodingSubmissionInput.model_validate(payload)
        result = self.service.submit_coding(
            state["request"]["student_id"],
            session_id,
            body,
        )
        return {"result": result, "lifecycle_status": "coding_feedback_ready"}

    def _coding_hint(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.coding_hint(
            state["request"]["student_id"], str(state["payload"].get("session_id", ""))
        )
        return {"result": result, "lifecycle_status": "coding_hint_ready"}

    def _coding_solution(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.coding_solution(
            state["request"]["student_id"], str(state["payload"].get("session_id", ""))
        )
        return {"result": result, "lifecycle_status": "coding_solution_viewed"}

    def _coding_history(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.coding_history(state["request"]["student_id"])
        return {"result": {"submissions": result}, "lifecycle_status": "coding_history_ready"}
