"""FastAPI application exposing the specification's core endpoints."""

from __future__ import annotations

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ai_education.agents.homework_tutoring import HomeworkTutoringAgent
from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.api.schemas import (
    DailyUpdateInput,
    ExamProfileConfirmation,
    ExamResultInput,
    HomeworkSubmissionInput,
    HomeworkVariantRequest,
    LearningEventInput,
    OCRConfirmationInput,
    OnboardingAnswers,
    OnboardingCreate,
    PlanConfirmation,
    PlannerInvocation,
    QuestionBankSearchInput,
    ReplanInput,
)
from ai_education.config import Settings
from ai_education.core.errors import AIEducationError
from ai_education.domain.enums import ActorType, Subject
from ai_education.domain.homework import HomeworkSessionCreate, VariantSubmission
from ai_education.domain.protocols import AgentRequest, CollaborationRequest, Operator
from ai_education.homework_repository import HomeworkRepository
from ai_education.orchestration.coordinator import MultiAgentCoordinator
from ai_education.orchestration.registry import AgentRegistry
from ai_education.repositories import PlannerRepository
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from ai_education.services.homework_input import HomeworkImageService
from ai_education.services.onboarding import OnboardingService
from ai_education.services.question_bank import QuestionBankService
from ai_education.version import __version__


