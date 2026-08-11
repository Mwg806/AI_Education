"""FastAPI application exposing the specification's core endpoints."""

from __future__ import annotations

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ai_education.agents.career_education_v1 import CareerEducationV1Agent
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
from ai_education.career_education_repository import CareerEducationRepository
from ai_education.config import Settings
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.diagnosis_repository import DiagnosisRepository
from ai_education.domain.career_education import (
    CareerChatInput,
    CareerCodingNextInput,
    CareerCodingSubmissionInput,
    CareerEducationOnboardingInput,
    CareerModeSwitchInput,
    CareerProjectAnswerInput,
    CareerProjectChatInput,
    CareerProjectStartInput,
    CareerSolutionRequestInput,
    GaokaoProgrammingNextInput,
    GaokaoProgrammingSubmissionInput,
)
from ai_education.domain.english_learning import (
    EnglishLanguageAnalysisInput,
    EnglishLearnerProfileInput,
    EnglishReadingBankProgressInput,
    EnglishReadingBankStartInput,
    EnglishReadingHintInput,
    EnglishReviewCompletionInput,
    EnglishTaskInput,
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
    EnglishVocabularySaveInput,
)
from ai_education.domain.enums import ActorType, AgentRole, Subject
from ai_education.domain.homework import HomeworkSessionCreate, VariantSubmission
from ai_education.domain.multi_agent import OrchestrationInput
from ai_education.domain.programming_learning import (
    CareerCodeSubmissionInput,
    CareerCodingTaskInput,
    CareerDiagnosticSubmission,
    CareerProgrammingProfileInput,
    ProgrammingCodeReviewInput,
    ProgrammingDiagnosticSubmission,
    ProgrammingInterviewAnswerInput,
    ProgrammingInterviewCreateInput,
    ProgrammingProfileInput,
    ProgrammingProjectHintInput,
    ProgrammingProjectRecommendationInput,
)
from ai_education.domain.protocols import (
    AgentRequest,
    AgentResponse,
    CollaborationRequest,
    Operator,
)
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.homework_repository import HomeworkRepository
from ai_education.llm.career_education import (
    StructuredCareerMentorGenerator,
    StructuredGaokaoProgrammingGrader,
    StructuredProjectMentorGenerator,
)
from ai_education.llm.diagnostic_generator import StructuredDiagnosticGenerator
from ai_education.llm.english_learning import (
    StructuredEnglishTrainingGenerator,
    StructuredLanguageTutorGenerator,
)
from ai_education.llm.exam_grader import StructuredExamGrader
from ai_education.llm.teacher_preparation import StructuredTeacherPreparationGenerator
from ai_education.mysql_persistence import MySQLPersistence
from ai_education.orchestration.coordinator import MultiAgentCoordinator
from ai_education.orchestration.intent_router import IntentRouter
from ai_education.orchestration.orchestrator import ProgressiveAgentOrchestrator
from ai_education.orchestration.registry import AgentRegistry
from ai_education.repositories import PlannerRepository
from ai_education.services.career_document import extract_project_upload
from ai_education.services.career_education_v1 import CareerEducationV1Service
from ai_education.services.curriculum_catalog import CurriculumCatalogService
from ai_education.services.diagnostic import DiagnosticService
from ai_education.services.english_knowledge import EnglishKnowledgeService
from ai_education.services.english_learning import EnglishLearningService
from ai_education.services.english_learning_v2 import (
    DEFAULT_READING_ROOT,
    EnglishLearningV2Service,
    StructuredEnglishStudyCoach,
)
from ai_education.services.english_material import MAX_MATERIAL_BYTES, EnglishMaterialService
from ai_education.services.exam_diagnosis import DEFAULT_BANK_ROOT, ExamDiagnosticService
from ai_education.services.homework_input import HomeworkImageService
from ai_education.services.onboarding import OnboardingService
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService
from ai_education.services.question_bank import QuestionBankService
from ai_education.services.shared.agent_execution_service import AgentExecutionService
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.model_router import ModelRouter
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.services.teacher_preparation import TeacherPreparationService
from ai_education.services.teacher_preparation_knowledge import TeachingKnowledgeBase
from ai_education.shared_learning_repository import SharedLearningRepository
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
        self.model_router = ModelRouter(self.settings)
        persistence_enabled = (
            self.settings.mysql_enabled if enable_persistence is None else enable_persistence
        )
        self.persistence = MySQLPersistence(self.settings) if persistence_enabled else None
        if self.persistence:
            self.persistence.initialize_schema()
        self.auth = AuthService(self.persistence, session_hours=self.settings.auth_session_hours)
        self.teacher_platform = TeacherPlatformService(self.persistence)
        self.repository = PlannerRepository(self.persistence)
        self.planner = PersonalizedLearningPlannerAgent(
            self.repository, self.settings, self.model_router.default_model
        )
        self.homework_repository = HomeworkRepository(self.persistence)
        self.question_bank = QuestionBankService()
        self.homework = HomeworkTutoringAgent(
            self.homework_repository,
            self.settings,
            self.question_bank,
            self.model_router.default_model,
        )
        self.english_learning_repository = EnglishLearningRepository(self.persistence)
        self.english_knowledge = EnglishKnowledgeService()
        self.english_materials = EnglishMaterialService()
        self.english_learning = EnglishReadingLanguageAgent(
            EnglishLearningService(
                self.english_learning_repository,
                StructuredEnglishTrainingGenerator(self.planner.plan_narrator.model),
                self.english_knowledge,
                StructuredLanguageTutorGenerator(self.planner.plan_narrator.model),
            )
        )
        self.english_learning_v2 = EnglishLearningV2Service(
            self.english_learning_repository,
            StructuredEnglishStudyCoach(self.planner.plan_narrator.model),
        )
        self.diagnosis_repository = DiagnosisRepository(self.persistence)
        self.learning_diagnosis = LearningDiagnosisAgent(
            self.diagnosis_repository,
            self.settings,
            self.model_router.default_model,
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
        self.programming_learning_repository = CareerEducationRepository(self.persistence)
        self.programming_knowledge = ProgrammingKnowledgeService()
        self.programming_learning = CareerEducationV1Agent(
            CareerEducationV1Service(
                self.programming_learning_repository,
                self.programming_knowledge,
                StructuredCareerMentorGenerator(self.planner.plan_narrator.model),
                StructuredProjectMentorGenerator(self.planner.plan_narrator.model),
                StructuredGaokaoProgrammingGrader(self.planner.plan_narrator.model),
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
        self.agent_registry.register(self.programming_learning)
        self.coordinator = MultiAgentCoordinator(self.agent_registry)
        self.shared_learning_repository = SharedLearningRepository(self.persistence)
        self.student_profile_service = StudentProfileService(self.shared_learning_repository)
        self.learning_event_service = LearningEventService(
            self.shared_learning_repository, self.student_profile_service
        )
        self.agent_execution = AgentExecutionService(
            self.agent_registry,
            self.student_profile_service,
            self.learning_event_service,
            self.shared_learning_repository,
            self.model_router,
            self.coordinator.bus,
        )
        self.coordinator.execution_service = self.agent_execution
        self.intent_router = IntentRouter(self.model_router)
        self.progressive_orchestrator = ProgressiveAgentOrchestrator(
            self.intent_router,
            self.agent_execution,
            self.student_profile_service,
            self.learning_event_service,
            self.shared_learning_repository,
        )

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
            "/api/v1/english-learning/reading-assets/",
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
    app.mount(
        "/api/v1/english-learning/reading-assets",
        StaticFiles(directory=DEFAULT_READING_ROOT / "assets", check_dir=True),
        name="english-reading-assets",
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
            "programming_learning_graph": "ready",
            "programming_learning_mode": "four_mode_career_project_coding_gaokao_v1",
            "career_mentor_generation_mode": (
                "llm"
                if services.programming_learning.service.career_mentor.available
                else "rule_fallback"
            ),
            "project_mentor_generation_mode": (
                "llm"
                if services.programming_learning.service.project_mentor.available
                else "rule_fallback"
            ),
            "gaokao_programming_grading_mode": (
                "multimodal_llm"
                if services.programming_learning.service.gaokao_grader.available
                else "evidence_fallback"
            ),
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

    async def invoke_agent_response(role: AgentRole, agent_request: AgentRequest) -> AgentResponse:
        response, _ = await services.agent_execution.invoke(role, agent_request)
        return response

    async def invoke_agent(role: AgentRole, agent_request: AgentRequest) -> dict:
        return (await invoke_agent_response(role, agent_request)).model_dump(mode="json")

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
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

    @app.get("/api/v1/students/{student_id}/plans/active")
    async def active_plan(student_id: str) -> dict:
        request = services.request(student_id=student_id, intent="get_plan", payload={})
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

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
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, agent_request)
        ).model_dump(mode="json")

    @app.post("/api/v1/learning-events")
    async def learning_event(body: LearningEventInput) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="practice_event",
            payload={"event": body.event},
            idempotency_key=body.idempotency_key,
        )
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

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
        response = await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
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
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

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
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

    @app.post("/api/v1/plans/{plan_id}/confirm")
    async def confirm_plan(plan_id: str, body: PlanConfirmation) -> dict:
        request = services.request(
            student_id=body.student_id,
            intent="confirm_plan",
            payload={"plan_id": plan_id, "expected_version": body.expected_version},
            idempotency_key=body.idempotency_key,
        )
        return (
            await invoke_agent_response(AgentRole.PERSONALIZED_LEARNING_PLANNER, request)
        ).model_dump(mode="json")

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
            "programming_learning": services.programming_learning.toolbox.capability_manifest(),
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
        diagnosis = await invoke_agent_response(AgentRole.LEARNING_DIAGNOSIS, request)
        return services.exam_diagnostics.attach_learning_diagnosis(
            session_id,
            body.student_id,
            diagnosis.model_dump(mode="json"),
        )

    async def invoke_learning_diagnosis(request: AgentRequest) -> dict:
        return await invoke_agent(AgentRole.LEARNING_DIAGNOSIS, request)

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
        return await invoke_agent(AgentRole.HOMEWORK_TUTOR, request)

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
        return await invoke_agent(AgentRole.ENGLISH_READING_LANGUAGE, request)

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

    @app.get("/api/v1/english-learning/reading-bank")
    async def english_reading_bank(request: Request) -> dict:
        profile = require_role(request, "student")
        return {
            "status": "success",
            "result": services.english_learning_v2.catalog(profile["studentId"]),
        }

    @app.post("/api/v1/english-learning/reading-bank/start", status_code=201)
    async def start_english_bank_reading(
        body: EnglishReadingBankStartInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return {
            "status": "success",
            "result": services.english_learning_v2.start(profile["studentId"], body.reading_id),
        }

    @app.put("/api/v1/english-learning/reading-bank/{reading_id}/progress")
    async def save_english_bank_progress(
        reading_id: str, body: EnglishReadingBankProgressInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return {
            "status": "success",
            "result": services.english_learning_v2.checkpoint(
                profile["studentId"],
                reading_id,
                body.answers,
                body.elapsed_seconds,
            ),
        }

    @app.post("/api/v1/english-learning/reading-bank/{reading_id}/submit")
    async def submit_english_bank_reading(
        reading_id: str, body: EnglishReadingBankProgressInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        result = services.english_learning_v2.submit(
            profile["studentId"],
            reading_id,
            body.answers,
            body.elapsed_seconds,
        )
        await services.learning_event_service.capture_english_reading_bank_submission(
            profile["studentId"], result
        )
        return {"status": "success", "result": result}

    @app.post("/api/v1/english-learning/language-analysis", status_code=201)
    async def analyze_english_language(
        body: EnglishLanguageAnalysisInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        learner = services.english_learning.service.learner_profile(profile["studentId"], profile)
        result = await services.english_learning_v2.analyze_language(
            profile["studentId"],
            body.text,
            body.mode,
            str(learner["estimated_level"]),
        )
        await services.learning_event_service.capture_english_language_analysis(
            profile["studentId"], body.text, body.mode, result
        )
        return {"status": "success", "result": result}

    @app.post("/api/v1/english-learning/vocabulary", status_code=201)
    async def save_english_vocabulary(body: EnglishVocabularySaveInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return {
            "status": "success",
            "result": services.english_learning_v2.save_vocabulary(
                profile["studentId"], body.source_text, body.words
            ),
        }

    @app.post("/api/v1/english-learning/speaking/assess", status_code=201)
    async def assess_english_speaking(
        request: Request,
        audio: UploadFile = File(...),  # noqa: B008
        topic: str = Form(...),
        duration_seconds: int = Form(...),
        browser_transcript: str = Form(""),
    ) -> dict:
        profile = require_role(request, "student")
        result = await services.english_learning_v2.assess_speaking(
            profile["studentId"],
            topic,
            await audio.read(15 * 1024 * 1024 + 1),
            audio.filename or "speaking.webm",
            audio.content_type or "audio/webm",
            max(1, min(duration_seconds, 600)),
            browser_transcript,
        )
        await services.learning_event_service.capture_english_speaking_assessment(
            profile["studentId"], result
        )
        return {"status": "success", "result": result}

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

    @app.post("/api/v1/english-learning/sessions/{session_id}/hint")
    async def english_reading_hint(
        session_id: str, body: EnglishReadingHintInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_english(
            english_request(
                profile,
                "get_english_reading_hint",
                {"session_id": session_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/english-learning/materials/extract")
    async def extract_english_reading_material(
        request: Request,
        material: UploadFile = File(...),  # noqa: B008
    ) -> dict:
        require_role(request, "student")
        result = services.english_materials.extract(
            await material.read(MAX_MATERIAL_BYTES + 1),
            material.content_type,
            material.filename,
        )
        return {"status": "success", "result": result}

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

    async def invoke_programming(request: AgentRequest) -> dict:
        return await invoke_agent(AgentRole.PROGRAMMING_LEARNING, request)

    def programming_request(
        profile: dict,
        intent: str,
        payload: dict,
        *,
        idempotency_key: str | None = None,
    ) -> AgentRequest:
        request = services.request(
            student_id=profile["studentId"],
            intent=intent,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return request.model_copy(update={"context": {"student_profile": profile}})

    @app.get("/api/v1/career-education/dashboard")
    async def career_education_dashboard(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(programming_request(profile, "v1_dashboard", {}))

    @app.post("/api/v1/career-education/onboarding")
    async def career_education_onboarding(
        body: CareerEducationOnboardingInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_onboarding", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/career-education/mode")
    async def switch_career_education_mode(body: CareerModeSwitchInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_switch_mode", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/career-education/career/chat")
    async def career_education_chat(body: CareerChatInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_career_chat", body.model_dump(mode="json"))
        )

    @app.get("/api/v1/career-education/projects")
    async def career_project_bank(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(programming_request(profile, "v1_list_projects", {}))

    @app.post("/api/v1/career-education/projects/start", status_code=201)
    async def start_career_project(body: CareerProjectStartInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_start_project", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/career-education/project/chat")
    async def career_project_chat(body: CareerProjectChatInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_project_chat", body.model_dump(mode="json"))
        )

    @app.get("/api/v1/career-education/projects/sessions/{session_id}")
    async def get_career_project_session(session_id: str, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_get_project", {"session_id": session_id})
        )

    @app.get("/api/v1/career-education/projects/sessions/{session_id}/documents/{document_type}")
    async def download_career_project_document(
        session_id: str, document_type: str, request: Request
    ) -> PlainTextResponse:
        profile = require_role(request, "student")
        content, filename = services.programming_learning.service.project_document(
            profile["studentId"], session_id, document_type
        )
        return PlainTextResponse(
            content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/v1/career-education/projects/sessions/{session_id}/submit-text")
    async def submit_career_project_text(
        session_id: str, body: CareerProjectAnswerInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_submit_project",
                {
                    "session_id": session_id,
                    "answer": body.model_dump(mode="json"),
                },
            )
        )

    @app.post("/api/v1/career-education/projects/sessions/{session_id}/upload")
    async def upload_career_project_answer(
        session_id: str, request: Request, file: UploadFile = File(...)
    ) -> dict:
        profile = require_role(request, "student")
        content = await file.read()
        text, metadata = extract_project_upload(
            filename=file.filename or "answer.txt",
            content_type=file.content_type,
            content=content,
            student_id=profile["studentId"],
            session_id=session_id,
        )
        result = services.programming_learning.service.submit_project_document(
            profile["studentId"], session_id, text, metadata
        )
        return {"status": "success", "result": result}

    @app.post("/api/v1/career-education/projects/sessions/{session_id}/evaluate")
    async def evaluate_career_project(session_id: str, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_evaluate_project", {"session_id": session_id})
        )

    @app.post("/api/v1/career-education/coding/next", status_code=201)
    async def next_career_coding_question(body: CareerCodingNextInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_next_question", body.model_dump(mode="json"))
        )

    @app.get("/api/v1/career-education/coding/questions")
    async def list_career_coding_questions(request: Request, difficulty: int | None = None) -> dict:
        profile = require_role(request, "student")
        if difficulty is not None and difficulty not in {1, 2, 3}:
            raise HTTPException(status_code=422, detail="难度只能是 1、2 或 3")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_list_coding_questions",
                {"difficulty": difficulty},
            )
        )

    @app.post(
        "/api/v1/career-education/gaokao-programming/next",
        status_code=201,
    )
    async def next_gaokao_programming_question(
        body: GaokaoProgrammingNextInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_gaokao_program_next",
                body.model_dump(mode="json"),
            )
        )

    @app.post("/api/v1/career-education/gaokao-programming/sessions/{session_id}/submit")
    async def submit_gaokao_programming_answer(
        session_id: str,
        body: GaokaoProgrammingSubmissionInput,
        request: Request,
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_gaokao_program_submit",
                {"session_id": session_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/career-education/gaokao-programming/sessions/{session_id}/submit-images")
    async def submit_gaokao_programming_images(
        session_id: str,
        request: Request,
        response_time_seconds: int = Form(default=60, ge=1, le=14_400),
        answer_text: str = Form(default=""),
        images: list[UploadFile] = File(...),
    ) -> dict:
        profile = require_role(request, "student")
        if not images or len(images) > 3:
            raise InputValidationError("请上传 1—3 张清晰的作答图片")
        processed = [
            services.homework_images.process(await upload.read(), upload.content_type)
            for upload in images
        ]
        ocr_text = "\n".join(item["text"] for item in processed if item["text"])
        combined_answer = (
            "\n".join(
                part
                for part in (
                    answer_text.strip(),
                    f"图片文字识别参考：\n{ocr_text}" if ocr_text else "",
                )
                if part
            )
            or "学生通过图片提交作答，请以图片中的手写内容为准。"
        )
        result = await services.programming_learning.service.submit_gaokao_programming_answer(
            profile["studentId"],
            session_id,
            GaokaoProgrammingSubmissionInput(
                answer=combined_answer,
                response_time_seconds=response_time_seconds,
            ),
            submission_method="image",
            image_data_urls=[item["data_url"] for item in processed],
            image_warnings=[warning for item in processed for warning in item["warnings"]],
        )
        return {"status": "success", "result": result}

    @app.get("/api/v1/career-education/gaokao-programming/history")
    async def gaokao_programming_history(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_gaokao_program_history", {})
        )

    @app.post("/api/v1/career-education/coding/sessions/{session_id}/submit")
    async def submit_career_coding_answer(
        session_id: str, body: CareerCodingSubmissionInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_submit_code",
                {"session_id": session_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/career-education/coding/sessions/{session_id}/hint")
    async def request_career_coding_hint(session_id: str, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "v1_coding_hint", {"session_id": session_id})
        )

    @app.post("/api/v1/career-education/coding/sessions/{session_id}/solution")
    async def request_career_coding_solution(
        session_id: str, body: CareerSolutionRequestInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "v1_coding_solution",
                {"session_id": session_id, **body.model_dump(mode="json")},
            )
        )

    @app.get("/api/v1/career-education/coding/history")
    async def career_coding_history(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(programming_request(profile, "v1_coding_history", {}))

    @app.get("/api/v1/programming-learning/dashboard")
    async def programming_learning_dashboard(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "get_programming_dashboard", {})
        )

    @app.put("/api/v1/programming-learning/career-profile")
    async def configure_career_profile(
        body: CareerProgrammingProfileInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "configure_career_profile", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/programming-learning/career-diagnostics", status_code=201)
    async def create_career_diagnostic(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "create_career_diagnostic", {})
        )

    @app.post("/api/v1/programming-learning/career-diagnostics/{diagnostic_id}/submission")
    async def submit_career_diagnostic(
        diagnostic_id: str,
        body: CareerDiagnosticSubmission,
        request: Request,
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "submit_career_diagnostic",
                {"diagnostic_id": diagnostic_id, **body.model_dump(mode="json")},
                idempotency_key=f"career_diagnostic:{diagnostic_id}",
            )
        )

    @app.post("/api/v1/programming-learning/coding/tasks", status_code=201)
    async def create_career_coding_task(body: CareerCodingTaskInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "create_career_coding_task", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/programming-learning/coding/tasks/{task_id}/submissions")
    async def submit_career_code(
        task_id: str, body: CareerCodeSubmissionInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "submit_career_code",
                {"task_id": task_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/programming-learning/coding/tasks/{task_id}/hint")
    async def get_career_coding_hint(task_id: str, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "get_career_coding_hint", {"task_id": task_id})
        )

    @app.put("/api/v1/programming-learning/profile")
    async def update_programming_profile(body: ProgrammingProfileInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "update_programming_profile",
                body.model_dump(mode="json"),
            )
        )

    @app.post("/api/v1/programming-learning/diagnostics", status_code=201)
    async def create_programming_diagnostic(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "create_programming_diagnostic", {})
        )

    @app.post("/api/v1/programming-learning/diagnostics/{diagnostic_id}/submission")
    async def submit_programming_diagnostic(
        diagnostic_id: str,
        body: ProgrammingDiagnosticSubmission,
        request: Request,
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "submit_programming_diagnostic",
                {
                    "diagnostic_id": diagnostic_id,
                    **body.model_dump(mode="json"),
                },
                idempotency_key=f"programming_diagnostic:{diagnostic_id}",
            )
        )

    @app.post("/api/v1/programming-learning/code-reviews", status_code=201)
    async def review_programming_code(body: ProgrammingCodeReviewInput, request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "review_python_code", body.model_dump(mode="json"))
        )

    @app.post("/api/v1/programming-learning/projects/recommendations", status_code=201)
    async def recommend_programming_project(
        body: ProgrammingProjectRecommendationInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "recommend_programming_project",
                body.model_dump(mode="json"),
            )
        )

    @app.post("/api/v1/programming-learning/projects/{project_id}/hints")
    async def get_programming_project_hint(
        project_id: str,
        body: ProgrammingProjectHintInput,
        request: Request,
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "get_programming_project_hint",
                {"project_id": project_id, **body.model_dump(mode="json")},
            )
        )

    @app.post("/api/v1/programming-learning/interviews", status_code=201)
    async def create_programming_interview(
        body: ProgrammingInterviewCreateInput, request: Request
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "create_programming_interview",
                body.model_dump(mode="json"),
            )
        )

    @app.post("/api/v1/programming-learning/interviews/{session_id}/answers")
    async def score_programming_interview_answer(
        session_id: str,
        body: ProgrammingInterviewAnswerInput,
        request: Request,
    ) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(
                profile,
                "score_programming_interview_answer",
                {"session_id": session_id, **body.model_dump(mode="json")},
            )
        )

    @app.get("/api/v1/programming-learning/weekly-report")
    async def programming_weekly_report(request: Request) -> dict:
        profile = require_role(request, "student")
        return await invoke_programming(
            programming_request(profile, "get_programming_weekly_report", {})
        )

    @app.post("/api/v1/orchestration/chat")
    async def orchestrate_learning(body: OrchestrationInput, request: Request) -> dict:
        profile = require_role(request, "student")
        result = await services.progressive_orchestrator.orchestrate(
            profile["studentId"],
            body,
            actor=Operator(type=ActorType.STUDENT, id=profile["studentId"]),
        )
        return result.model_dump(mode="json")

    @app.post("/api/v1/orchestration/teacher/chat")
    async def orchestrate_teacher_preparation(body: OrchestrationInput, request: Request) -> dict:
        profile = require_role(request, "teacher")
        context = dict(body.context)
        classroom_id = context.get("classroom_id")
        if classroom_id:
            detail = services.teacher_platform.classroom_detail(
                profile["teacherId"], int(classroom_id)
            )
            context.update(
                {
                    "classroom_id": int(classroom_id),
                    "classroom": detail["classroom"],
                    "diagnosis_summary": (
                        services.teacher_preparation.service.aggregate_class_diagnosis(
                            detail["students"]
                        )
                    ),
                }
            )
        secured = body.model_copy(update={"context": context})
        result = await services.progressive_orchestrator.orchestrate(
            f"teacher:{profile['teacherId']}",
            secured,
            actor=Operator(type=ActorType.TEACHER, id=profile["teacherId"]),
        )
        return result.model_dump(mode="json")

    @app.get("/api/v1/orchestration/profile")
    async def unified_learning_profile(request: Request) -> dict:
        profile = require_role(request, "student")
        result = await services.student_profile_service.get_profile(profile["studentId"])
        return {"status": "success", "profile": result.model_dump(mode="json")}

    @app.get("/api/v1/orchestration/memory")
    async def collaboration_memory(request: Request, limit: int = 12) -> dict:
        profile = require_role(request, "student")
        student_id = profile["studentId"]
        memory = services.shared_learning_repository.load_collaboration_memory(student_id)
        messages = services.shared_learning_repository.list_collaboration_messages(
            student_id, limit=max(1, min(limit, 40))
        )
        return {
            "status": "success",
            "memory": memory,
            "personalization_mode": (
                memory.get("personalization_mode") if memory else "standard_student_baseline"
            ),
            "messages": messages,
        }

    @app.get("/api/v1/orchestration/events")
    async def unified_learning_events(request: Request, limit: int = 50) -> dict:
        profile = require_role(request, "student")
        events = await services.learning_event_service.get_recent_events(
            profile["studentId"], max(1, min(limit, 200))
        )
        return {
            "status": "success",
            "events": [item.model_dump(mode="json") for item in events],
        }

    @app.get("/api/v1/orchestration/runs/{run_id}")
    async def orchestration_run(run_id: str, request: Request) -> dict:
        profile = require_role(request, "student")
        result = services.shared_learning_repository.load_run(run_id, profile["studentId"])
        if not result:
            raise HTTPException(status_code=404, detail="未找到该编排运行记录")
        return {"status": "success", "run": result}

    @app.post("/api/v1/orchestration/execute")
    async def execute_collaboration(body: CollaborationRequest) -> dict:
        return (await services.coordinator.coordinate(body)).model_dump(mode="json")

    return app


app = create_app()
