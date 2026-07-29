"""FastAPI application exposing the specification's core endpoints."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.api.schemas import (
    DailyUpdateInput,
    ExamProfileConfirmation,
    ExamResultInput,
    LearningEventInput,
    OnboardingAnswers,
    OnboardingCreate,
    PlanConfirmation,
    PlannerInvocation,
    ReplanInput,
)
from ai_education.config import Settings
from ai_education.core.errors import AIEducationError
from ai_education.domain.enums import ActorType
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.repositories import PlannerRepository
from ai_education.services.onboarding import OnboardingService
from ai_education.version import __version__


class AppContainer:
    def __init__(self) -> None:
        self.repository = PlannerRepository()
        self.settings = Settings.from_env()
        self.planner = PersonalizedLearningPlannerAgent(self.repository, self.settings)
        self.onboarding = OnboardingService(self.repository)

    def request(
        self,
        *,
        student_id: str,
        intent: str,
        payload: dict,
        actor_type: ActorType = ActorType.STUDENT,
        actor_id: str | None = None,
        idempotency_key: str | None = None,
        data_version: str = "v0",
    ) -> AgentRequest:
        return AgentRequest(
            student_id=student_id,
            actor=Operator(type=actor_type, id=actor_id or student_id),
            intent=intent,
            payload=payload,
            idempotency_key=idempotency_key,
            data_version=data_version,
        )


def create_app(container: AppContainer | None = None) -> FastAPI:
    services = container or AppContainer()
    app = FastAPI(
        title="AI Education Personalized Learning Planner",
        version=__version__,
        description="面向新高考全国Ⅰ卷的个性化学习规划智能体 API",
    )
    app.state.container = services

    @app.exception_handler(AIEducationError)
    async def domain_error_handler(_: Request, exc: AIEducationError) -> JSONResponse:
        return JSONResponse(
            status_code=409 if exc.code in {"DATA_VERSION_CONFLICT", "POLICY_CONFLICT"} else 400,
            content={
                "status": "failed",
                "errors": [{"code": exc.code, "message": exc.message, "details": exc.details}],
            },
        )

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "llm_enabled": services.settings.llm_enabled,
            "planner_graph": "ready",
        }

    @app.post("/api/v1/onboarding/sessions", status_code=201)
    async def create_onboarding(body: OnboardingCreate) -> dict:
        return services.onboarding.create(body.student_id).model_dump(mode="json")

    @app.get("/api/v1/onboarding/sessions/{onboarding_id}/next-questions")
    async def next_questions(onboarding_id: str) -> dict:
        return {"questions": services.onboarding.next_questions(onboarding_id)}

    @app.post("/api/v1/onboarding/sessions/{onboarding_id}/answers")
    async def submit_answers(onboarding_id: str, body: OnboardingAnswers) -> dict:
        session = services.onboarding.submit_answers(onboarding_id, body.answers)
        return {
            "session": session.model_dump(mode="json"),
            "completeness": services.onboarding.completeness(session.answers),
            "next_questions": services.onboarding.next_questions(onboarding_id),
        }

    @app.post("/api/v1/onboarding/sessions/{onboarding_id}/exam-profile/confirm")
    async def confirm_exam_profile(onboarding_id: str, body: ExamProfileConfirmation) -> dict:
        return services.onboarding.confirm_exam_profile(
            onboarding_id, body.exam_profile_id
        ).model_dump(mode="json")

    @app.post("/api/v1/planner/initialize")
    async def initialize_planner(body: PlannerInvocation) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="initialize_plan",
            payload=body.payload,
            actor_type=body.actor_type,
            actor_id=body.actor_id,
            idempotency_key=body.idempotency_key,
            data_version=body.data_version,
        )
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.get("/api/v1/students/{student_id}/plans/active")
    async def active_plan(student_id: str) -> dict:
        request = services.request(student_id=student_id, intent="get_plan", payload={})
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.post("/api/v1/learning-events")
    async def learning_event(body: LearningEventInput) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="practice_event",
            payload={"event": body.event},
            idempotency_key=body.idempotency_key,
        )
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.post("/api/v1/students/{student_id}/exam-results", status_code=202)
    async def exam_result(student_id: str, body: ExamResultInput) -> dict:
        # Preserve raw evidence and evaluate rules without fabricating grading details.
        metrics = body.exam_result.get("adjustment_metrics", {})
        request = services.request(
            student_id=student_id,
            intent="daily_update",
            payload={"metrics": metrics, "reason": "重要考试结果导入"},
            idempotency_key=body.idempotency_key,
        )
        response = await services.planner.ainvoke(request)
        result = response.model_dump(mode="json")
        result["exam_result_received"] = True
        result["attribution_status"] = "requires_structured_scoring_evidence"
        return result

    @app.post("/api/v1/planner/daily-update")
    async def daily_update(body: DailyUpdateInput) -> dict:
        payload = {"metrics": body.metrics}
        if body.plan_id:
            payload["plan_id"] = body.plan_id
        request = services.request(
            student_id=body.student_id,
            intent="daily_update",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.post("/api/v1/plans/{plan_id}/replan")
    async def replan(plan_id: str, body: ReplanInput) -> dict:
        payload = {"plan_id": plan_id, "reason": body.reason, "metrics": body.metrics}
        if body.level:
            payload["level"] = body.level
        request = services.request(
            student_id=body.student_id,
            intent="replan",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.post("/api/v1/plans/{plan_id}/confirm")
    async def confirm_plan(plan_id: str, body: PlanConfirmation) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="confirm_plan",
            payload={"plan_id": plan_id, "expected_version": body.expected_version},
            idempotency_key=body.idempotency_key,
        )
        return (await services.planner.ainvoke(request)).model_dump(mode="json")

    @app.get("/api/v1/tools/manifest")
    async def tool_manifest() -> dict:
        return services.planner.toolbox.capability_manifest()

    return app


app = create_app()
