"""FastAPI application exposing the specification's core endpoints."""

from __future__ import annotations

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ai_education.agents.english_learning import EnglishReadingLanguageAgent
from ai_education.agents.homework_tutoring import HomeworkTutoringAgent
from ai_education.agents.learning_diagnosis import LearningDiagnosisAgent
from ai_education.agents.personalized_learning_planner import PersonalizedLearningPlannerAgent
from ai_education.agents.teacher_preparation import TeacherPreparationAgent
from ai_education.api.diagnosis_schemas import LearningDiagnosisRunInput, TeacherReviewInput
from ai_education.api.diagnostic_schemas import (
    DiagnosticCreateInput,
    DiagnosticSubmissionInput,
)
from ai_education.api.exam_diagnosis_schemas import (
    ExamDiagnosticSessionCreate,
    ExamDiagnosticSubmit,
)
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
from ai_education.api.teacher_preparation_schemas import (
    LessonPlanCreateInput,
    LessonPlanRevisionInput,
    LessonPlanTransitionInput,
    PostLessonFeedbackInput,
)
from ai_education.auth import (
    AuthService,
    StudentLoginInput,
    StudentRegistrationInput,
    TeacherLoginInput,
    TeacherRegistrationInput,
    bearer_token,
)
from ai_education.config import Settings
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.diagnosis_repository import DiagnosisRepository
from ai_education.domain.english_learning import (
    EnglishLearnerProfileInput,
    EnglishReviewCompletionInput,
    EnglishTaskInput,
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
)
from ai_education.domain.enums import ActorType, Subject
from ai_education.domain.homework import HomeworkSessionCreate, VariantSubmission
from ai_education.domain.protocols import AgentRequest, CollaborationRequest, Operator
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.homework_repository import HomeworkRepository
from ai_education.llm.diagnostic_generator import StructuredDiagnosticGenerator
from ai_education.llm.english_learning import (
    StructuredEnglishTrainingGenerator,
    StructuredLanguageTutorGenerator,
)
from ai_education.llm.exam_grader import StructuredExamGrader
from ai_education.llm.teacher_preparation import StructuredTeacherPreparationGenerator
from ai_education.mysql_persistence import MySQLPersistence
from ai_education.orchestration.coordinator import MultiAgentCoordinator
from ai_education.orchestration.registry import AgentRegistry
from ai_education.repositories import PlannerRepository
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from ai_education.services.diagnostic import DiagnosticService
from ai_education.services.english_knowledge import EnglishKnowledgeService
from ai_education.services.english_learning import EnglishLearningService
from ai_education.services.exam_diagnosis import DEFAULT_BANK_ROOT, ExamDiagnosticService
from ai_education.services.homework_input import HomeworkImageService
from ai_education.services.onboarding import OnboardingService
from ai_education.services.question_bank import QuestionBankService
from ai_education.services.teacher_preparation import TeacherPreparationService
from ai_education.services.teacher_preparation_knowledge import TeachingKnowledgeBase
from ai_education.teacher_platform import (
    AnnouncementCreateInput,
    ClassroomCreateInput,
    ClassroomJoinInput,
    ClassroomLeaveDecisionInput,
    ExamAssignmentInput,
    TeacherPlatformService,
)
from ai_education.teacher_preparation_repository import TeacherPreparationRepository
from ai_education.version import __version__


