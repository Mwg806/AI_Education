"""LangGraph-based, source-grounded homework tutoring agent."""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.config import Settings
from ai_education.core.errors import (
    AIEducationError,
    InputValidationError,
    ModelUnavailableError,
)
from ai_education.domain.enums import AgentRole, MessageType, StandardStatus, Subject
from ai_education.domain.homework import (
    GuardResult,
    HomeworkSession,
    HomeworkSessionCreate,
    HomeworkTurnInput,
    HomeworkTurnRecord,
    QuestionContext,
    StudentStep,
    StudentWork,
)
from ai_education.domain.protocols import (
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ErrorDetail,
    Evidence,
    WarningDetail,
)
from ai_education.homework_repository import HomeworkRepository
from ai_education.llm.factory import create_chat_model
from ai_education.llm.homework_tutor import StructuredHomeworkTutor
from ai_education.prompts.homework import SUBJECT_POLICIES
from ai_education.services.homework_feedback import content_feedback
from ai_education.services.homework_guard import HomeworkOutputGuard
from ai_education.services.homework_knowledge import HomeworkKnowledgeService
from ai_education.services.policy import ExamPolicyService
from ai_education.services.question_bank import QuestionBankService
from ai_education.tools.homework import HomeworkToolbox


class HomeworkTutorState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    session: dict[str, Any]
    question: dict[str, Any]
    student_work: dict[str, Any]
    learning_stage: str
    user_intent: str
    direct_answer_request: bool
    policy_route: str
    question_bank_matches: list[dict[str, Any]]
    knowledge_matches: list[dict[str, Any]]
    secure_source_count: int
    candidate_response: dict[str, Any]
    guard_result: dict[str, Any]
    final_result: dict[str, Any]
    response_status: str
    lifecycle_status: str
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    next_node: str


