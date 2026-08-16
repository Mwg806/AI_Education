"""LangGraph learning-state diagnosis agent with evidence gating and audit."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from ai_education.agents.base import BaseEducationAgent
from ai_education.config import Settings
from ai_education.core.errors import AIEducationError, InputValidationError
from ai_education.diagnosis_repository import DiagnosisRepository
from ai_education.domain.diagnosis import (
    DiagnosisContext,
    DiagnosisNarrativeBundle,
    LearningEvidenceRecord,
    TeacherReview,
)
from ai_education.domain.enums import ActorType, AgentRole, MessageType, StandardStatus, Subject
from ai_education.domain.protocols import (
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ErrorDetail,
    Evidence,
    WarningDetail,
)
from ai_education.llm.diagnosis_reporter import StructuredDiagnosisReporter
from ai_education.llm.factory import create_chat_model
from ai_education.services.learning_diagnosis import LearningDiagnosisService
from ai_education.tools.diagnosis import DiagnosisToolbox


class LearningDiagnosisGraphState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    payload: dict[str, Any]
    next_node: str
    final_result: dict[str, Any]
    response_status: StandardStatus
    lifecycle_status: str
    evidence: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class LearningDiagnosisAgent(BaseEducationAgent):
    def __init__(
        self, repository: DiagnosisRepository, settings: Settings, chat_model: Any | None = None
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.service = LearningDiagnosisService()
        self.reporter = StructuredDiagnosisReporter(
            chat_model if chat_model is not None else create_chat_model(settings)
        )
        self.toolbox = DiagnosisToolbox()
        self.graph = self._build_graph()

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="learning_state_diagnosis_agent",
            role=AgentRole.LEARNING_DIAGNOSIS,
            version="1.0.0",
            description="面向高中多源学习证据的可追溯、增量式学情诊断智能体",
            capabilities=set(self.toolbox.capability_manifest()),
            accepted_intents={
                "initialize_learning_diagnosis", "ingest_learning_evidence",
                "get_learning_state", "get_diagnosis_report", "submit_teacher_review",
            },
        )

    async def ainvoke(self, request: AgentRequest) -> AgentResponse:
        cached = self.repository.get_idempotent(request.idempotency_key)
        if cached:
            return AgentResponse.model_validate(cached)
        initial: LearningDiagnosisGraphState = {
            "request": request.model_dump(mode="json"), "intent": request.intent,
            "payload": request.payload, "warnings": [], "errors": [], "evidence": [],
            "messages": [], "response_status": StandardStatus.SUCCESS,
            "lifecycle_status": "received",
        }
        try:
            final = await self.graph.ainvoke(initial)
            response = self._to_response(request, final)
        except (ValidationError, InputValidationError) as exc:
            details = exc.details if isinstance(exc, InputValidationError) else {
                "fields": [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
            }
            response = self._error_response(request, StandardStatus.NEED_MORE_INFORMATION,
                "waiting_for_data", "DIAGNOSIS_INPUT_INVALID",
                exc.message if isinstance(exc, InputValidationError) else "诊断证据未通过结构校验", details)
        except AIEducationError as exc:
            response = self._error_response(request, StandardStatus.FAILED, "failed", exc.code, exc.message, exc.details)
        except Exception:
            response = self._error_response(request, StandardStatus.FAILED, "failed",
                "UNEXPECTED_DIAGNOSIS_AGENT_ERROR", "学情诊断流程出现未预期错误，未写入未经验证的结论", {})
        self.repository.put_idempotent(request.idempotency_key, response.model_dump(mode="json"))
        return response

    def _build_graph(self):
        graph = StateGraph(LearningDiagnosisGraphState)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("run", self._run)
        graph.add_node("get_state", self._get_state)
        graph.add_node("get_report", self._get_report)
        graph.add_node("review", self._review)
        graph.add_node("unsupported", self._unsupported)
        graph.add_edge(START, "dispatch")
        graph.add_conditional_edges("dispatch", lambda state: state["next_node"], {
            "run": "run", "get_state": "get_state", "get_report": "get_report",
            "review": "review", "unsupported": "unsupported",
        })
        for node in ("run", "get_state", "get_report", "review", "unsupported"):
            graph.add_edge(node, END)
        return graph.compile()

    def _dispatch(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        routes = {
            "initialize_learning_diagnosis": "run", "ingest_learning_evidence": "run",
            "get_learning_state": "get_state", "get_diagnosis_report": "get_report",
            "submit_teacher_review": "review",
        }
        return {"next_node": routes.get(state["intent"], "unsupported")}

    async def _run(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        payload = state["payload"]
        context = DiagnosisContext.model_validate({
            key: payload[key] for key in DiagnosisContext.model_fields if key in payload
        })
        if context.student_id != state["request"]["student_id"]:
            raise InputValidationError("诊断上下文与请求学生身份不一致")
        raw_records = payload.get("records") or []
        if not raw_records:
            raise InputValidationError("至少需要 1 条真实作答或评价证据")
        records = []
        for item in raw_records:
            clean = {**item, "subject": context.subject.value}
            if clean.get("occurred_at") is None:
                clean.pop("occurred_at", None)
            records.append(LearningEvidenceRecord.model_validate(clean))
        normalized = self.service.normalize(records)
        inserted, duplicates = self.repository.upsert_evidence(context.student_id, context.subject.value, normalized)
        all_records = self.repository.list_evidence(context.student_id, context.subject.value)
        previous = self.repository.latest_state(context.student_id, context.subject.value)
        diagnosis = self.service.infer(
            student_id=context.student_id, subject=context.subject.value,
            target_exam_year=context.target_exam_year, records=all_records,
            previous=previous, rejected=duplicates,
        )
        warnings: list[WarningDetail] = []
        narrative = None
        report_context = self._report_context(payload, context, diagnosis)
        for _ in range(2):
            try:
                candidate = await self.reporter.generate(report_context)
                if candidate and self._student_narrative_is_safe(candidate.student_summary):
                    narrative = candidate
                    break
            except Exception:
                continue
        if narrative is None:
            warnings.append(WarningDetail(
                code="DIAGNOSIS_REPORT_MODEL_FAILED",
                message="结构化状态已生成，但大模型报告未通过中文表达与详细度校验；未使用固定模板冒充模型回答",
            ))
        if narrative:
            diagnosis = diagnosis.model_copy(update={"narrative": DiagnosisNarrativeBundle(
                **narrative.model_dump(), generation_mode="llm")})
        else:
            warnings.append(WarningDetail(
                code="DIAGNOSIS_REPORT_UNAVAILABLE",
                message="当前仅返回可审计结构化状态，未生成模型叙述",
            ))
        saved = self.repository.save_state(diagnosis)
        protocol_evidence = [Evidence(
            source_type=item.assessment_type,
            source_id=item.source_id or item.evidence_id,
            description=f"{item.knowledge_tags[0]} / {item.question_type} 的可核验作答记录",
            confidence=item.evidence_weight,
            observed_at=item.occurred_at,
            metadata={"evidence_id": item.evidence_id, "assessment_id": item.assessment_id},
        ) for item in all_records]
        event = {
            "event_type": "learning_state.updated",
            "diagnosis_id": saved.diagnosis_id,
            "state_version": saved.state_version,
            "subject": saved.subject.value,
            "diagnosis_status": saved.diagnosis_status,
            "weak_dimensions": [item.dimension_id for item in saved.knowledge_states if item.mastery_level in {"needs_support", "developing"}],
            "evidence_sufficiency": saved.evidence_gate.sufficiency_level,
        }
        message = AgentMessage(
            trace_id=state["request"]["trace_id"], message_type=MessageType.EVENT,
            sender=AgentRole.LEARNING_DIAGNOSIS,
            recipient=AgentRole.PERSONALIZED_LEARNING_PLANNER,
            student_id=context.student_id, payload=event,
            evidence=protocol_evidence[:20],
        )
        status = StandardStatus.SUCCESS
        if saved.diagnosis_status in {"insufficient_evidence", "preliminary"} or not narrative:
            status = StandardStatus.PARTIAL_SUCCESS
        if saved.diagnosis_status == "review_required":
            status = StandardStatus.MANUAL_REVIEW_REQUIRED
        return {
            "final_result": {
                "learning_state": saved.model_dump(mode="json"),
                "diagnosis_report": saved.narrative.model_dump(mode="json"),
                "evidence_summary": {
                    "received_now": len(records), "inserted_now": len(inserted),
                    "duplicates_ignored": duplicates, "total": len(all_records),
                },
                "diagnosis_event": event,
            },
            "response_status": status,
            "lifecycle_status": saved.diagnosis_status,
            "warnings": [item.model_dump(mode="json") for item in warnings],
            "evidence": [item.model_dump(mode="json") for item in protocol_evidence],
            "messages": [message.model_dump(mode="json")],
        }

    @staticmethod
    def _report_context(
        payload: dict[str, Any],
        context: DiagnosisContext,
        diagnosis: Any,
    ) -> dict[str, Any]:
        """Give the reporter Chinese, student-facing facts instead of raw schema fields."""
        level_labels = {
            "insufficient_evidence": "证据不足，暂不判断稳定掌握程度",
            "needs_support": "需要重点支持",
            "developing": "正在发展",
            "proficient": "掌握较熟练",
            "strong": "表现较强",
        }
        trend_labels = {
            "improving": "近期有提升",
            "stable": "近期相对稳定",
            "declining": "近期表现下降，需复测确认",
            "unknown": "暂无足够历史证据比较",
        }

        def dimension_rows(items: list[Any]) -> list[dict[str, Any]]:
            return [
                {
                    "名称": item.dimension_label,
                    "当前估计得分水平": f"{item.mastery_probability:.0%}",
                    "判断": level_labels.get(item.mastery_level, "需要继续观察"),
                    "可信程度": f"{item.confidence:.0%}",
                    "有效记录数": item.valid_evidence_count,
                    "独立测次数": item.independent_assessment_count,
                    "变化": trend_labels.get(item.trend, "暂无足够历史证据比较"),
                }
                for item in items
            ]

        exam_record = dict(payload.get("exam_learning_record") or {})
        student_analysis = dict(exam_record.get("student_analysis") or {})
        paper_facts = {
            "试卷标题": exam_record.get("paper_title"),
            "本卷得分率": (
                f"{float(exam_record.get('score_accuracy') or 0):.0%}"
                if exam_record
                else None
            ),
            "选择题准确率": (
                f"{float(exam_record.get('objective_accuracy') or 0):.0%}"
                if exam_record
                else None
            ),
            "整卷有效用时（秒）": exam_record.get("total_duration_seconds"),
            "成绩是否仍待复核": bool(exam_record.get("is_provisional")),
            "本卷水平概述": student_analysis.get("level_summary"),
            "本卷薄弱知识": student_analysis.get("weak_knowledge") or [],
            "本卷优势知识": student_analysis.get("strong_knowledge") or [],
            "本卷作答行为观察": student_analysis.get("answering_behavior") or [],
            "建议的复盘动作": student_analysis.get("next_actions") or [],
            "本卷结论边界": student_analysis.get("evidence_boundary"),
        }
        return {
            "诊断请求": context.diagnosis_request,
            "本卷学习记录": paper_facts,
            "跨测次证据允许得出的结论": diagnosis.evidence_gate.allowed_conclusion,
            "有效证据概况": {
                "有效作答记录": diagnosis.evidence_gate.valid_evidence_count,
                "独立测次": diagnosis.evidence_gate.independent_assessment_count,
                "覆盖题型": diagnosis.evidence_gate.question_type_count,
                "仍缺少的证据": list(diagnosis.evidence_gate.missing_evidence),
            },
            "已观察事实": list(diagnosis.observed_facts),
            "知识点状态": dimension_rows(diagnosis.knowledge_states),
            "题型状态": dimension_rows(diagnosis.question_type_states),
            "跨测次重复失分模式": [
                {
                    "名称": item.label,
                    "说明": item.description,
                    "出现次数": item.occurrence_count,
                    "涉及知识点": list(item.knowledge_tags),
                    "可信程度": f"{item.confidence:.0%}",
                }
                for item in diagnosis.stable_error_patterns
            ],
            "需要验证的可能原因": [
                {
                    "可能原因": item.hypothesis,
                    "可信程度": f"{item.confidence:.0%}",
                    "验证方式": item.verification_needed,
                }
                for item in diagnosis.cause_hypotheses
            ],
        }

    @staticmethod
    def _student_narrative_is_safe(summary: str) -> bool:
        lowered = summary.lower()
        forbidden = (
            "evidence_id",
            "assessment_id",
            "dimension_id",
            "insufficient_evidence",
            "needs_support",
            "proficient",
            "generation_mode",
        )
        return not any(token in lowered for token in forbidden)

    def _get_state(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        student_id = state["request"]["student_id"]
        subject = Subject(state["payload"].get("subject", "mathematics"))
        diagnosis = self.repository.latest_state(student_id, subject.value)
        if not diagnosis:
            raise InputValidationError("该学生尚无学情诊断状态")
        return {"final_result": {"learning_state": diagnosis.model_dump(mode="json")}, "lifecycle_status": diagnosis.diagnosis_status}

    def _get_report(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        diagnosis = self.repository.get_diagnosis(str(state["payload"].get("diagnosis_id", "")), student_id=state["request"]["student_id"])
        return {"final_result": {"learning_state": diagnosis.model_dump(mode="json"), "diagnosis_report": diagnosis.narrative.model_dump(mode="json")}, "lifecycle_status": diagnosis.diagnosis_status}

    def _review(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        actor = ActorType(state["request"]["actor"]["type"])
        if actor not in {ActorType.TEACHER, ActorType.ADMIN}:
            raise InputValidationError("只有教师或管理员可以提交诊断复核")
        review = TeacherReview.model_validate(state["payload"])
        saved = self.repository.save_review(review)
        diagnosis = self.repository.get_diagnosis(review.diagnosis_id, student_id=review.student_id)
        return {"final_result": {"review": saved.model_dump(mode="json"), "learning_state": diagnosis.model_dump(mode="json")}, "lifecycle_status": "teacher_review_recorded"}

    def _unsupported(self, state: LearningDiagnosisGraphState) -> dict[str, Any]:
        return {"response_status": StandardStatus.FAILED, "lifecycle_status": "failed", "errors": [ErrorDetail(
            code="UNSUPPORTED_DIAGNOSIS_INTENT", message=f"学情诊断 Agent 不支持意图：{state['intent']}"
        ).model_dump(mode="json")], "final_result": {}}

    @staticmethod
    def _to_response(request: AgentRequest, state: LearningDiagnosisGraphState) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id, trace_id=request.trace_id,
            agent_role=AgentRole.LEARNING_DIAGNOSIS,
            status=state.get("response_status", StandardStatus.SUCCESS),
            lifecycle_status=state.get("lifecycle_status", "completed"),
            result=state.get("final_result", {}), messages=state.get("messages", []),
            evidence=state.get("evidence", []), warnings=state.get("warnings", []),
            errors=state.get("errors", []), data_version=request.data_version,
        )

    @staticmethod
    def _error_response(request: AgentRequest, status: StandardStatus, lifecycle: str,
        code: str, message: str, details: dict[str, Any]) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id, trace_id=request.trace_id,
            agent_role=AgentRole.LEARNING_DIAGNOSIS, status=status,
            lifecycle_status=lifecycle, errors=[ErrorDetail(
                code=code, message=str(message), details=details,
            )], data_version=request.data_version,
        )