class AppContainer:
    def __init__(self, *, enable_persistence: bool | None = None) -> None:
        self.settings = Settings.from_env()
        persistence_enabled = (
            self.settings.mysql_enabled if enable_persistence is None else enable_persistence
        )
        self.persistence = MySQLPersistence(self.settings) if persistence_enabled else None
        if self.persistence:
            self.persistence.initialize_schema()
        self.auth = AuthService(self.persistence, session_hours=self.settings.auth_session_hours)
        self.teacher_platform = TeacherPlatformService(self.persistence)
        self.repository = PlannerRepository(self.persistence)
        self.planner = PersonalizedLearningPlannerAgent(self.repository, self.settings)
        self.homework_repository = HomeworkRepository(self.persistence)
        self.question_bank = QuestionBankService()
        self.homework = HomeworkTutoringAgent(
            self.homework_repository,
            self.settings,
            self.question_bank,
        )
        self.english_learning_repository = EnglishLearningRepository(self.persistence)
        self.english_knowledge = EnglishKnowledgeService()
        self.english_learning = EnglishReadingLanguageAgent(
            EnglishLearningService(
                self.english_learning_repository,
                StructuredEnglishTrainingGenerator(self.planner.plan_narrator.model),
                self.english_knowledge,
                StructuredLanguageTutorGenerator(self.planner.plan_narrator.model),
            )
        )
        self.diagnosis_repository = DiagnosisRepository(self.persistence)
        self.learning_diagnosis = LearningDiagnosisAgent(
            self.diagnosis_repository,
            self.settings,
        )
        self.teaching_knowledge = TeachingKnowledgeBase()
        self.teacher_preparation_repository = TeacherPreparationRepository(self.persistence)
        self.teacher_preparation = TeacherPreparationAgent(
            TeacherPreparationService(
                self.teacher_preparation_repository,
                self.teaching_knowledge,
                StructuredTeacherPreparationGenerator(self.planner.plan_narrator.model),
                model_name=self.settings.llm_model,
            )
        )
        self.homework_images = HomeworkImageService()
        self.onboarding = OnboardingService(self.repository)
        self.curriculum_catalog = CurriculumCatalogService()
        self.diagnostics = DiagnosticService(
            self.curriculum_catalog,
            StructuredDiagnosticGenerator(self.planner.plan_narrator.model),
            self.settings,
        )
        self.exam_diagnostics = ExamDiagnosticService(
            StructuredExamGrader(
                self.planner.plan_narrator.model,
                provider=self.settings.llm_provider,
            ),
            persistence=self.persistence,
        )
        self.agent_registry = AgentRegistry()
        self.agent_registry.register(self.planner)
        self.agent_registry.register(self.homework)
        self.agent_registry.register(self.learning_diagnosis)
        self.agent_registry.register(self.teacher_preparation)
        self.agent_registry.register(self.english_learning)
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

    @app.middleware("http")
    async def require_mysql_session(request: Request, call_next):
        public_paths = (
            "/health",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/teacher/register",
            "/api/v1/auth/teacher/login",
            "/api/v1/exam-diagnostics/assets/",
        )
        requires_auth = (
            services.persistence is not None
            and request.url.path.startswith("/api/v1/")
            and request.method != "OPTIONS"
            and not any(request.url.path.startswith(path) for path in public_paths)
        )
        if requires_auth:
            try:
                request.state.student_profile = services.auth.authenticate(
                    bearer_token(request.headers.get("authorization"))
                )
            except AIEducationError as exc:
                return JSONResponse(status_code=401, content={"detail": exc.message})
        return await call_next(request)

    app.mount(
        "/api/v1/exam-diagnostics/assets",
        StaticFiles(directory=DEFAULT_BANK_ROOT / "assets", check_dir=True),
        name="exam-diagnostic-assets",
    )

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
            "llm_provider": services.settings.llm_provider
            if services.settings.llm_enabled
            else None,
            "llm_model": services.settings.llm_model if services.settings.llm_enabled else None,
            "planner_generation_mode": (
                "llm" if services.planner.plan_narrator.available else "unavailable"
            ),
            "homework_generation_mode": (
                "llm"
                if services.homework.structured_tutor.available
                else "rule_test_only"
                if services.settings.allow_rule_fallback
                else "unavailable"
            ),
            "diagnosis_report_generation_mode": (
                "llm" if services.learning_diagnosis.reporter.available else "unavailable"
            ),
            "vision_input_enabled": services.homework.structured_tutor.available,
            "exam_diagnostic_bank": "ready"
            if services.exam_diagnostics.available
            else "unavailable",
            "exam_constructed_grading": (
                "multimodal_llm" if services.exam_diagnostics.grader.available else "unavailable"
            ),
            "planner_graph": "ready",
            "homework_tutor_graph": "ready",
            "learning_diagnosis_graph": "ready",
            "teacher_preparation_graph": "ready",
            "english_learning_graph": "ready",
            "english_learning_generation_mode": (
                "llm"
                if services.english_learning.service.tutor_generator.available
                else "evidence_template"
            ),
            "english_learning_target_user": "新高考全国Ⅰ卷考生",
            "teacher_preparation_generation_mode": (
                "llm" if services.teacher_preparation.generator.available else "reference_template"
            ),
            "teaching_resource_bank": services.teaching_knowledge.catalog(),
            "registered_agents": [role.value for role in services.agent_registry.roles()],
            "mysql_persistence": (
                "ready" if services.persistence and services.persistence.health() else "disabled"
            ),
            "student_authentication": "mysql_session" if services.persistence else "disabled",
        }

    @app.post("/api/v1/auth/register", status_code=201)
    async def register_student(body: StudentRegistrationInput) -> dict:
        return services.auth.register(body)

    @app.post("/api/v1/auth/login")
    async def login_student(body: StudentLoginInput) -> dict:
        return services.auth.login(body)

    @app.post("/api/v1/auth/teacher/register", status_code=201)
    async def register_teacher(body: TeacherRegistrationInput) -> dict:
        return services.auth.register_teacher(body)

    @app.post("/api/v1/auth/teacher/login")
    async def login_teacher(body: TeacherLoginInput) -> dict:
        return services.auth.login_teacher(body)

    @app.get("/api/v1/auth/me")
    async def authenticated_student(authorization: str | None = Header(default=None)) -> dict:
        try:
            return {"profile": services.auth.authenticate(bearer_token(authorization))}
        except AIEducationError as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc

    @app.post("/api/v1/auth/logout", status_code=204)
    async def logout_student(authorization: str | None = Header(default=None)) -> None:
        services.auth.logout(bearer_token(authorization))

    def require_role(request: Request, role: str) -> dict:
        profile = getattr(request.state, "student_profile", None)
        if not profile or profile.get("role") != role:
            raise HTTPException(status_code=403, detail=f"该操作仅限{role}身份")
        return profile

    @app.get("/api/v1/teacher/dashboard")
    async def teacher_dashboard(request: Request) -> dict:
        profile = require_role(request, "teacher")
        return services.teacher_platform.teacher_dashboard(profile["teacherId"])

    @app.post("/api/v1/teacher/classrooms", status_code=201)
    async def create_teacher_classroom(body: ClassroomCreateInput, request: Request) -> dict:
        profile = require_role(request, "teacher")
        return services.teacher_platform.create_classroom(profile["teacherId"], body)

    @app.get("/api/v1/teacher/classrooms/{classroom_id}")
    async def teacher_classroom_detail(classroom_id: int, request: Request) -> dict:
        profile = require_role(request, "teacher")
        return services.teacher_platform.classroom_detail(profile["teacherId"], classroom_id)

    @app.put("/api/v1/teacher/classroom-leave-requests/{request_id}")
    async def review_classroom_leave_request(
        request_id: str, body: ClassroomLeaveDecisionInput, request: Request
    ) -> dict:
        profile = require_role(request, "teacher")
        return services.teacher_platform.review_classroom_leave(
            profile["teacherId"], request_id, body
        )

    @app.post(
        "/api/v1/teacher/classrooms/{classroom_id}/announcements",
        status_code=201,
    )
    async def publish_classroom_announcement(
        classroom_id: int, body: AnnouncementCreateInput, request: Request
    ) -> dict:
        profile = require_role(request, "teacher")
        return services.teacher_platform.publish_announcement(
            profile["teacherId"], classroom_id, body
        )

    @app.put("/api/v1/teacher/classrooms/{classroom_id}/exam-assignments")
    async def save_classroom_exam_assignment(
        classroom_id: int, body: ExamAssignmentInput, request: Request
    ) -> dict:
        profile = require_role(request, "teacher")
        services.exam_diagnostics.paper(body.paper_id)
        return services.teacher_platform.save_exam_assignment(
            profile["teacherId"], classroom_id, body
        )

    async def invoke_teacher_preparation(agent_request: AgentRequest) -> dict:
        response = await services.teacher_preparation.ainvoke(agent_request)
        for message in response.messages:
            await services.coordinator.bus.publish(message)
        return response.model_dump(mode="json")

    def teacher_lesson_request(
        profile: dict,
        *,
        intent: str,
        payload: dict,
        idempotency_key: str | None = None,
    ) -> AgentRequest:
        teacher_id = profile["teacherId"]
        return services.request(
            student_id=f"teacher:{teacher_id}",
            intent=intent,
            payload=payload,
            actor_type=ActorType.TEACHER,
            actor_id=teacher_id,
            idempotency_key=idempotency_key,
        )

    @app.get("/api/v1/teacher/preparation/resources/catalog")
    async def teacher_preparation_catalog(request: Request) -> dict:
        require_role(request, "teacher")
        return {
            **services.teaching_knowledge.catalog(),
            "integrity": services.teaching_knowledge.verify_integrity(),
        }

    @app.get("/api/v1/teacher/preparation/resources/search")
    async def search_teacher_preparation_resources(
        request: Request,
        subject: Subject,
        query: str,
        limit: int = 3,
    ) -> dict:
        profile = require_role(request, "teacher")
        agent_request = teacher_lesson_request(
            profile,
            intent="search_teaching_resources",
            payload={"subject": subject.value, "query": query, "limit": limit},
        )
        return await invoke_teacher_preparation(agent_request)

    @app.get("/api/v1/teacher/lesson-plans")
    async def list_teacher_lesson_plans(request: Request, classroom_id: int | None = None) -> dict:
        profile = require_role(request, "teacher")
        agent_request = teacher_lesson_request(
            profile,
            intent="list_lesson_plans",
            payload={"classroom_id": classroom_id},
        )
        return await invoke_teacher_preparation(agent_request)

    @app.post("/api/v1/teacher/lesson-plans", status_code=201)
    async def create_teacher_lesson_plan(body: LessonPlanCreateInput, request: Request) -> dict:
        profile = require_role(request, "teacher")
        detail = services.teacher_platform.classroom_detail(profile["teacherId"], body.classroom_id)
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        payload.update(
            {
                "classroom": detail["classroom"],
                "diagnosis_summary": (
                    services.teacher_preparation.service.aggregate_class_diagnosis(
                        detail["students"]
                    )
                ),
            }
        )
        agent_request = teacher_lesson_request(
            profile,
            intent="create_lesson_plan",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_teacher_preparation(agent_request)

    @app.get("/api/v1/teacher/lesson-plans/{lesson_plan_id}")
    async def get_teacher_lesson_plan(
        lesson_plan_id: str, request: Request, version: int | None = None
    ) -> dict:
        profile = require_role(request, "teacher")
        agent_request = teacher_lesson_request(
            profile,
            intent="get_lesson_plan",
            payload={"lesson_plan_id": lesson_plan_id, "version": version},
        )
        return await invoke_teacher_preparation(agent_request)

    @app.post("/api/v1/teacher/lesson-plans/{lesson_plan_id}/revise")
    async def revise_teacher_lesson_plan(
        lesson_plan_id: str, body: LessonPlanRevisionInput, request: Request
    ) -> dict:
        profile = require_role(request, "teacher")
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        payload["lesson_plan_id"] = lesson_plan_id
        agent_request = teacher_lesson_request(
            profile,
            intent="revise_lesson_plan",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_teacher_preparation(agent_request)

    async def transition_teacher_lesson_plan(
        lesson_plan_id: str,
        body: LessonPlanTransitionInput,
        request: Request,
        *,
        intent: str,
    ) -> dict:
        profile = require_role(request, "teacher")
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        payload["lesson_plan_id"] = lesson_plan_id
        agent_request = teacher_lesson_request(
            profile,
            intent=intent,
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_teacher_preparation(agent_request)

    @app.post("/api/v1/teacher/lesson-plans/{lesson_plan_id}/approve")
    async def approve_teacher_lesson_plan(
        lesson_plan_id: str, body: LessonPlanTransitionInput, request: Request
    ) -> dict:
        return await transition_teacher_lesson_plan(
            lesson_plan_id, body, request, intent="approve_lesson_plan"
        )

    @app.post("/api/v1/teacher/lesson-plans/{lesson_plan_id}/publish")
    async def publish_teacher_lesson_plan(
        lesson_plan_id: str, body: LessonPlanTransitionInput, request: Request
    ) -> dict:
        return await transition_teacher_lesson_plan(
            lesson_plan_id, body, request, intent="publish_lesson_plan"
        )

    @app.post(
        "/api/v1/teacher/lesson-plans/{lesson_plan_id}/feedback",
        status_code=201,
    )
    async def record_teacher_lesson_feedback(
        lesson_plan_id: str, body: PostLessonFeedbackInput, request: Request
    ) -> dict:
        profile = require_role(request, "teacher")
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        payload["lesson_plan_id"] = lesson_plan_id
        agent_request = teacher_lesson_request(
            profile,
            intent="record_post_lesson_feedback",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_teacher_preparation(agent_request)

    @app.get("/api/v1/student/classrooms")
    async def student_classroom_portal(request: Request) -> dict:
        profile = require_role(request, "student")
        return services.teacher_platform.student_portal(profile["studentId"])

    @app.post("/api/v1/student/classrooms/join")
    async def student_join_classroom(body: ClassroomJoinInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return services.teacher_platform.join_classroom(profile["studentId"], body)

    @app.post(
        "/api/v1/student/classrooms/{classroom_id}/leave-requests",
        status_code=201,
    )
    async def student_request_classroom_leave(classroom_id: int, request: Request) -> dict:
        profile = require_role(request, "student")
        return services.teacher_platform.request_classroom_leave(profile["studentId"], classroom_id)

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

    @app.post("/api/v1/planner/diagnostics", status_code=201)
    async def create_planner_diagnostic(body: DiagnosticCreateInput) -> dict:
        return await services.diagnostics.create(body.model_dump(mode="json"))

    @app.post("/api/v1/planner/diagnostics/{diagnostic_id}/submit")
    async def submit_planner_diagnostic(
        diagnostic_id: str, body: DiagnosticSubmissionInput
    ) -> dict:
        return services.diagnostics.submit(
            diagnostic_id,
            body.student_id,
            [item.model_dump(mode="json") for item in body.responses],
        )

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

    @app.get("/api/v1/students/{student_id}/plans/latest")
    async def latest_plan(student_id: str, request: Request) -> dict:
        authenticated = getattr(request.state, "student_profile", None)
        if authenticated and authenticated["studentId"].lower() != student_id.lower():
            raise HTTPException(status_code=403, detail="无权读取其他学生的学习规划")
        agent_request = services.request(
            student_id=student_id,
            intent="get_plan",
            payload={"scope": "latest"},
        )
        return (await services.planner.ainvoke(agent_request)).model_dump(mode="json")

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
            "learning_diagnosis": services.learning_diagnosis.toolbox.capability_manifest(),
            "teacher_preparation": services.teacher_preparation.toolbox.capability_manifest(),
            "english_reading_language": services.english_learning.toolbox.capability_manifest(),
        }

    @app.get("/api/v1/exam-diagnostics/catalog")
    async def exam_diagnostic_catalog() -> dict:
        return services.exam_diagnostics.catalog()

    @app.get("/api/v1/exam-diagnostics/papers/{paper_id}")
    async def get_exam_diagnostic_paper(paper_id: str) -> dict:
        return services.exam_diagnostics.paper(paper_id)

    @app.post("/api/v1/exam-diagnostics/sessions", status_code=201)
    async def create_exam_diagnostic_session(body: ExamDiagnosticSessionCreate) -> dict:
        return services.exam_diagnostics.create_session(
            student_id=body.student_id,
            paper_id=body.paper_id,
            grade=body.grade.value,
            province_code=body.province_code,
            target_exam_year=body.target_exam_year,
        )

    @app.get("/api/v1/exam-diagnostics/sessions/{session_id}")
    async def get_exam_diagnostic_session(session_id: str, student_id: str) -> dict:
        return services.exam_diagnostics.get_session(session_id, student_id)

    @app.post("/api/v1/exam-diagnostics/sessions/{session_id}/questions/{question_id}/grade")
    async def grade_exam_constructed_response(
        session_id: str,
        question_id: str,
        student_id: str = Form(...),
        duration_seconds: int = Form(default=1, ge=1, le=14_400),
        images: list[UploadFile] = File(...),
    ) -> dict:
        processed = [
            services.homework_images.process(await upload.read(), upload.content_type)
            for upload in images[:3]
        ]
        return await services.exam_diagnostics.grade_constructed(
            session_id=session_id,
            student_id=student_id,
            question_id=question_id,
            image_data_urls=[item["data_url"] for item in processed],
            ocr_text="\n".join(item["text"] for item in processed if item["text"]),
            image_warnings=[warning for item in processed for warning in item["warnings"]],
            duration_seconds=duration_seconds,
        )

    @app.post("/api/v1/exam-diagnostics/sessions/{session_id}/submit")
    async def submit_exam_diagnostic(
        session_id: str,
        body: ExamDiagnosticSubmit,
    ) -> dict:
        result = services.exam_diagnostics.submit(
            session_id=session_id,
            student_id=body.student_id,
            objective_answers=[item.model_dump(mode="json") for item in body.answers],
            question_durations=body.question_durations,
        )
        if not result["evidence_records"]:
            return services.exam_diagnostics.attach_learning_diagnosis(
                session_id, body.student_id, None
            )
        session = services.exam_diagnostics.get_session(session_id, body.student_id)["session"]
        request = services.request(
            student_id=body.student_id,
            intent="ingest_learning_evidence",
            payload={
                "student_id": body.student_id,
                "grade": session["grade"],
                "province_code": session["province_code"],
                "subject": session["subject"],
                "target_exam_year": session["target_exam_year"],
                "diagnosis_request": "根据本套高考真题诊断卷的客观得分与主观题可核验作答，识别薄弱知识与下一步训练重点。",
                "diagnosis_window": "current_gaokao_diagnostic",
                "records": result["evidence_records"],
            },
            idempotency_key=f"learning_diagnosis:{session_id}",
        )
        diagnosis = await services.learning_diagnosis.ainvoke(request)
        return services.exam_diagnostics.attach_learning_diagnosis(
            session_id,
            body.student_id,
            diagnosis.model_dump(mode="json"),
        )

    async def invoke_learning_diagnosis(request: AgentRequest) -> dict:
        response = await services.learning_diagnosis.ainvoke(request)
        for message in response.messages:
            await services.coordinator.bus.publish(message)
        return response.model_dump(mode="json")

    @app.post("/api/v1/learning-diagnosis/run", status_code=201)
    async def run_learning_diagnosis(body: LearningDiagnosisRunInput) -> dict:
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        request = services.request(
            student_id=body.student_id,
            intent="initialize_learning_diagnosis",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_learning_diagnosis(request)

    @app.post("/api/v1/learning-diagnosis/record-images")
    async def process_learning_record_images(
        question_images: list[UploadFile] = File(default=[]),
        solution_images: list[UploadFile] = File(default=[]),
    ) -> dict:
        if not question_images and not solution_images:
            raise InputValidationError("请至少上传一张题目或解法图片")
        if len(question_images) > 3 or len(solution_images) > 3:
            raise InputValidationError("题目和解法图片分别最多上传 3 张")

        async def process_uploads(uploads: list[UploadFile]) -> list[dict]:
            return [
                services.homework_images.process(await upload.read(), upload.content_type)
                for upload in uploads
            ]

        question = await process_uploads(question_images)
        solution = await process_uploads(solution_images)
        return {
            "question_text": "\n".join(item["text"] for item in question if item["text"]),
            "solution_text": "\n".join(item["text"] for item in solution if item["text"]),
            "question_image_count": len(question),
            "solution_image_count": len(solution),
            "warnings": list(
                dict.fromkeys(
                    warning for item in [*question, *solution] for warning in item["warnings"]
                )
            ),
            "raw_images_persisted": False,
        }

    @app.post("/api/v1/learning-diagnosis/evidence", status_code=202)
    async def ingest_learning_evidence(body: LearningDiagnosisRunInput) -> dict:
        payload = body.model_dump(mode="json", exclude={"idempotency_key"})
        request = services.request(
            student_id=body.student_id,
            intent="ingest_learning_evidence",
            payload=payload,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_learning_diagnosis(request)

    @app.get("/api/v1/learning-diagnosis/students/{student_id}/state")
    async def get_learning_diagnosis_state(
        student_id: str, subject: Subject = Subject.MATHEMATICS
    ) -> dict:
        request = services.request(
            student_id=student_id,
            intent="get_learning_state",
            payload={"subject": subject.value},
        )
        return await invoke_learning_diagnosis(request)

    @app.get("/api/v1/learning-diagnosis/reports/{diagnosis_id}")
    async def get_learning_diagnosis_report(diagnosis_id: str, student_id: str) -> dict:
        request = services.request(
            student_id=student_id,
            intent="get_diagnosis_report",
            payload={"diagnosis_id": diagnosis_id},
        )
        return await invoke_learning_diagnosis(request)

    @app.post("/api/v1/learning-diagnosis/reviews", status_code=201)
    async def submit_learning_diagnosis_review(body: TeacherReviewInput) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="submit_teacher_review",
            payload=body.model_dump(mode="json", exclude={"idempotency_key"}),
            actor_type=ActorType.TEACHER,
            actor_id=body.reviewer_id,
            idempotency_key=body.idempotency_key,
        )
        return await invoke_learning_diagnosis(request)

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
        image_data_urls = [item["data_url"] for item in image_results if item.get("data_url")]
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
                "image_data_urls": image_data_urls,
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

    async def invoke_english(request: AgentRequest) -> dict:
        response = await services.english_learning.ainvoke(request)
        return response.model_dump(mode="json")

    def english_request(
        profile: dict, intent: str, payload: dict, *, idempotency_key: str | None = None
    ) -> AgentRequest:
        request = services.request(
            student_id=profile["studentId"],
            intent=intent,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return request.model_copy(update={"context": {"student_profile": profile}})

    @app.get("/api/v1/english-learning/dashboard")
    async def english_learning_dashboard(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(english_request(profile, "get_english_dashboard", {}))

    @app.get("/api/v1/english-learning/exam-blueprint")
    async def english_learning_exam_blueprint(request: Request) -> dict:
        require_role(request, "student")
        return {"status": "success", "result": services.english_learning.service.exam_blueprint()}

    @app.post("/api/v1/english-learning/tasks", status_code=201)
    async def execute_english_language_task(body: EnglishTaskInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "execute_english_language_task",
                body.model_dump(mode="json"),
            )
        )

    @app.put("/api/v1/english-learning/profile")
    async def update_english_learner_profile(
        body: EnglishLearnerProfileInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "update_english_learner_profile",
                body.model_dump(mode="json"),
            )
        )

    @app.delete("/api/v1/english-learning/records/{record_type}/{record_id}")
    async def delete_english_learning_record(
        record_type: str, record_id: str, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "delete_english_learning_record",
                {"record_type": record_type, "record_id": record_id},
            )
        )

    @app.post("/api/v1/english-learning/analyses", status_code=201)
    async def analyze_english_text(body: EnglishTextAnalysisInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(profile, "analyze_english_text", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/english-learning/sessions", status_code=201)
    async def create_english_training(body: EnglishTrainingCreateInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(profile, "create_english_training", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/english-learning/sessions/{session_id}/submission")
    async def submit_english_training(
        session_id: str, body: EnglishTrainingSubmissionInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "submit_english_training",
                {"session_id": session_id, **body.model_dump(mode="json")},
                idempotency_key=f"english_submission:{session_id}",
            )
        )

    @app.put("/api/v1/english-learning/reviews/{review_id}")
    async def complete_english_review(
        review_id: str, body: EnglishReviewCompletionInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "complete_english_review",
                {"review_id": review_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/orchestration/execute")
    async def execute_collaboration(body: CollaborationRequest) -> dict:
        return (await services.coordinator.coordinate(body)).model_dump(mode="json")

    return app


app = create_app()