class HomeworkTutoringAgent(BaseEducationAgent):
    """Second education agent: guided tutoring, not an answer generator."""

    def __init__(
        self,
        repository: HomeworkRepository | None = None,
        settings: Settings | None = None,
        question_bank: QuestionBankService | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.repository = repository or HomeworkRepository()
        self.settings = settings or Settings.from_env()
        self.question_bank = question_bank or QuestionBankService()
        self.knowledge = HomeworkKnowledgeService()
        self.policy_service = ExamPolicyService()
        self.guard = HomeworkOutputGuard()
        self.structured_tutor = StructuredHomeworkTutor(
            chat_model if chat_model is not None else create_chat_model(self.settings),
            provider=self.settings.llm_provider,
        )
        self.toolbox = HomeworkToolbox(self.question_bank, self.guard)
        self.langchain_tools = self.toolbox.as_langchain_tools()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="homework_tutoring_agent",
            role=AgentRole.HOMEWORK_TUTOR,
            version="1.0.0",
            description="面向新高考全国Ⅰ卷高中生的启发式作业辅导智能体",
            capabilities={
                "guided_solving",
                "question_structuring",
                "image_ocr_confirmation",
                "step_follow_up",
                "answer_verification",
                "error_diagnosis",
                "knowledge_review",
                "question_bank_retrieval",
                "variant_practice",
                "answer_leakage_prevention",
                "planner_evidence_feedback",
            },
            accepted_intents={
                "create_homework_session",
                "homework_turn",
                "confirm_ocr",
                "submit_homework_answer",
                "request_homework_variant",
                "submit_variant_answer",
                "get_homework_session",
            },
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        cached = self.repository.get_idempotent(request.idempotency_key)
        if cached:
            return AgentResponse.model_validate(cached)
        initial: HomeworkTutorState = {
            "request": request.model_dump(mode="json"),
            "intent": request.intent,
            "payload": request.payload,
            "warnings": [],
            "errors": [],
            "evidence": [],
            "messages": [],
            "response_status": StandardStatus.SUCCESS,
            "lifecycle_status": "received",
        }
        try:
            final = await self.graph.ainvoke(initial)
            response = self._to_response(request, final)
        except (ValidationError, InputValidationError) as exc:
            details = (
                exc.details
                if isinstance(exc, InputValidationError)
                else {
                    "fields": [
                        ".".join(str(part) for part in error["loc"]) for error in exc.errors()
                    ]
                }
            )
            response = self._error_response(
                request,
                status=StandardStatus.NEED_MORE_INFORMATION,
                lifecycle="waiting_for_data",
                code="HOMEWORK_INPUT_INVALID",
                message=str(
                    exc.message if isinstance(exc, InputValidationError) else "输入未通过结构校验"
                ),
                details=details,
            )
        except AIEducationError as exc:
            response = self._error_response(
                request,
                status=StandardStatus.FAILED,
                lifecycle="failed",
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        except Exception:
            response = self._error_response(
                request,
                status=StandardStatus.FAILED,
                lifecycle="failed",
                code="UNEXPECTED_HOMEWORK_AGENT_ERROR",
                message="作业辅导流程出现未预期错误，未释放答案或覆盖学习状态",
            )
        self.repository.put_idempotent(
            request.idempotency_key,
            response.model_dump(mode="json"),
        )
        return response

    def _build_graph(self):
        graph = StateGraph(HomeworkTutorState)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("create_session", self._create_session)
        graph.add_node("get_session", self._get_session_result)
        graph.add_node("load_context", self._load_context)
        graph.add_node("normalize_input", self._normalize_input)
        graph.add_node("request_parse_confirmation", self._request_parse_confirmation)
        graph.add_node("parse_question", self._parse_question)
        graph.add_node("respond_conversation", self._respond_conversation)
        graph.add_node("classify_intent_stage", self._classify_intent_stage)
        graph.add_node("retrieve_question_bank", self._retrieve_question_bank)
        graph.add_node("retrieve_knowledge", self._retrieve_knowledge)
        graph.add_node("select_tutoring_policy", self._select_tutoring_policy)
        graph.add_node("generate_hint", self._generate_hint)
        graph.add_node("analyze_student_step", self._analyze_student_step)
        graph.add_node("verify_answer", self._verify_answer)
        graph.add_node("generate_review", self._generate_review)
        graph.add_node("generate_variant", self._generate_variant)
        graph.add_node("answer_leakage_guard", self._answer_leakage_guard)
        graph.add_node("persist_turn", self._persist_turn)
        graph.add_node("publish_events", self._publish_events)
        graph.add_node("unsupported", self._unsupported)
        graph.add_node("finish", lambda state: state)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            lambda state: state["next_node"],
            {
                "create_session": "create_session",
                "get_session": "get_session",
                "load_context": "load_context",
                "unsupported": "unsupported",
            },
        )
        graph.add_edge("create_session", "finish")
        graph.add_edge("get_session", "finish")
        graph.add_edge("load_context", "normalize_input")
        graph.add_conditional_edges(
            "normalize_input",
            lambda state: state["next_node"],
            {
                "request_parse_confirmation": "request_parse_confirmation",
                "respond_conversation": "respond_conversation",
                "parse_question": "parse_question",
            },
        )
        graph.add_edge("request_parse_confirmation", "answer_leakage_guard")
        graph.add_edge("respond_conversation", "answer_leakage_guard")
        graph.add_edge("parse_question", "classify_intent_stage")
        graph.add_edge("classify_intent_stage", "retrieve_question_bank")
        graph.add_edge("retrieve_question_bank", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "select_tutoring_policy")
        graph.add_conditional_edges(
            "select_tutoring_policy",
            lambda state: state["policy_route"],
            {
                "generate_hint": "generate_hint",
                "analyze_student_step": "analyze_student_step",
                "verify_answer": "verify_answer",
                "generate_review": "generate_review",
                "generate_variant": "generate_variant",
            },
        )
        for node in (
            "generate_hint",
            "analyze_student_step",
            "verify_answer",
            "generate_review",
            "generate_variant",
        ):
            graph.add_edge(node, "answer_leakage_guard")
        graph.add_edge("answer_leakage_guard", "persist_turn")
        graph.add_edge("persist_turn", "publish_events")
        graph.add_edge("publish_events", "finish")
        graph.add_edge("unsupported", "finish")
        graph.add_edge("finish", END)
        return graph.compile()

    def _dispatch(self, state: HomeworkTutorState) -> dict[str, Any]:
        routes = {
            "create_homework_session": "create_session",
            "get_homework_session": "get_session",
            "homework_turn": "load_context",
            "confirm_ocr": "load_context",
            "submit_homework_answer": "load_context",
            "request_homework_variant": "load_context",
            "submit_variant_answer": "load_context",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    def _create_session(self, state: HomeworkTutorState) -> dict[str, Any]:
        data = HomeworkSessionCreate.model_validate(state["payload"])
        exam = self.policy_service.resolve(
            data.province_code,
            data.target_exam_year - 3,
            data.target_exam_year,
        )
        session = self.repository.create_session(
            HomeworkSession(
                student_id=data.student_id,
                grade=data.grade,
                province_code=data.province_code,
                target_exam_year=data.target_exam_year,
                exam_profile_id=exam.exam_profile_id,
                subject_hint=data.subject_hint,
                plan_task_id=data.plan_task_id,
            )
        )
        return {
            "final_result": {
                "session": session.model_dump(mode="json"),
                "next_action": "submit_question_or_image",
            },
            "lifecycle_status": session.status,
            "evidence": [
                Evidence(
                    source_type="exam_policy_config",
                    source_id=exam.policy_version,
                    description="作业辅导会话按省份和目标考试年份绑定全国新课标Ⅰ卷配置",
                    confidence=1.0,
                ).model_dump(mode="json")
            ],
        }

    def _get_session_result(self, state: HomeworkTutorState) -> dict[str, Any]:
        session_id = str(state["payload"].get("session_id", ""))
        session = self.repository.get_session(
            session_id,
            student_id=state["request"]["student_id"],
        )
        return {
            "final_result": {"session": session.model_dump(mode="json")},
            "lifecycle_status": session.status,
        }

    def _load_context(self, state: HomeworkTutorState) -> dict[str, Any]:
        payload = state["payload"]
        session_id = str(payload.get("session_id", ""))
        if not session_id and payload.get("question_id"):
            session = self.repository.session_for_question(str(payload["question_id"]))
        else:
            session = self.repository.get_session(
                session_id,
                student_id=state["request"]["student_id"],
            )
        if session.student_id != state["request"]["student_id"]:
            raise InputValidationError("会话与学生身份不匹配")
        return {"session": session.model_dump(mode="json")}

    def _normalize_input(self, state: HomeworkTutorState) -> dict[str, Any]:
        data = HomeworkTurnInput.model_validate(state["payload"])
        session = HomeworkSession.model_validate(state["session"])
        image_confidence = data.image_confidence
        if (
            image_confidence is not None
            and image_confidence < 0.8
            and not data.image_data_urls
            and state["intent"] != "confirm_ocr"
        ):
            return {
                "candidate_response": {
                    "action": "request_parse_confirmation",
                    "student_visible_content": {
                        "acknowledgement": "我已读取图片，但部分文字或公式不够确定。",
                        "guidance": data.image_text or "请重新拍摄完整、清晰且无反光的题目。",
                        "question_to_student": "上面的识别内容是否准确？请直接修改后确认。",
                        "warning": "未确认前不会继续解题，也不会猜测缺失条件。",
                    },
                    "pedagogical_metadata": {"ocr_confidence": image_confidence},
                    "confidence": image_confidence,
                },
                "user_intent": "confirm_ocr",
                "learning_stage": "unknown",
                "next_node": "request_parse_confirmation",
                "warnings": [
                    WarningDetail(
                        code="OCR_CONFIRMATION_REQUIRED",
                        message="OCR 置信度低于 0.80，已暂停辅导等待学生确认",
                        details={"warnings": data.image_warnings},
                    ).model_dump(mode="json")
                ],
            }
        existing = session.active_question.stem if session.active_question else ""
        current_message = (data.message or data.question_text).strip()
        classification_text = current_message
        if data.question_text.strip() and data.question_text.strip() != current_message:
            classification_text = f"{data.question_text.strip()}\n{current_message}"
        conversation_kind = self._conversation_kind(
            classification_text,
            has_active_question=bool(session.active_question),
            has_image=bool(data.image_text or data.image_data_urls),
        )
        if conversation_kind:
            return {
                "payload": {
                    **state["payload"],
                    "conversation_text": current_message,
                    "normalized_stem": existing,
                },
                "user_intent": conversation_kind,
                "learning_stage": "unknown",
                "next_node": "respond_conversation",
            }
        stem = (data.question_text or data.image_text or existing).strip()
        if not stem and data.image_data_urls:
            stem = "[图片题目：题干由多模态模型结合原图读取]"
        if not stem:
            raise InputValidationError("请提供文字题目、具体问题或清晰题目图片")
        return {
            "payload": {**state["payload"], "normalized_stem": stem},
            "next_node": "parse_question",
        }

    async def _generate_model_response(
        self,
        state: HomeworkTutorState,
        *,
        task_type: str,
        requested_action: str,
        subject: Subject,
        question: str,
        student_work: str,
        evidence: dict[str, Any],
        hint_level: int = 0,
    ) -> dict[str, Any] | None:
        if not self.structured_tutor.available:
            if self.settings.allow_rule_fallback:
                return None
            raise ModelUnavailableError(
                "作业辅导大模型尚未配置，已禁止使用规则模板代替模型回答",
                details={
                    "required": [
                        "AI_EDUCATION_LLM_ENABLED=true",
                        "AI_EDUCATION_LLM_MODEL",
                        "OPENAI_API_KEY",
                    ],
                    "provider": self.settings.llm_provider,
                },
            )
        data = HomeworkTurnInput.model_validate(state["payload"])
        session = HomeworkSession.model_validate(state["session"])
        history = [
            {
                "student": turn.student_message,
                "assistant": turn.student_visible_content,
                "action": turn.assistant_action,
            }
            for turn in session.turns[-8:]
        ]
        payload = {
            "task_type": task_type,
            "requested_action": requested_action,
            "subject_policy": SUBJECT_POLICIES[subject],
            "question": question or "当前没有固定作业题",
            "student_message": data.message or data.conversation_text or data.question_text,
            "student_work": student_work or "尚未作答",
            "conversation_history": json.dumps(history, ensure_ascii=False),
            "learning_stage": state.get("learning_stage", "unknown"),
            "hint_level": hint_level,
            "evidence": json.dumps(evidence, ensure_ascii=False),
        }
        try:
            generated = await self.structured_tutor.generate(
                payload,
                image_data_urls=data.image_data_urls,
            )
        except Exception as exc:
            if self.settings.allow_rule_fallback:
                return None
            raise ModelUnavailableError(
                "作业辅导大模型调用失败，请检查模型、API Key、Base URL 或网络连接",
                details={
                    "provider": self.settings.llm_provider,
                    "model": self.settings.llm_model,
                    "multimodal_request": bool(data.image_data_urls),
                },
            ) from exc
        if generated is None:
            if self.settings.allow_rule_fallback:
                return None
            raise ModelUnavailableError("作业辅导大模型没有返回有效结果")
        candidate = generated.model_dump(mode="json")
        candidate["action"] = requested_action
        candidate.setdefault("pedagogical_metadata", {}).update(
            {
                "generation_mode": "llm",
                "provider": self.settings.llm_provider,
                "model": self.settings.llm_model,
                "multimodal": bool(data.image_data_urls),
                "knowledge_source_ids": [
                    str(item.get("source_id"))
                    for item in evidence.get("curriculum_knowledge", [])[:4]
                ],
            }
        )
        return candidate

    async def _respond_conversation(self, state: HomeworkTutorState) -> dict[str, Any]:
        data = HomeworkTurnInput.model_validate(state["payload"])
        session = HomeworkSession.model_validate(state["session"])
        message = str(state["payload"].get("conversation_text") or data.message).strip()
        subject = data.subject or session.subject_hint or Subject.MATHEMATICS
        active_stem = session.active_question.stem if session.active_question else ""
        feedback = content_feedback(subject, active_stem, message)
        kind = state.get("user_intent", "general_chat")
        references = (
            self.knowledge.search(f"{active_stem} {message}", subject=subject, limit=4)
            if kind == "knowledge_question"
            else []
        )
        requested_action = (
            "knowledge_explanation" if kind == "knowledge_question" else "general_response"
        )
        model_candidate = await self._generate_model_response(
            state,
            task_type=kind,
            requested_action=requested_action,
            subject=subject,
            question=active_stem,
            student_work=data.student_work,
            evidence={"curriculum_knowledge": references, "question_bank": []},
        )
        if model_candidate is not None:
            return {
                "candidate_response": model_candidate,
                "knowledge_matches": references,
                "lifecycle_status": ("reviewing" if kind == "knowledge_question" else "guiding"),
            }
        normalized = re.sub(r"\s+", " ", message).strip()
        if re.fullmatch(r"(?:你好|您好|嗨|hello|hi|在吗)[！!。.?？ ]*", normalized, re.I):
            acknowledgement = "你好，我在。你可以像和老师对话一样直接问，不必先整理成固定格式。"
            guidance = (
                "我可以读取文字题目、你的解题步骤或题目图片；普通概念问题会直接解释，"
                "作业题会结合课程标准、知识分类和题库依据分步引导。"
            )
            question = "你现在想问一个知识点，还是发一道具体题目？"
        elif re.search(r"谢谢|感谢|明白了|懂了", normalized):
            acknowledgement = "不客气，我已经记住当前对话上下文。"
            guidance = "你可以继续追问原因、发下一步让我检查，或者上传另一道题的图片。"
            question = "要继续当前题目，还是换一个知识点？"
        elif re.search(r"你能|可以.*(?:做什么|帮什么)|怎么使用|如何使用|功能", normalized):
            acknowledgement = "我能正常回答基础学习问题，也能围绕作业进行分步辅导。"
            guidance = (
                "文字输入会按你的具体问题回复；图片会先做质量检查和 OCR，再根据识别到的题干分析；"
                "涉及作业答案时，我会解释概念、指出方法、检查步骤，但不会直接给可抄写的最终答案。"
            )
            question = "你可以现在发一个概念问题、一道题或一张清晰的题目图片。"
        else:
            source_note = ""
            if references:
                source_note = f"本地知识库将它关联到“{references[0]['title']}”。"
            acknowledgement = f"我读到了你的问题：“{normalized[:120]}”。"
            if re.search(r"为什么|原因|作用", normalized):
                guidance = f"{feedback.concept}{source_note}理解原因时，重点是：{feedback.method}"
            elif re.search(r"什么是|是什么意思|概念|定义", normalized):
                guidance = f"{feedback.concept}{source_note}应用时还要检查：{feedback.checkpoint}。"
            else:
                guidance = f"{feedback.concept}{source_note}{feedback.method}"
            question = feedback.next_prompt
        return {
            "candidate_response": {
                "action": "knowledge_explanation"
                if kind == "knowledge_question"
                else "general_response",
                "student_visible_content": {
                    "acknowledgement": acknowledgement,
                    "guidance": guidance,
                    "question_to_student": question,
                    "warning": (
                        "如果你发的是正式作业题，我会提供可继续思考的指导，但不直接给最终答案。"
                        if kind == "knowledge_question"
                        else ""
                    ),
                },
                "pedagogical_metadata": {
                    "knowledge_ids": [
                        str(item.get("module_id") or item.get("source_id"))
                        for item in references[:3]
                    ],
                    "response_kind": kind,
                },
                "confidence": 0.86 if kind == "general_chat" else (0.84 if references else 0.68),
            },
            "knowledge_matches": references,
            "lifecycle_status": "reviewing" if kind == "knowledge_question" else "guiding",
        }

    def _request_parse_confirmation(self, state: HomeworkTutorState) -> dict[str, Any]:
        return {
            "lifecycle_status": "waiting_for_confirmation",
            "response_status": StandardStatus.NEED_MORE_INFORMATION,
        }

    def _parse_question(self, state: HomeworkTutorState) -> dict[str, Any]:
        session = HomeworkSession.model_validate(state["session"])
        data = HomeworkTurnInput.model_validate(state["payload"])
        stem = str(state["payload"]["normalized_stem"])
        subject = data.subject or session.subject_hint or self._infer_subject(stem)
        parse_confidence = data.image_confidence if data.image_confidence is not None else 0.96
        options = [
            line.strip()
            for line in stem.splitlines()
            if re.match(r"^[A-DＡ-Ｄ][.、．\s]", line.strip(), re.I)
        ]
        current = session.active_question
        if current and current.stem == stem and current.subject == subject:
            question = current
        else:
            question = QuestionContext(
                session_id=session.session_id,
                student_id=session.student_id,
                exam_profile_id=session.exam_profile_id,
                subject=subject,
                grade=session.grade,
                question_type=self._question_type(stem, options),
                source_type=(
                    "image_upload" if data.image_text or data.image_data_urls else "student_text"
                ),
                stem=stem,
                options=options,
                parse_confidence=parse_confidence or 0,
                uncertain_fields=data.image_warnings,
            )
        work_text = data.student_work.strip()
        completion = "empty"
        if work_text:
            completion = (
                "completed"
                if state["intent"] in {"submit_homework_answer", "submit_variant_answer"}
                or data.intent == "submit_answer"
                else "partial"
            )
        steps = [
            StudentStep(sequence=index, content=line.strip(), confidence=parse_confidence or 1)
            for index, line in enumerate(work_text.splitlines(), 1)
            if line.strip()
        ]
        work = StudentWork(
            question_id=question.question_id,
            student_id=session.student_id,
            input_mode="mixed"
            if (data.image_text or data.image_data_urls) and data.message
            else "question_image"
            if data.image_text or data.image_data_urls
            else "text",
            raw_text=work_text,
            steps=steps,
            final_answer=work_text if completion == "completed" else None,
            completion_status=completion,
            parse_confidence=parse_confidence or 0,
        )
        return {
            "question": question.model_dump(mode="json"),
            "student_work": work.model_dump(mode="json"),
            "lifecycle_status": "question_ready",
        }

    def _classify_intent_stage(self, state: HomeworkTutorState) -> dict[str, Any]:
        data = HomeworkTurnInput.model_validate(state["payload"])
        work = StudentWork.model_validate(state["student_work"])
        direct = bool(
            re.search(
                r"(?:直接|只要|赶时间).{0,8}(?:答案|结果|选项)|告诉我选[什么哪]|完整(?:代码|范文|解答)",
                f"{data.message}\n{data.question_text}",
            )
        )
        intent = data.intent
        if intent == "request_hint":
            if re.search(r"知识点|公式|概念|回顾", data.message):
                intent = "request_knowledge_review"
            elif re.search(r"检查|对不对|是否正确|这一步", data.message):
                intent = "check_step"
        if state["intent"] == "submit_homework_answer":
            intent = "submit_answer"
        elif state["intent"] == "request_homework_variant":
            intent = "request_similar_question"
        elif state["intent"] == "submit_variant_answer":
            intent = "submit_answer"
        elif state["intent"] == "confirm_ocr":
            intent = "confirm_ocr"
        stage = (
            "completed_attempt"
            if work.completion_status == "completed"
            else "partial_attempt"
            if work.completion_status == "partial"
            else "no_attempt"
        )
        return {
            "user_intent": intent,
            "learning_stage": stage,
            "direct_answer_request": direct,
        }

    def _retrieve_question_bank(self, state: HomeworkTutorState) -> dict[str, Any]:
        question = QuestionContext.model_validate(state["question"])
        session = HomeworkSession.model_validate(state["session"])
        data = HomeworkTurnInput.model_validate(state["payload"])
        live_query = "\n".join(
            item for item in (question.stem, data.message, data.student_work) if item.strip()
        )
        matches = self.question_bank.search(
            live_query,
            subject=question.subject,
            province=session.province_code,
            limit=5,
        )
        secure_matches = self.question_bank.search(
            live_query,
            subject=question.subject,
            province=session.province_code,
            include_secure=True,
            limit=10,
        )
        topics = [item.topic for item in matches if item.topic]
        knowledge_ids = [self._knowledge_id(question.subject, topic) for topic in topics[:3]]
        if not knowledge_ids:
            knowledge_ids = [f"{question.subject.value}:pending_mapping"]
        question = question.model_copy(
            update={
                "knowledge_ids": knowledge_ids,
                "source_evidence": matches,
                "gaokao_relevance": 0.82 if matches else 0.6,
            }
        )
        evidence = [
            Evidence(
                source_type="question_bank_metadata",
                source_id=item.source_id,
                description=f"2026 五三 {item.edition} 版 · {item.topic or item.title}",
                confidence=item.confidence,
                metadata={
                    "relative_path": item.relative_path,
                    "content_role": item.content_role,
                    "region": item.region,
                },
            ).model_dump(mode="json")
            for item in matches
        ]
        return {
            "question": question.model_dump(mode="json"),
            "question_bank_matches": [item.model_dump(mode="json") for item in matches],
            "secure_source_count": sum(item.secure_content_available for item in secure_matches),
            "evidence": evidence,
        }

    def _retrieve_knowledge(self, state: HomeworkTutorState) -> dict[str, Any]:
        question = QuestionContext.model_validate(state["question"])
        data = HomeworkTurnInput.model_validate(state["payload"])
        query = "\n".join(
            item for item in (question.stem, data.message, data.student_work) if item.strip()
        )
        references = self.knowledge.search(query, subject=question.subject, limit=4)
        evidence = [*state.get("evidence", [])]
        evidence.extend(
            Evidence(
                source_type="curriculum_knowledge",
                source_id=str(item["source_id"]),
                description=f"{item['title']} · {item['document_type']}",
                confidence=0.92 if item.get("authority_level") == "A" else 0.82,
                metadata={
                    "document_id": item.get("document_id"),
                    "page_start": item.get("page_start"),
                    "page_end": item.get("page_end"),
                    "review_status": item.get("review_status"),
                },
            ).model_dump(mode="json")
            for item in references
        )
        return {"knowledge_matches": references, "evidence": evidence}

    def _select_tutoring_policy(self, state: HomeworkTutorState) -> dict[str, Any]:
        intent = state["user_intent"]
        stage = state["learning_stage"]
        if intent == "request_similar_question":
            route = "generate_variant"
        elif intent == "request_knowledge_review":
            route = "generate_review"
        elif intent == "check_step":
            route = "analyze_student_step"
        elif intent == "submit_answer" or stage == "completed_attempt":
            route = "verify_answer"
        else:
            route = "generate_hint"
        return {"policy_route": route}

    async def _generate_hint(self, state: HomeworkTutorState) -> dict[str, Any]:
        question = QuestionContext.model_validate(state["question"])
        work = StudentWork.model_validate(state["student_work"])
        session = HomeworkSession.model_validate(state["session"])
        data = HomeworkTurnInput.model_validate(state["payload"])
        next_level = min(session.hint_runtime.current_level + 1, session.hint_runtime.max_level)
        candidate = await self._generate_model_response(
            state,
            task_type=(
                "direct_answer_safety_guidance"
                if state.get("direct_answer_request")
                else "stepwise_homework_guidance"
            ),
            requested_action="release_hint",
            subject=question.subject,
            question=question.stem,
            student_work=work.raw_text,
            evidence={
                "question_bank": state.get("question_bank_matches", [])[:5],
                "curriculum_knowledge": state.get("knowledge_matches", [])[:4],
            },
            hint_level=next_level,
        )
        if candidate is None:
            candidate = self._fallback_hint(
                question,
                work,
                next_level,
                direct=bool(state.get("direct_answer_request")),
                message=data.message,
                knowledge_matches=state.get("knowledge_matches", []),
                image_based=bool(data.image_text or data.image_data_urls),
                image_warnings=data.image_warnings,
            )
        candidate.setdefault("pedagogical_metadata", {})["hint_level"] = next_level
        candidate["pedagogical_metadata"]["knowledge_ids"] = question.knowledge_ids
        return {"candidate_response": candidate, "lifecycle_status": "guiding"}

    async def _analyze_student_step(self, state: HomeworkTutorState) -> dict[str, Any]:
        work = StudentWork.model_validate(state["student_work"])
        question = QuestionContext.model_validate(state["question"])
        latest = work.steps[-1].content if work.steps else "尚未提供具体步骤"
        references = state.get("knowledge_matches", [])
        candidate = await self._generate_model_response(
            state,
            task_type="student_step_check",
            requested_action="check_step",
            subject=question.subject,
            question=question.stem,
            student_work=work.raw_text,
            evidence={
                "question_bank": state.get("question_bank_matches", [])[:5],
                "curriculum_knowledge": references[:4],
            },
        )
        if candidate is not None:
            candidate.setdefault("pedagogical_metadata", {})["target_step"] = (
                work.steps[-1].step_id if work.steps else None
            )
            return {"candidate_response": candidate, "lifecycle_status": "guiding"}
        feedback = content_feedback(question.subject, question.stem, latest)
        source_note = f"课程知识库关联到“{references[0]['title']}”。" if references else ""
        return {
            "candidate_response": {
                "action": "check_step",
                "student_visible_content": {
                    "acknowledgement": f"我正在检查你本轮写的内容：“{latest[:120]}”。",
                    "guidance": (
                        f"这一步属于“{feedback.topic}”。{source_note}{feedback.method}"
                        f"针对你写的这一步，重点核对：{feedback.checkpoint}。"
                    ),
                    "question_to_student": feedback.next_prompt,
                    "warning": "当前未取得与本题唯一对应的评分对照，不会把方法检查误报成正误结论。",
                },
                "pedagogical_metadata": {
                    "target_step": work.steps[-1].step_id if work.steps else None
                },
                "confidence": 0.72,
            },
            "lifecycle_status": "guiding",
        }

    async def _verify_answer(self, state: HomeworkTutorState) -> dict[str, Any]:
        work = StudentWork.model_validate(state["student_work"])
        question = QuestionContext.model_validate(state["question"])
        if not work.raw_text:
            raise InputValidationError("提交完整作答前，请先填写自己的过程或答案")
        candidate = await self._generate_model_response(
            state,
            task_type="completed_answer_review",
            requested_action="answer_verification",
            subject=question.subject,
            question=question.stem,
            student_work=work.raw_text,
            evidence={
                "question_bank": state.get("question_bank_matches", [])[:5],
                "curriculum_knowledge": state.get("knowledge_matches", [])[:4],
                "verification_rule": (
                    "没有唯一题号与可信评分答案映射时，不得宣称答案完全正确或错误"
                ),
            },
        )
        if candidate is not None:
            if not candidate.get("verification"):
                candidate["verification"] = {
                    "result": "model_review_without_unique_rubric",
                    "issues": [],
                    "next_action": "check_step",
                }
            return {
                "candidate_response": candidate,
                "response_status": StandardStatus.PARTIAL_SUCCESS,
                "lifecycle_status": "verifying",
            }
        feedback = content_feedback(question.subject, question.stem, work.raw_text)
        issue = (
            "当前作答只有结论，主观题还需要补充可核验过程。"
            if len(work.steps) <= 1 and question.question_type != "multiple_choice"
            else (
                f"作答过程已记录；请重点复核{feedback.checkpoint}。"
                "当前没有与本题唯一对应的可信评分答案，暂不猜测正误。"
            )
        )
        return {
            "candidate_response": {
                "action": "answer_verification",
                "student_visible_content": {
                    "acknowledgement": f"我已读取你的作答：{work.raw_text[:100]}",
                    "guidance": f"本题属于“{feedback.topic}”。{feedback.method}{issue}",
                    "question_to_student": (
                        "请指出你最不确定的一步，我会先检查该步的条件、方法和表达。"
                    ),
                    "warning": "题库命中只作为来源证据；未确认题号与答案映射前不会宣称对错。",
                },
                "verification": {
                    "result": "uncertain",
                    "correct_steps": [],
                    "issues": [issue],
                    "next_action": "check_step",
                },
                "pedagogical_metadata": {"knowledge_ids": question.knowledge_ids},
                "confidence": 0.7,
            },
            "response_status": StandardStatus.PARTIAL_SUCCESS,
            "lifecycle_status": "verifying",
        }

    async def _generate_review(self, state: HomeworkTutorState) -> dict[str, Any]:
        question = QuestionContext.model_validate(state["question"])
        work = StudentWork.model_validate(state["student_work"])
        feedback = content_feedback(question.subject, question.stem, work.raw_text)
        topic = next(
            (
                item.get("topic")
                for item in state.get("question_bank_matches", [])
                if item.get("topic")
            ),
            feedback.topic,
        )
        references = state.get("knowledge_matches", [])
        candidate = await self._generate_model_response(
            state,
            task_type="knowledge_review",
            requested_action="knowledge_review",
            subject=question.subject,
            question=question.stem,
            student_work=work.raw_text,
            evidence={
                "question_bank": state.get("question_bank_matches", [])[:5],
                "curriculum_knowledge": references[:4],
                "retrieved_topic": topic,
            },
        )
        if candidate is not None:
            return {"candidate_response": candidate, "lifecycle_status": "reviewing"}
        source_note = f"课程知识库同时命中“{references[0]['title']}”。" if references else ""
        return {
            "candidate_response": {
                "action": "knowledge_review",
                "student_visible_content": {
                    "acknowledgement": f"我已根据当前题目关联到“{topic}”，不是使用固定学科模板。",
                    "guidance": (
                        f"{feedback.concept}{source_note}{feedback.method}"
                        f"自检重点：{feedback.checkpoint}。"
                    ),
                    "question_to_student": feedback.next_prompt,
                    "warning": (
                        "知识点名称同时参考题目文字、课程知识库与题库元数据；不读取或展示隔离答案。"
                    ),
                },
                "pedagogical_metadata": {"knowledge_ids": question.knowledge_ids},
                "confidence": 0.76,
            },
            "lifecycle_status": "reviewing",
        }

    async def _generate_variant(self, state: HomeworkTutorState) -> dict[str, Any]:
        matches = state.get("question_bank_matches", [])
        question = QuestionContext.model_validate(state["question"])
        work = StudentWork.model_validate(state["student_work"])
        source = matches[0] if matches else None
        if source:
            guidance = f"已定位同专题训练资源：{source.get('topic') or source.get('title')}。"
            locator = {
                key: source.get(key)
                for key in ("source_id", "title", "topic", "edition", "region", "file_type")
            }
        else:
            guidance = "当前没有足够可靠的同源题库命中，暂不伪造变式题。"
            locator = None
        variant_id = f"variant_{uuid4().hex[:14]}"
        candidate = await self._generate_model_response(
            state,
            task_type="similar_practice_generation",
            requested_action="variant_practice",
            subject=question.subject,
            question=question.stem,
            student_work=work.raw_text,
            evidence={
                "question_bank": matches[:5],
                "curriculum_knowledge": state.get("knowledge_matches", [])[:4],
                "variant_rule": "保持同一核心考点，改变数值或情境，不附答案",
            },
        )
        if candidate is not None:
            candidate["variant_package"] = {
                "variant_id": variant_id,
                "origin_question_id": question.question_id,
                "source_locator": locator,
                "knowledge_ids": question.knowledge_ids,
                "synthetic_variant": True,
                "release_policy": "after_student_submission",
            }
            return {"candidate_response": candidate, "lifecycle_status": "variant_training"}
        return {
            "candidate_response": {
                "action": "variant_practice",
                "student_visible_content": {
                    "acknowledgement": "同类训练会保持核心考点一致，并隔离答案。",
                    "guidance": guidance,
                    "question_to_student": "你希望先做同难度训练，还是先降低一个难度台阶？",
                    "warning": "当前返回经检索的练习定位，不把题库答案或解析发送到学生端。",
                },
                "variant_package": {
                    "variant_id": variant_id,
                    "origin_question_id": question.question_id,
                    "source_locator": locator,
                    "knowledge_ids": question.knowledge_ids,
                    "synthetic_variant": False,
                    "release_policy": "after_student_submission",
                },
                "pedagogical_metadata": {"knowledge_ids": question.knowledge_ids},
                "confidence": 0.82 if source else 0.45,
            },
            "lifecycle_status": "variant_training",
        }

    def _answer_leakage_guard(self, state: HomeworkTutorState) -> dict[str, Any]:
        session = HomeworkSession.model_validate(state["session"])
        completed = state.get("learning_stage") == "completed_attempt"
        candidate = state["candidate_response"]
        guard = self.guard.inspect(
            candidate,
            completed_attempt=completed,
            cumulative_budget=session.hint_runtime.cumulative_leakage_budget,
        )
        if not guard.passed:
            candidate = self.guard.sanitize(candidate, guard.risk_types)
            guard = guard.model_copy(update={"sanitized": True})
        return {
            "candidate_response": candidate,
            "guard_result": guard.model_dump(mode="json"),
        }

    def _persist_turn(self, state: HomeworkTutorState) -> dict[str, Any]:
        session = HomeworkSession.model_validate(state["session"])
        data = HomeworkTurnInput.model_validate(state["payload"])
        candidate = state["candidate_response"]
        guard = GuardResult.model_validate(state["guard_result"])
        before = session.hint_runtime.current_level
        after = int(candidate.get("pedagogical_metadata", {}).get("hint_level", before))
        hint_runtime = session.hint_runtime.model_copy(
            update={
                "current_level": after,
                "released_hint_ids": [
                    *session.hint_runtime.released_hint_ids,
                    f"hint_{session.session_id}_{len(session.turns) + 1}",
                ]
                if candidate.get("action") == "release_hint"
                else session.hint_runtime.released_hint_ids,
                "student_attempt_count": session.hint_runtime.student_attempt_count
                + int(state.get("learning_stage") in {"partial_attempt", "completed_attempt"}),
                "hint_dependency_score": min(1.0, after * 0.12),
                "cumulative_leakage_budget": min(
                    1.0,
                    session.hint_runtime.cumulative_leakage_budget + after * 0.035,
                ),
            }
        )
        status_map = {
            "request_parse_confirmation": "waiting_for_confirmation",
            "release_hint": "waiting_for_student",
            "check_step": "waiting_for_student",
            "answer_verification": "verifying",
            "knowledge_review": "reviewing",
            "knowledge_explanation": "reviewing",
            "general_response": "waiting_for_student",
            "variant_practice": "variant_training",
            "request_student_attempt": "waiting_for_student",
        }
        question = (
            QuestionContext.model_validate(state["question"])
            if state.get("question")
            else session.active_question
        )
        work = (
            StudentWork.model_validate(state["student_work"])
            if state.get("student_work")
            else session.student_work
        )
        updated = session.model_copy(
            update={
                "active_question": question,
                "student_work": work,
                "hint_runtime": hint_runtime,
                "status": status_map.get(candidate.get("action"), "waiting_for_student"),
            }
        )
        turn = HomeworkTurnRecord(
            session_id=session.session_id,
            trace_id=state["request"]["trace_id"],
            user_intent=state.get("user_intent", "confirm_ocr"),
            learning_stage=state.get("learning_stage", "unknown"),
            assistant_action=str(candidate.get("action", "unknown")),
            student_message=(
                data.message
                or data.student_work
                or data.question_text
                or ("[用户上传了题目图片]" if data.image_data_urls else "")
            ),
            student_visible_content=candidate["student_visible_content"],
            hint_level_before=before,
            hint_level_after=after,
            guard_result=guard,
            evidence_refs=[item.get("source_id", "") for item in state.get("evidence", [])],
        )
        saved = self.repository.append_turn(updated, turn, expected_version=session.state_version)
        variant = candidate.get("variant_package")
        if variant and variant.get("variant_id"):
            self.repository.register_variant(str(variant["variant_id"]), saved.session_id)
        self.repository.audit(
            {
                "trace_id": state["request"]["trace_id"],
                "student_id_hash": uuid4().hex[:12],
                "session_id": saved.session_id,
                "question_id": question.question_id if question else None,
                "state_version": saved.state_version,
                "node_path": [
                    "parse_question",
                    state.get("policy_route", "request_parse_confirmation"),
                    "answer_leakage_guard",
                ],
                "guard_score": guard.risk_score,
                "decision": candidate.get("action"),
                "prompt_version": "HOMEWORK_TUTOR_GLOBAL_SYSTEM_V2",
            }
        )
        return {
            "session": saved.model_dump(mode="json"),
            "lifecycle_status": saved.status,
        }

    def _publish_events(self, state: HomeworkTutorState) -> dict[str, Any]:
        session = HomeworkSession.model_validate(state["session"])
        question = session.active_question
        work = session.student_work
        candidate = state["candidate_response"]
        messages: list[dict[str, Any]] = []
        planner_feedback: dict[str, Any] | None = None
        if (
            question
            and work
            and work.completion_status == "completed"
            and state.get("learning_stage") == "completed_attempt"
        ):
            verification = candidate.get("verification", {})
            planner_feedback = {
                "event_name": "homework.knowledge_evidence.created",
                "question_id": question.question_id,
                "task_id": session.plan_task_id,
                "subject": question.subject,
                "knowledge_ids": question.knowledge_ids,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "verification_result": verification.get("result", "uncertain"),
                "hint_dependency_score": session.hint_runtime.hint_dependency_score,
                "evidence_quality": round(question.parse_confidence * 0.8, 3),
            }
            messages.append(
                AgentMessage(
                    trace_id=state["request"]["trace_id"],
                    message_type=MessageType.EVENT,
                    sender=AgentRole.HOMEWORK_TUTOR,
                    recipient=AgentRole.PERSONALIZED_LEARNING_PLANNER,
                    student_id=session.student_id,
                    payload=planner_feedback,
                    evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
                ).model_dump(mode="json")
            )
        public_matches = [
            {
                key: item.get(key)
                for key in (
                    "source_id",
                    "title",
                    "subject",
                    "edition",
                    "region",
                    "content_role",
                    "topic",
                    "file_type",
                    "confidence",
                )
            }
            for item in state.get("question_bank_matches", [])
        ]
        return {
            "messages": messages,
            "final_result": {
                "session": session.model_dump(mode="json"),
                "question": question.model_dump(mode="json") if question else None,
                "tutoring": candidate,
                "question_bank_matches": public_matches,
                "knowledge_sources": [
                    {
                        key: item.get(key)
                        for key in (
                            "source_id",
                            "title",
                            "document_type",
                            "authority_level",
                            "review_status",
                            "summary",
                            "source_url",
                            "page_start",
                            "page_end",
                            "module_id",
                        )
                    }
                    for item in state.get("knowledge_matches", [])
                ],
                "question_bank_secure_source_count": state.get("secure_source_count", 0),
                "planner_feedback": planner_feedback,
                "guard": state.get("guard_result", {}),
            },
        }

    def _unsupported(self, state: HomeworkTutorState) -> dict[str, Any]:
        return {
            "response_status": StandardStatus.FAILED,
            "lifecycle_status": "failed",
            "errors": [
                ErrorDetail(
                    code="UNSUPPORTED_HOMEWORK_INTENT",
                    message=f"作业辅导 Agent 不支持意图：{state['intent']}",
                ).model_dump(mode="json")
            ],
        }

    def _to_response(self, request: AgentRequest, state: HomeworkTutorState) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.HOMEWORK_TUTOR,
            status=StandardStatus(state.get("response_status", StandardStatus.SUCCESS)),
            lifecycle_status=state.get("lifecycle_status", "failed"),
            result=state.get("final_result", {}),
            messages=[AgentMessage.model_validate(item) for item in state.get("messages", [])],
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            warnings=[WarningDetail.model_validate(item) for item in state.get("warnings", [])],
            errors=[ErrorDetail.model_validate(item) for item in state.get("errors", [])],
            data_version=request.data_version,
        )

    @staticmethod
    def _error_response(
        request: AgentRequest,
        *,
        status: StandardStatus,
        lifecycle: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            trace_id=request.trace_id,
            agent_role=AgentRole.HOMEWORK_TUTOR,
            status=status,
            lifecycle_status=lifecycle,
            errors=[ErrorDetail(code=code, message=message, details=details or {})],
            data_version=request.data_version,
        )

    @staticmethod
    def _conversation_kind(
        message: str,
        *,
        has_active_question: bool,
        has_image: bool,
    ) -> str | None:
        if has_image or not message.strip():
            return None
        normalized = re.sub(r"\s+", " ", message).strip()
        if re.fullmatch(
            r"(?:你好|您好|嗨|hello|hi|在吗|谢谢|感谢|明白了|懂了)[！!。.?？ ]*",
            normalized,
            re.I,
        ):
            return "general_chat"
        if re.search(
            r"你能|可以.*(?:做什么|帮什么)|怎么使用|如何使用|功能|"
            r"聊聊|聊天|心情|最近|你是谁|你觉得",
            normalized,
        ):
            return "general_chat"
        looks_like_problem = bool(
            re.search(
                r"已知|若.+则|求(?:证|解|值|函数|数列|概率|面积|体积)|证明|计算|解方程|"
                r"下列|选择题|填空题|材料题|阅读下文|如图|[=＝]|"
                r"\d\s*[+\-×÷*/^]\s*\d",
                normalized,
            )
        )
        asks_for_explanation = bool(
            re.search(
                r"什么是|是什么意思|为什么|怎么理解|如何理解|请解释|能否解释|"
                r"区别|关系|概念|定义|原理|作用|适用条件",
                normalized,
            )
        )
        if asks_for_explanation and not looks_like_problem:
            return "knowledge_question"
        if has_active_question and re.search(
            r"为什么|怎么|如何|能不能|可以吗|吗[？?]?$", normalized
        ):
            return "knowledge_question"
        if not has_active_question and not looks_like_problem:
            return "general_chat"
        return None

    @staticmethod
    def _infer_subject(text: str) -> Subject:
        markers = (
            (("函数", "导数", "数列", "几何", "概率", "集合"), Subject.MATHEMATICS),
            (("电路", "速度", "加速度", "受力", "电场", "磁场"), Subject.PHYSICS),
            (("反应", "离子", "物质的量", "有机", "化学"), Subject.CHEMISTRY),
            (("基因", "细胞", "遗传", "生态", "生物"), Subject.BIOLOGY),
            (("史料", "朝代", "历史", "革命"), Subject.HISTORY),
            (("气候", "经纬", "地形", "人口", "地理"), Subject.GEOGRAPHY),
            (("材料体现", "哲学", "政治", "经济与社会"), Subject.IDEOLOGY_POLITICS),
            (("阅读", "文言", "诗歌", "作文", "语文"), Subject.CHINESE),
            (("English", "grammar", "cloze", "英语"), Subject.FOREIGN_LANGUAGE),
            (("算法", "流程图", "数据库", "技术"), Subject.TECHNOLOGY),
        )
        for words, subject in markers:
            if any(word.lower() in text.lower() for word in words):
                return subject
        raise InputValidationError("无法可靠识别学科，请手动选择科目")

    @staticmethod
    def _question_type(stem: str, options: list[str]) -> str:
        if options:
            return "multiple_choice"
        if "作文" in stem or "写作" in stem:
            return "writing"
        if "实验" in stem:
            return "experimental_question"
        if any(marker in stem for marker in ("证明", "解答", "计算", "求")):
            return "subjective_calculation"
        return "short_answer"

    @staticmethod
    def _knowledge_id(subject: Subject, topic: str) -> str:
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "_", topic).strip("_")[:80]
        return f"{subject.value}:{normalized or 'pending_mapping'}"

    @staticmethod
    def _fallback_hint(
        question: QuestionContext,
        work: StudentWork,
        level: int,
        *,
        direct: bool = False,
        message: str = "",
        knowledge_matches: list[dict[str, Any]] | None = None,
        image_based: bool = False,
        image_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        stem_excerpt = re.sub(r"\s+", " ", question.stem).strip()[:120]
        work_excerpt = re.sub(r"\s+", " ", work.raw_text).strip()[:120]
        message_excerpt = re.sub(r"\s+", " ", message).strip()[:120]
        if direct:
            acknowledgement = (
                f"我读到了你想直接得到结果的请求，也看到了题目“{stem_excerpt}”。"
                "我不能直接给可抄写的答案，但可以从关键一步带你做。"
            )
        elif image_based:
            acknowledgement = f"我从你上传的图片中识别到：“{stem_excerpt}”。"
        elif work.raw_text:
            acknowledgement = f"我读到了你本轮写的内容：“{work_excerpt}”。"
        else:
            acknowledgement = f"我已经读取题目：“{stem_excerpt}”。"
        feedback = content_feedback(
            question.subject,
            question.stem,
            f"{work.raw_text} {message}",
        )
        references = knowledge_matches or []
        source_note = ""
        if references:
            source_note = f"本地知识库将本题关联到“{references[0]['title']}”。"
        if re.search(r"什么是|是什么意思|概念|定义", message_excerpt):
            guidance = (
                f"{feedback.concept}{source_note}在这道题中要特别检查：{feedback.checkpoint}。"
            )
        elif re.search(r"为什么|原因|作用", message_excerpt):
            guidance = (
                f"{feedback.concept}{source_note}之所以先这样处理，是为了"
                f"{feedback.method.rstrip('。')}。"
            )
        elif work.raw_text:
            guidance = (
                f"这道题关联“{feedback.topic}”。{source_note}{feedback.method}"
                f"针对你刚写的内容，先核对：{feedback.checkpoint}。"
            )
        else:
            guidance = f"这道题关联“{feedback.topic}”。{source_note}{feedback.method}"
        warning_parts = ["本轮只推进一个可检验步骤，不直接展开最终答案。"]
        if image_based and image_warnings:
            warning_parts.append(f"图片识别提示：{'；'.join(image_warnings[:2])}。")
        return {
            "action": "release_hint",
            "student_visible_content": {
                "acknowledgement": acknowledgement,
                "guidance": guidance,
                "question_to_student": feedback.next_prompt,
                "warning": "".join(warning_parts),
            },
            "pedagogical_metadata": {
                "hint_level": level,
                "expected_student_action": "submit_next_independent_step",
                "response_to": message_excerpt,
                "knowledge_source_ids": [str(item.get("source_id")) for item in references[:3]],
            },
            "confidence": 0.84 if references else 0.76,
        }
