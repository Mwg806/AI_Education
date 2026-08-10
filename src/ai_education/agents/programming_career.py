"""LangGraph workflow for the career-driven Agent 6 V2."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_education.agents.programming_learning import (
    ProgrammingLearningAgent,
    ProgrammingLearningState,
)
from ai_education.domain.enums import AgentRole
from ai_education.domain.programming_learning import (
    CareerCodeSubmissionInput,
    CareerCodingTaskInput,
    CareerDiagnosticSubmission,
    CareerProgrammingProfileInput,
)
from ai_education.domain.protocols import AgentMetadata


class CareerProgrammingLearningAgent(ProgrammingLearningAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="student_career_programming_agent",
            role=AgentRole.PROGRAMMING_LEARNING,
            version="2.0.0",
            description="面向实习与初级岗位的 Python 后端职业技能导师",
            capabilities={
                "python_backend_skill_graph",
                "evidence_based_gap_analysis",
                "career_learning_plan",
                "coding_task_selection",
                "restricted_code_execution",
                "automatic_tests",
                "progressive_teaching_feedback",
                "skill_mastery_update",
            },
            accepted_intents={
                "get_programming_dashboard",
                "configure_career_profile",
                "create_career_diagnostic",
                "submit_career_diagnostic",
                "create_career_coding_task",
                "submit_career_code",
                "get_career_coding_hint",
            },
        )

    def _build_graph(self):
        graph = StateGraph(ProgrammingLearningState)
        graph.add_node("dispatch", self._dispatch_v2)
        handlers = {
            "dashboard": self._dashboard,
            "profile": self._profile,
            "diagnostic": self._diagnostic,
            "diagnostic_submit": self._diagnostic_submit,
            "task": self._task,
            "submit": self._submit,
            "hint": self._hint,
            "legacy_profile": self._update_profile,
            "legacy_diagnostic": self._create_diagnostic,
            "legacy_diagnostic_submit": self._submit_diagnostic,
            "legacy_review": self._review_code,
            "legacy_project": self._recommend_project,
            "legacy_project_hint": self._project_hint,
            "legacy_interview": self._create_interview,
            "legacy_interview_score": self._score_interview,
            "legacy_weekly_report": self._weekly_report,
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
    def _dispatch_v2(state: ProgrammingLearningState) -> dict[str, Any]:
        routes = {
            "get_programming_dashboard": "dashboard",
            "configure_career_profile": "profile",
            "create_career_diagnostic": "diagnostic",
            "submit_career_diagnostic": "diagnostic_submit",
            "create_career_coding_task": "task",
            "submit_career_code": "submit",
            "get_career_coding_hint": "hint",
            "update_programming_profile": "legacy_profile",
            "create_programming_diagnostic": "legacy_diagnostic",
            "submit_programming_diagnostic": "legacy_diagnostic_submit",
            "review_python_code": "legacy_review",
            "recommend_programming_project": "legacy_project",
            "get_programming_project_hint": "legacy_project_hint",
            "create_programming_interview": "legacy_interview",
            "score_programming_interview_answer": "legacy_interview_score",
            "get_programming_weekly_report": "legacy_weekly_report",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _profile(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerProgrammingProfileInput.model_validate(state["payload"])
        result = self.service.configure_career_profile(
            state["request"]["student_id"], body, state["profile"]
        )
        return {"result": result, "lifecycle_status": "career_goal_ready"}

    def _diagnostic(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.create_career_diagnostic(state["request"]["student_id"])
        return {"result": result, "lifecycle_status": "career_diagnostic_in_progress"}

    def _diagnostic_submit(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerDiagnosticSubmission.model_validate(
            {"answers": state["payload"].get("answers", [])}
        )
        result = self.service.submit_career_diagnostic(
            state["request"]["student_id"],
            str(state["payload"].get("diagnostic_id", "")),
            body,
        )
        return {"result": result, "lifecycle_status": "career_gap_ready"}

    def _task(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerCodingTaskInput.model_validate(state["payload"])
        result = self.service.create_coding_task(state["request"]["student_id"], body)
        return {"result": result, "lifecycle_status": "career_coding_task_ready"}

    def _submit(self, state: ProgrammingLearningState) -> dict[str, Any]:
        body = CareerCodeSubmissionInput.model_validate({"code": state["payload"].get("code", "")})
        result = self.service.submit_coding_task(
            state["request"]["student_id"],
            str(state["payload"].get("task_id", "")),
            body,
        )
        return {"result": result, "lifecycle_status": "career_coding_feedback_ready"}

    def _hint(self, state: ProgrammingLearningState) -> dict[str, Any]:
        result = self.service.get_coding_hint(
            state["request"]["student_id"],
            str(state["payload"].get("task_id", "")),
        )
        return {"result": result, "lifecycle_status": "career_hint_ready"}
