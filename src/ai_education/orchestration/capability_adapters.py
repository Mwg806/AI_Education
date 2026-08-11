"""Capability adapters translating supervisor goals into native Agent requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_education.domain.enums import ActorType, AgentRole
from ai_education.domain.multi_agent import (
    AgentTask,
    MissingContext,
    OrchestrationPlan,
    RoutingDecision,
    UnifiedStudentProfile,
)
from ai_education.domain.protocols import AgentRequest, Operator

SUBJECT_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("foreign_language", ("英语", "english", "阅读", "词汇", "语法", "口语")),
    ("mathematics", ("数学", "函数", "导数", "数列", "几何", "概率")),
    ("chinese", ("语文", "作文", "古诗文")),
    ("physics", ("物理", "力学", "电学")),
    ("chemistry", ("化学",)),
    ("biology", ("生物",)),
    ("history", ("历史",)),
    ("geography", ("地理",)),
    ("ideology_politics", ("政治", "思想政治")),
    ("technology", ("技术", "信息技术")),
)


@dataclass(frozen=True, slots=True)
class AdapterContext:
    user_id: str
    message: str
    subject: str
    request_context: dict[str, Any]
    profile: UnifiedStudentProfile
    actor: Operator


def detect_subjects(message: str, fallback: str) -> list[str]:
    text = message.lower()
    found = [
        subject for subject, aliases in SUBJECT_ALIASES if any(item in text for item in aliases)
    ]
    return list(dict.fromkeys(found)) or [fallback]


def _english_text(message: str, context: dict[str, Any]) -> str:
    supplied = str(context.get("source_text") or context.get("text") or "").strip()
    if supplied:
        return supplied
    segments = re.findall(r"[A-Za-z][A-Za-z0-9 ,.;:'!?()\-]{2,}", message)
    return max(segments, key=len).strip() if segments else ""


def _missing(field: str, prompt: str, reason: str, *sources: str) -> MissingContext:
    return MissingContext(
        field=field,
        prompt=prompt,
        reason=reason,
        accepted_sources=list(sources) or ["用户输入"],
    )


class CapabilityAdapter:
    role: AgentRole

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        raise NotImplementedError

    def resolve_payload(
        self,
        task: AgentTask,
        context: AdapterContext,
        dependency_results: dict[str, dict[str, Any]],
        recent_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del context, dependency_results, recent_events
        return dict(task.payload)


class DiagnosisCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.LEARNING_DIAGNOSIS

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        return [
            AgentTask(
                agent=self.role,
                intent="ingest_learning_evidence",
                objective=f"基于可核验记录诊断 {context.subject} 学习状态",
                subject=context.subject,
                depends_on=depends_on,
                execution_group=0,
                payload={"diagnosis_request": context.message},
            )
        ]

    def resolve_payload(self, task, context, dependency_results, recent_events):
        del dependency_results
        selected = [
            item
            for item in recent_events
            if item.get("knowledge_point")
            and (not item.get("subject") or item.get("subject") == task.subject)
            and item.get("event_type") not in {"PLAN_UPDATED", "DIAGNOSIS_UPDATED"}
        ][:50]
        records: list[dict[str, Any]] = []
        error_types = {
            "QUESTION_WRONG",
            "KNOWLEDGE_WEAK",
            "READING_ERROR",
            "GRAMMAR_ERROR",
            "WRITING_ERROR",
            "SPEAKING_ERROR",
        }
        for item in selected:
            metadata = item.get("metadata") or {}
            is_error = item.get("event_type") in error_types
            occurred = item.get("occurred_at")
            records.append(
                {
                    "evidence_id": item["event_id"],
                    "assessment_id": str(
                        item.get("session_id")
                        or f"unified-{str(occurred)[:10]}-{item['event_id'][-6:]}"
                    )[:128],
                    "assessment_type": "homework"
                    if item.get("agent") == "homework_tutor"
                    else "practice",
                    "question_id": str(metadata.get("source_item_id") or item["event_id"])[:128],
                    "knowledge_tags": [str(item["knowledge_point"])[:128]],
                    "question_type": str(
                        metadata.get("question_type")
                        or metadata.get("error_type")
                        or str(item.get("event_type", "practice")).lower()
                    )[:80],
                    "ability_tags": ["reading_comprehension"]
                    if item.get("event_type") == "READING_ERROR"
                    else [],
                    "difficulty": float(item.get("difficulty") or 0.5),
                    "score": float(
                        item["score"] if item.get("score") is not None else 0.0 if is_error else 1.0
                    ),
                    "max_score": 1.0,
                    "error_tags": [str(metadata.get("error_type") or "learning_error")[:80]]
                    if is_error
                    else [],
                    "source_id": item["event_id"],
                    "occurred_at": occurred,
                    "source_reliability": float(item.get("confidence") or 0.7),
                }
            )
        basic = context.profile.basic_profile
        return {
            "student_id": context.user_id,
            "grade": basic.get("grade", "grade_12"),
            "province_code": basic.get("province_code", "43"),
            "subject": task.subject or context.subject,
            "target_exam_year": int(basic.get("target_exam_year", 2027)),
            "diagnosis_request": context.message,
            "diagnosis_window": "unified_recent_events",
            "records": records,
        }


class PlannerCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.PERSONALIZED_LEARNING_PLANNER

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        if "确认" in context.message and context.request_context.get("plan_id"):
            intent = "confirm_plan"
            payload = {
                "plan_id": context.request_context["plan_id"],
                "expected_version": context.request_context.get("expected_version"),
            }
            missing = (
                []
                if payload["expected_version"]
                else [
                    _missing(
                        "expected_version",
                        "请刷新计划后再确认。",
                        "计划确认需要当前版本号",
                        "当前计划",
                    )
                ]
            )
        elif depends_on:
            intent = "apply_diagnosis_to_plan"
            payload = {"student_request": context.message, "subject": context.subject}
            missing = []
        else:
            intent = "get_plan"
            payload = {"scope": "latest"}
            missing = []
        return [
            AgentTask(
                agent=self.role,
                intent=intent,
                objective="读取或依据诊断调整个性化学习计划",
                subject=context.subject,
                payload=payload,
                depends_on=depends_on,
                execution_group=1 if depends_on else 0,
                missing_context=missing,
            )
        ]

    def resolve_payload(self, task, context, dependency_results, recent_events):
        del recent_events
        payload = dict(task.payload)
        if task.intent == "apply_diagnosis_to_plan":
            diagnosis: dict[str, Any] = {}
            for item in dependency_results.values():
                candidate = item.get("result", {})
                if "learning_state" in candidate or "diagnosis_report" in candidate:
                    diagnosis = candidate
                    break
            payload["diagnosis"] = diagnosis
            payload["student_request"] = context.message
        return payload


class EnglishCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.ENGLISH_READING_LANGUAGE

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        text = _english_text(context.message, context.request_context)
        lower = context.message.lower()
        missing: list[MissingContext] = []
        if "语法" in lower:
            intent = "execute_english_language_task"
            payload = {
                "task_type": "grammar_correction",
                "source_text": text,
                "user_message": context.message,
                "response_mode": "guided",
            }
            if not text:
                missing.append(
                    _missing(
                        "source_text",
                        "请发送需要分析或修改的英文句子。",
                        "语法分析不能凭空构造学生原句",
                        "英文文本",
                    )
                )
        elif "词汇" in lower or "单词" in lower:
            intent = "execute_english_language_task"
            payload = {
                "task_type": "vocabulary_explanation",
                "source_text": text,
                "user_message": context.message,
                "response_mode": "teaching",
            }
            if not text:
                missing.append(
                    _missing(
                        "source_text",
                        "请发送包含目标单词的英文句子或短文。",
                        "词汇解释需要真实语境",
                        "英文文本",
                    )
                )
        elif "口语" in lower:
            intent = "execute_english_language_task"
            payload = {
                "task_type": "speaking_practice",
                "source_text": text,
                "user_message": context.message,
                "scenario": context.request_context.get("scenario", "新高考英语口语表达"),
                "response_mode": "immersive",
            }
        elif any(token in lower for token in ("训练", "练习", "阅读题")):
            intent = "create_english_training"
            payload = {
                "title": context.request_context.get("title", "协作中心英语训练"),
                "text": text,
                "mode": context.request_context.get("training_mode", "reading_multiple_choice"),
                "question_count": int(context.request_context.get("question_count", 4)),
            }
            if len(text) < 80:
                missing.append(
                    _missing(
                        "source_text",
                        "请提供至少 80 个字符的英语阅读材料，或前往英语阅读题库选卷。",
                        "生成训练必须基于真实材料",
                        "英文材料",
                        "英语阅读题库",
                    )
                )
        else:
            intent = "execute_english_language_task"
            payload = {
                "task_type": "progress_query",
                "user_message": context.message,
                "source_text": text,
                "response_mode": "teaching",
            }
        return [
            AgentTask(
                agent=self.role,
                intent=intent,
                objective="完成英语阅读与语言学习请求",
                subject="foreign_language",
                payload=payload,
                depends_on=depends_on,
                execution_group=0,
                missing_context=missing,
            )
        ]


class ProgrammingCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.PROGRAMMING_LEARNING

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        lower = context.message.lower()
        missing: list[MissingContext] = []
        if "项目" in lower and any(
            token in lower for token in ("下一步", "怎么做", "继续", "开发")
        ):
            intent = "v1_project_chat"
            session_id = context.request_context.get(
                "project_session_id"
            ) or context.request_context.get("session_id")
            payload = {"message": context.message, "session_id": session_id}
            if not session_id:
                missing.append(
                    _missing(
                        "project_session_id",
                        "请先从项目实训中开始一个项目，或提供项目会话。",
                        "需要读取具体项目方案和当前阶段",
                        "项目实训会话",
                    )
                )
        elif "项目" in lower:
            intent = "v1_list_projects"
            payload = {}
        elif any(token in lower for token in ("代码题", "刷题", "练习题", "换一道")):
            intent = "v1_next_question"
            level = str(context.profile.learning_preferences.get("programming_level", "beginner"))
            difficulty = {"beginner": 1, "basic": 2, "project": 3}.get(level, 1)
            payload = {
                "language": "python",
                "difficulty": difficulty,
                "selection_mode": "recommended",
            }
        else:
            intent = "v1_career_chat"
            payload = {"message": context.message}
        return [
            AgentTask(
                agent=self.role,
                intent=intent,
                objective="提供与学生编程画像一致的岗位或项目指导",
                subject="technology",
                payload=payload,
                depends_on=depends_on,
                execution_group=0,
                missing_context=missing,
            )
        ]


class HomeworkCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.HOMEWORK_TUTOR

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        session_id = context.request_context.get(
            "homework_session_id"
        ) or context.request_context.get("session_id")
        question_text = str(context.request_context.get("question_text") or "").strip()
        if session_id:
            return [
                AgentTask(
                    agent=self.role,
                    intent="homework_turn",
                    objective="在现有作业会话中继续启发式辅导",
                    subject=context.subject,
                    payload={
                        "session_id": session_id,
                        "message": context.message,
                        "question_text": question_text,
                        "subject": context.subject,
                    },
                    depends_on=depends_on,
                    execution_group=0,
                )
            ]
        basic = context.profile.basic_profile
        create = AgentTask(
            agent=self.role,
            intent="create_homework_session",
            objective="建立受考试政策约束的作业辅导会话",
            subject=context.subject,
            payload={
                "student_id": context.user_id,
                "grade": basic.get("grade", "grade_12"),
                "province_code": basic.get("province_code", "43"),
                "target_exam_year": int(basic.get("target_exam_year", 2027)),
                "subject_hint": context.subject,
            },
            depends_on=depends_on,
            execution_group=0,
        )
        if not question_text:
            return [create]
        turn = AgentTask(
            agent=self.role,
            intent="homework_turn",
            objective="围绕学生提供的真实题目开始启发式辅导",
            subject=context.subject,
            payload={
                "message": context.message,
                "question_text": question_text,
                "subject": context.subject,
            },
            depends_on=[create.task_id],
            execution_group=1,
        )
        return [create, turn]

    def resolve_payload(self, task, context, dependency_results, recent_events):
        del context, recent_events
        payload = dict(task.payload)
        if task.intent == "homework_turn" and not payload.get("session_id"):
            for result in dependency_results.values():
                session = result.get("result", {}).get("session", {})
                if session.get("session_id"):
                    payload["session_id"] = session["session_id"]
                    break
        return payload


class TeacherPreparationCapabilityAdapter(CapabilityAdapter):
    role = AgentRole.TEACHER_PREPARATION

    def tasks(self, context: AdapterContext, depends_on: list[str]) -> list[AgentTask]:
        lower = context.message.lower()
        if any(token in lower for token in ("资源", "教案素材", "搜索")) and "生成" not in lower:
            intent = "search_teaching_resources"
            payload = {"query": context.message, "subject": context.subject, "limit": 5}
            missing: list[MissingContext] = []
        elif any(token in lower for token in ("已有教案", "教案列表", "历史教案")):
            intent = "list_lesson_plans"
            payload = {"classroom_id": context.request_context.get("classroom_id")}
            missing = []
        else:
            classroom = context.request_context.get("classroom") or {}
            classroom_id = context.request_context.get("classroom_id") or classroom.get("id")
            topic = str(context.request_context.get("topic") or "").strip()
            payload = {
                "classroom_id": classroom_id,
                "classroom": classroom,
                "diagnosis_summary": context.request_context.get("diagnosis_summary") or {},
                "subject": context.subject,
                "lesson_type": context.request_context.get("lesson_type", "review"),
                "topic": topic,
                "lesson_request": context.message,
                "duration_minutes": int(context.request_context.get("duration_minutes", 45)),
                "teaching_stage": context.request_context.get("teaching_stage", "高考复习"),
                "textbook_version": context.request_context.get("textbook_version", "教师指定教材"),
                "exam_year": int(context.request_context.get("exam_year", 2027)),
                "homework_time_limit_minutes": int(
                    context.request_context.get("homework_time_limit_minutes", 25)
                ),
            }
            missing = []
            if not classroom_id or not classroom:
                missing.append(
                    _missing(
                        "classroom",
                        "请选择已授权班级后再生成教案。",
                        "备课必须使用匿名班级学情并校验教师权限",
                        "教师班级选择",
                    )
                )
            if not topic:
                missing.append(
                    _missing(
                        "topic",
                        "请填写本节课的具体课题，例如“函数单调性复习”。",
                        "检索资源和生成教案需要明确课题",
                        "教师输入",
                    )
                )
            intent = "create_lesson_plan"
        if context.actor.type not in {ActorType.TEACHER, ActorType.ADMIN}:
            missing = [
                _missing(
                    "teacher_authorization",
                    "请使用教师账号进入备课协作。",
                    "学生无权读取班级学情或生成教师教案",
                    "教师登录态",
                )
            ]
        return [
            AgentTask(
                agent=self.role,
                intent=intent,
                objective="基于匿名班级学情和教学资源生成或检索备课内容",
                subject=context.subject,
                payload=payload,
                depends_on=depends_on,
                execution_group=0,
                missing_context=missing,
            )
        ]


class CapabilityAdapterRegistry:
    def __init__(self) -> None:
        adapters = (
            PlannerCapabilityAdapter(),
            HomeworkCapabilityAdapter(),
            DiagnosisCapabilityAdapter(),
            TeacherPreparationCapabilityAdapter(),
            EnglishCapabilityAdapter(),
            ProgrammingCapabilityAdapter(),
        )
        self._adapters = {item.role: item for item in adapters}

    def get(self, role: AgentRole) -> CapabilityAdapter:
        return self._adapters[role]

    @property
    def roles(self) -> set[AgentRole]:
        return set(self._adapters)

    def build_plan(self, routing: RoutingDecision, context: AdapterContext) -> OrchestrationPlan:
        tasks: list[AgentTask] = []
        diagnosis_ids: list[str] = []
        subjects = detect_subjects(context.message, context.subject)
        for role in routing.required_agents:
            dependencies = diagnosis_ids if role == AgentRole.PERSONALIZED_LEARNING_PLANNER else []
            if role == AgentRole.LEARNING_DIAGNOSIS and len(subjects) > 1:
                for subject in subjects:
                    scoped = AdapterContext(
                        user_id=context.user_id,
                        message=context.message,
                        subject=subject,
                        request_context=context.request_context,
                        profile=context.profile,
                        actor=context.actor,
                    )
                    created = self.get(role).tasks(scoped, [])
                    tasks.extend(created)
                    diagnosis_ids.extend(item.task_id for item in created)
            else:
                created = self.get(role).tasks(context, dependencies)
                tasks.extend(created)
                if role == AgentRole.LEARNING_DIAGNOSIS:
                    diagnosis_ids.extend(item.task_id for item in created)
        mode = routing.execution_mode
        if diagnosis_ids and len(diagnosis_ids) > 1 and any(item.depends_on for item in tasks):
            mode = "hybrid"
        elif len({item.execution_group for item in tasks}) > 1:
            mode = "sequential"
        return OrchestrationPlan(
            goal=context.message,
            execution_mode=mode,
            tasks=tasks,
            stop_conditions=[
                "缺失真实题目、会话、计划、项目或班级上下文时停止并追问",
                "必需依赖失败时停止下游任务并明确标注",
                "正式学习计划只有学生确认后才能发布或覆盖",
            ],
        )

    def build_request(
        self,
        task: AgentTask,
        context: AdapterContext,
        dependency_results: dict[str, dict[str, Any]],
        recent_events: list[dict[str, Any]],
        *,
        trace_id: str,
        run_id: str,
        session_id: str,
    ) -> AgentRequest:
        payload = self.get(task.agent).resolve_payload(
            task, context, dependency_results, recent_events
        )
        return AgentRequest(
            trace_id=trace_id,
            student_id=context.user_id,
            actor=context.actor,
            intent=task.intent,
            payload=payload,
            context={
                **context.request_context,
                "session_id": session_id,
                "orchestration_run_id": run_id,
                "orchestration_task_id": task.task_id,
                "dependency_results": dependency_results,
            },
            idempotency_key=f"{run_id}:{task.task_id}",
        )