class AppContainer:
    def __init__(self) -> None:
        self.repository = PlannerRepository()
        self.settings = Settings.from_env()
        self.planner = PersonalizedLearningPlannerAgent(self.repository, self.settings)
        self.homework_repository = HomeworkRepository()
        self.question_bank = QuestionBankService()
        self.homework = HomeworkTutoringAgent(
            self.homework_repository,
            self.settings,
            self.question_bank,
        )
        self.homework_images = HomeworkImageService()
        self.onboarding = OnboardingService(self.repository)
        self.curriculum_catalog = CurriculumCatalogService()
        self.agent_registry = AgentRegistry()
        self.agent_registry.register(self.planner)
        self.agent_registry.register(self.homework)
        self.coordinator = MultiAgentCoordinator(self.agent_registry)

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
            "homework_tutor_graph": "ready",
            "registered_agents": [role.value for role in services.agent_registry.roles()],
        }

    @app.get("/api/v1/catalog/onboarding")
    async def onboarding_catalog() -> dict:
        return services.curriculum_catalog.onboarding_catalog()

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

    @app.get("/api/v1/agents/manifest")
    async def agent_manifest() -> dict:
        return {
            "personalized_learning_planner": services.planner.toolbox.capability_manifest(),
            "homework_tutor": services.homework.toolbox.capability_manifest(),
        }

    async def invoke_homework(request: AgentRequest) -> dict:
        response = await services.homework.ainvoke(request)
        for message in response.messages:
            await services.coordinator.bus.publish(message)
        return response.model_dump(mode="json")

    @app.get("/api/v1/homework/question-bank/summary")
    async def homework_question_bank_summary() -> dict:
        return services.question_bank.summary()

    @app.post("/api/v1/homework/question-bank/search")
    async def homework_question_bank_search(body: QuestionBankSearchInput) -> dict:
        matches = services.question_bank.search(
            body.query,
            subject=body.subject,
            province=body.province,
            limit=body.limit,
        )
        return {
            "matches": [
                {
                    key: value
                    for key, value in item.model_dump(mode="json").items()
                    if key not in {"relative_path", "secure_content_available", "file_size"}
                }
                for item in matches
            ],
            "answer_content_exposed": False,
        }

    @app.post("/api/v1/homework/sessions", status_code=201)
    async def create_homework_session(body: HomeworkSessionCreate) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="create_homework_session",
            payload=body.model_dump(mode="json"),
            idempotency_key=f"create_homework:{body.student_id}:{body.plan_task_id or 'adhoc'}",
        )
        return await invoke_homework(request)

    @app.get("/api/v1/homework/sessions/{session_id}")
    async def get_homework_session(session_id: str, student_id: str) -> dict:
        request = services.request(
            student_id=student_id,
            intent="get_homework_session",
            payload={"session_id": session_id},
        )
        return await invoke_homework(request)

    @app.post("/api/v1/homework/sessions/{session_id}/turns")
    async def submit_homework_turn(
        session_id: str,
        student_id: str = Form(...),
        message: str = Form(""),
        question_text: str = Form(""),
        student_work: str = Form(""),
        intent: str = Form("request_hint"),
        subject: str | None = Form(None),
        client_turn_id: str | None = Form(None),
        images: list[UploadFile] = File(default=[]),  # noqa: B008
    ) -> dict:
        image_results = []
        for upload in images[:3]:
            image_results.append(
                services.homework_images.process(await upload.read(), upload.content_type)
            )
        image_text = "\n".join(item["text"] for item in image_results if item["text"])
        image_confidence = (
            min(item["confidence"] for item in image_results) if image_results else None
        )
        image_warnings = [warning for item in image_results for warning in item["warnings"]]
        request = services.request(
            student_id=student_id,
            intent="homework_turn",
            payload={
                "session_id": session_id,
                "message": message,
                "question_text": question_text,
                "student_work": student_work,
                "intent": intent,
                "subject": Subject(subject).value if subject else None,
                "client_turn_id": client_turn_id,
                "image_text": image_text,
                "image_confidence": image_confidence,
                "image_warnings": image_warnings,
            },
            idempotency_key=client_turn_id,
        )
        return await invoke_homework(request)

    @app.post("/api/v1/homework/sessions/{session_id}/ocr-confirmation")
    async def confirm_homework_ocr(session_id: str, body: OCRConfirmationInput) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="confirm_ocr",
            payload={
                "session_id": session_id,
                "question_text": body.confirmed_text,
                "student_work": body.student_work,
                "intent": "confirm_ocr",
                "subject": body.subject.value if body.subject else None,
            },
            idempotency_key=body.idempotency_key,
        )
        return await invoke_homework(request)

    @app.post("/api/v1/homework/questions/{question_id}/submission")
    async def submit_homework_answer(question_id: str, body: HomeworkSubmissionInput) -> dict:
        session = services.homework_repository.session_for_question(question_id)
        request = services.request(
            student_id=body.student_id,
            intent="submit_homework_answer",
            payload={
                "session_id": session.session_id,
                "question_id": question_id,
                "student_work": body.answer,
                "intent": "submit_answer",
            },
            idempotency_key=body.idempotency_key,
        )
        return await invoke_homework(request)

    @app.post("/api/v1/homework/questions/{question_id}/variants")
    async def request_homework_variant(question_id: str, body: HomeworkVariantRequest) -> dict:
        session = services.homework_repository.session_for_question(question_id)
        request = services.request(
            student_id=body.student_id,
            intent="request_homework_variant",
            payload={
                "session_id": session.session_id,
                "question_id": question_id,
                "intent": "request_similar_question",
            },
            idempotency_key=body.idempotency_key,
        )
        return await invoke_homework(request)

    @app.post("/api/v1/homework/variants/{variant_id}/submission")
    async def submit_variant_answer(variant_id: str, body: VariantSubmission) -> dict:
        session = services.homework_repository.session_for_variant(variant_id)
        request = services.request(
            student_id=body.student_id,
            intent="submit_variant_answer",
            payload={
                "session_id": session.session_id,
                "question_id": session.active_question.question_id
                if session.active_question
                else None,
                "student_work": body.answer,
                "intent": "submit_answer",
            },
            idempotency_key=f"variant_submission:{variant_id}:{session.state_version}",
        )
        return await invoke_homework(request)

    @app.post("/api/v1/orchestration/execute")
    async def execute_collaboration(body: CollaborationRequest) -> dict:
        return (await services.coordinator.coordinate(body)).model_dump(mode="json")

    return app


app = create_app()
