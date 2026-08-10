"""Four-mode Career / Project / Coding / Gaokao workflow for Agent 6."""

from __future__ import annotations

import json
import random
import re
from typing import Any
from uuid import uuid4

from ai_education.career_education_repository import CareerEducationRepository
from ai_education.config import PROJECT_ROOT
from ai_education.core.errors import InputValidationError
from ai_education.domain.career_education import (
    CareerChatInput,
    CareerCodingNextInput,
    CareerCodingSubmissionInput,
    CareerEducationOnboardingInput,
    CareerProjectAnswerInput,
    CareerProjectChatInput,
    CareerProjectStartInput,
    GaokaoProgrammingNextInput,
    GaokaoProgrammingSubmissionInput,
)
from ai_education.llm.career_education import (
    StructuredCareerMentorGenerator,
    StructuredGaokaoProgrammingGrader,
    StructuredProjectMentorGenerator,
)
from ai_education.services.career_mentor import generate_contextual_career_reply
from ai_education.services.programming_career import CareerProgrammingLearningService
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService
from ai_education.services.programming_learning import _now

CATALOG_PATH = PROJECT_ROOT / "Knowledge" / "Agent_6" / "career_education_v1_catalog.json"
GAOKAO_TECHNOLOGY_ROOT = (
    PROJECT_ROOT / "Knowledge" / "Exam" / "高考真题" / "diagnose" / "technology"
)
GAOKAO_TECHNOLOGY_ANSWERS_ROOT = GAOKAO_TECHNOLOGY_ROOT.parent / "answers" / "technology"
GAOKAO_PROGRAMMING_PATTERN = re.compile(
    r"Python|VB程序|程序段|程序如下|算法|流程图|数组|列表|代码|循环|变量"
)

RUBRIC = [
    ("requirement_understanding", "需求理解", 0.15),
    ("solution_completeness", "方案完整性", 0.20),
    ("technology_selection", "技术选型合理性", 0.15),
    ("system_design", "系统设计能力", 0.15),
    ("problem_analysis", "问题分析能力", 0.15),
    ("engineering_feasibility", "工程可实施性", 0.10),
    ("risk_awareness", "风险意识", 0.05),
    ("clarity", "表达与结构", 0.05),
]


class CareerEducationV1Service(CareerProgrammingLearningService):
    def __init__(
        self,
        repository: CareerEducationRepository,
        knowledge: ProgrammingKnowledgeService,
        career_mentor: StructuredCareerMentorGenerator | None = None,
        project_mentor: StructuredProjectMentorGenerator | None = None,
        gaokao_grader: StructuredGaokaoProgrammingGrader | None = None,
    ) -> None:
        super().__init__(repository, knowledge)
        self.repository = repository
        self.career_mentor = career_mentor or StructuredCareerMentorGenerator(None)
        self.project_mentor = project_mentor or StructuredProjectMentorGenerator(None)
        self.gaokao_grader = gaokao_grader or StructuredGaokaoProgrammingGrader(None)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.gaokao_programming_questions = self._load_gaokao_programming_bank()
        self.repository.sync_catalog(self.catalog)

    def dashboard(self, student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        configured = bool(profile and profile.get("career_spec_version") == "1.0")
        if not configured:
            profile = self._default_profile_v1(student_id, auth_profile)
        projects = self.repository.list_records(
            student_id, record_type="v1_project_session", limit=30
        )
        submissions = self.repository.list_records(
            student_id, record_type="v1_coding_submission", limit=100
        )
        skill_states = self._career_skill_states(student_id)
        solved = [item for item in submissions if item["status"] in {"solved", "solved_with_hint"}]
        independent = [
            item
            for item in solved
            if item["payload"].get("attempt_number") == 1 and item["payload"].get("hint_level") == 0
        ]
        evaluated = [item for item in projects if item["status"] == "evaluated"]
        return {
            "spec_version": "1.0",
            "configured": configured,
            "profile": profile,
            "jobs": self.repository.list_jobs(),
            "current_mode": profile.get("current_mode", "CAREER"),
            "summary": {
                "readiness": self._career_readiness(skill_states),
                "project_count": len(evaluated),
                "project_average": round(
                    sum(float(item["payload"]["evaluation"]["total_score"]) for item in evaluated)
                    / max(1, len(evaluated)),
                    1,
                ),
                "coding_solved": len(solved),
                "coding_attempts": len(submissions),
                "independent_pass_rate": round(len(independent) / max(1, len(solved)), 3),
            },
            "skill_profile": skill_states,
            "learning_plan": self._learning_plan(profile, skill_states, projects, submissions),
            "recent_activity": [
                {
                    "type": item["record_type"],
                    "status": item["status"],
                    "title": item["payload"].get("title")
                    or item["payload"].get("question_title")
                    or "学习记录",
                    "updated_at": item["updated_at"],
                }
                for item in sorted(
                    [*projects[:4], *submissions[:6]],
                    key=lambda value: value["updated_at"],
                    reverse=True,
                )[:6]
            ],
            "content_version": self.catalog["content_version"],
        }

    def onboarding(
        self,
        student_id: str,
        body: CareerEducationOnboardingInput,
        auth_profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not any(item["job_id"] == body.target_job_id for item in self.repository.list_jobs()):
            raise InputValidationError("目标岗位不在平台开放列表中")
        previous = self.repository.load_profile(student_id) or {}
        profile = {
            "student_id": student_id,
            "student_name": auth_profile.get("studentName", "同学"),
            "career_spec_version": "1.0",
            **body.model_dump(mode="json"),
            "current_mode": "CAREER",
            "learning_mode": "beginner" if body.programming_level != "project" else "advanced",
            "target_direction": "software_engineering",
            "effective_weekly_minutes": body.weekly_hours * 60,
            "exam_period": False,
            "profile_version": int(previous.get("profile_version", 0)) + 1,
            "updated_at": _now(),
        }
        self.repository.save_profile(profile)
        return {**profile, "configured": True}

    def switch_mode(self, student_id: str, mode: str) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        profile.update(current_mode=mode, updated_at=_now())
        self.repository.save_profile(profile)
        return {"current_mode": mode, "saved": True}

    async def career_chat(self, student_id: str, body: CareerChatInput) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        skills = self._career_skill_states(student_id)
        job = self._job(profile["target_job_id"])
        generated, history_count = await generate_contextual_career_reply(
            generator=self.career_mentor,
            repository=self.repository,
            student_id=student_id,
            job=job,
            profile=profile,
            skills=skills,
            user_message=body.message,
        )
        if generated is None:
            return self._rule_career_chat(student_id, body)
        result = {
            "message_id": f"career_message_{uuid4().hex}",
            "mode": "CAREER",
            "target_job": job,
            **generated.model_dump(mode="json"),
            "generation_mode": "llm",
            "context_used": {
                "target_job_id": profile["target_job_id"],
                "weekly_hours": profile["weekly_hours"],
                "recent_evidence_count": sum(item["evidence_count"] for item in skills),
                "conversation_turns": history_count,
            },
        }
        self._save_simple_record(
            student_id,
            result["message_id"],
            "v1_career_dialogue",
            {**result, "user_message": body.message, "title": body.message[:60]},
            status="completed",
        )
        return result

    def _rule_career_chat(self, student_id: str, body: CareerChatInput) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        skills = self._career_skill_states(student_id)
        weak = sorted(skills, key=lambda item: item["mastery"])[:3]
        message = body.message.lower()
        topic = next(
            (
                item
                for item in skills
                if item["name"].lower() in message
                or item["skill_id"].lower().replace("_", "") in message.replace(" ", "")
            ),
            weak[0],
        )
        if "mysql" in message or "数据库" in message or "sql" in message:
            topic = next(item for item in skills if item["skill_id"] == "MYSQL_SQL")
        elif "fastapi" in message or "接口" in message:
            topic = next(item for item in skills if item["skill_id"] == "FASTAPI_ROUTE")
        elif "http" in message or "rest" in message:
            topic = next(item for item in skills if item["skill_id"] == "HTTP_REST")
        hours = int(profile["weekly_hours"])
        tasks = [
            {
                "task": f"理解 {topic['name']} 的核心概念与岗位使用场景",
                "estimated_minutes": min(120, hours * 12),
                "acceptance": f"能用自己的话解释 {topic['name']} 并举一个后端例子",
            },
            {
                "task": f"完成 2 道与 {topic['name']} 相关的代码或方案练习",
                "estimated_minutes": min(150, hours * 15),
                "acceptance": "至少一次不查看完整解析独立通过",
            },
            {
                "task": "复盘错误并记录一个可复用检查清单",
                "estimated_minutes": 30,
                "acceptance": "检查清单包含正常、边界和异常路径",
            },
        ]
        result = {
            "message_id": f"career_message_{uuid4().hex}",
            "mode": "CAREER",
            "target_job": self._job(profile["target_job_id"]),
            "analysis": (
                f"你当前目标是 Python 后端，{topic['name']} 掌握度约为"
                f" {round(topic['mastery'] * 100)}%，证据数 {topic['evidence_count']}。"
                "因此先安排可验收的小任务，而不是一次铺开整条技术栈。"
            ),
            "answer": self._career_explanation(topic["skill_id"]),
            "task_breakdown": tasks,
            "two_week_route": [
                {
                    "week": 1,
                    "focus": topic["name"],
                    "tasks": [tasks[0], tasks[1]],
                    "estimated_hours": min(hours, 8),
                },
                {
                    "week": 2,
                    "focus": "应用与验证",
                    "tasks": [tasks[2]],
                    "estimated_hours": min(hours, 8),
                },
            ],
            "recommended_mode": "CODING" if topic["skill_id"] != "DOCKER_DEPLOY" else "PROJECT",
            "follow_up_question": "你更想先理解概念，还是直接通过一道练习来掌握它？",
            "generation_mode": "rule_fallback",
            "context_used": {
                "target_job_id": profile["target_job_id"],
                "weekly_hours": profile["weekly_hours"],
                "recent_evidence_count": sum(item["evidence_count"] for item in skills),
                "conversation_turns": len(
                    self.repository.list_records(
                        student_id, record_type="v1_career_dialogue", limit=8
                    )
                ),
            },
        }
        self._save_simple_record(
            student_id,
            result["message_id"],
            "v1_career_dialogue",
            {**result, "user_message": body.message, "title": topic["name"]},
            status="completed",
        )
        return result

    def list_project_bank(self, student_id: str) -> list[dict[str, Any]]:
        profile = self._require_profile(student_id)
        return [
            self._public_project(item)
            for item in self.repository.list_projects(profile["target_job_id"])
        ]

    def start_project(self, student_id: str, body: CareerProjectStartInput) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        projects = self.repository.list_projects(profile["target_job_id"])
        if not projects:
            raise InputValidationError("当前岗位暂无已发布项目模板")
        if body.project_id:
            project = next(
                (item for item in projects if item["project_id"] == body.project_id), None
            )
            if project is None:
                raise InputValidationError("项目不存在或不属于当前岗位")
        else:
            completed = {
                item["payload"].get("project_id")
                for item in self.repository.list_records(
                    student_id, record_type="v1_project_session", limit=50
                )
                if item["status"] == "evaluated"
            }
            candidates = [
                item for item in projects if item["project_id"] not in completed
            ] or projects
            project = random.choice(candidates) if body.randomize else candidates[0]
        session_id = f"project_session_{uuid4().hex}"
        requirement_doc = self._requirement_document(project)
        problem_doc = self._problem_document(project)
        payload = {
            "session_id": session_id,
            "project_id": project["project_id"],
            "title": project["title"],
            "difficulty": project["difficulty"],
            "target_job_id": profile["target_job_id"],
            "project": project,
            "requirement_doc": requirement_doc,
            "problem_doc": problem_doc,
            "answer": None,
            "evaluation": None,
            "created_at": _now(),
        }
        self._save_simple_record(
            student_id, session_id, "v1_project_session", payload, status="waiting_submission"
        )
        return self._public_project_session(payload, "waiting_submission")

    async def project_chat(self, student_id: str, body: CareerProjectChatInput) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        session_payload: dict[str, Any] | None = None
        if body.session_id:
            record = self.repository.load_record(
                body.session_id,
                student_id=student_id,
                record_type="v1_project_session",
            )
            session_payload = record["payload"]

        dialogue_records = self.repository.list_records(
            student_id, record_type="v1_project_dialogue", limit=30
        )
        dialogue_records = [
            item
            for item in dialogue_records
            if item["payload"].get("session_id") == body.session_id
        ][:8]
        history = [
            {
                "student": item["payload"].get("user_message", ""),
                "mentor": item["payload"].get("answer", ""),
            }
            for item in reversed(dialogue_records)
        ]
        if session_payload:
            project = session_payload["project"]
            project_context = {
                "project_id": project["project_id"],
                "title": project["title"],
                "background": project["background"],
                "business_goal": project["business_goal"],
                "requirements": project["requirements"],
                "non_functional_requirements": project["non_functional_requirements"],
                "problems_to_consider": project.get("problems", []),
                "requirement_document": session_payload["requirement_doc"],
                "problem_document": session_payload["problem_doc"],
                "current_answer": session_payload.get("answer"),
            }
        else:
            project_context = {
                "available_projects": [
                    self._public_project(item)
                    for item in self.repository.list_projects(profile["target_job_id"])
                ]
            }

        generated = None
        if self.project_mentor.available:
            try:
                generated = await self.project_mentor.generate(
                    {
                        "learner_profile": {
                            "identity": profile["identity"],
                            "education_stage": profile["education_stage"],
                            "programming_level": profile["programming_level"],
                            "known_languages": profile["known_languages"],
                            "weekly_hours": profile["weekly_hours"],
                            "learning_goal": profile["learning_goal"],
                        },
                        "project_context": project_context,
                        "conversation_history": history,
                        "user_message": body.message,
                    }
                )
            except Exception:
                generated = None

        if generated is not None:
            reply = generated.model_dump(mode="json")
            generation_mode = "llm"
        else:
            title = session_payload["title"] if session_payload else "Python 后端实训"
            requirements = (
                session_payload["project"].get("requirements", []) if session_payload else []
            )
            requirement_text = "、".join(requirements[:3]) or "需求理解、接口设计与数据建模"
            level_guidance = {
                "beginner": (
                    "你现在按入门路线推进：先做一个能运行的最小版本，每完成一步就验证输入和输出。"
                ),
                "basic": (
                    "你已经有语法基础，可以把任务拆成路由、服务和数据访问三层，并同步补接口测试。"
                ),
                "project": (
                    "你已有项目经验，本次应重点说明架构取舍、异常路径、性能边界和部署验证。"
                ),
            }[profile["programming_level"]]
            school_guidance = (
                "作为高中生，先用短迭代完成核心业务，不要求一次铺开复杂工程工具。"
                if profile["identity"] == "high_school_student"
                else ""
            )
            reply = {
                "answer": (
                    f"我们可以围绕“{title}”一步一步推进。先不要急着写代码，"
                    f"请先把核心交付物拆清楚：{requirement_text}。"
                    f"{level_guidance}{school_guidance}"
                    "接着画出一条主业务流程，再据此确定数据表和 API；你把初步想法发给我，"
                    "我会继续帮你检查遗漏和技术取舍。"
                ),
                "guiding_questions": [
                    "这个项目最核心的用户和业务动作分别是什么？",
                    "一次完整业务流程会读写哪些关键数据？",
                    "你准备先实现哪个最小可验收版本？",
                ],
                "suggested_actions": [
                    "用 3—5 句话复述项目目标",
                    "列出核心实体及其关系",
                    "写出第一版 API 清单",
                ],
                "follow_up_question": "你先说说自己理解的主业务流程是什么？",
            }
            generation_mode = "rule_fallback"

        result = {
            "message_id": f"project_message_{uuid4().hex}",
            "session_id": body.session_id,
            **reply,
            "generation_mode": generation_mode,
            "context_used": {
                "project_loaded": session_payload is not None,
                "conversation_turns": len(history),
            },
        }
        self._save_simple_record(
            student_id,
            result["message_id"],
            "v1_project_dialogue",
            {**result, "user_message": body.message, "title": body.message[:60]},
            status="completed",
        )
        return result

    def get_project_session(self, student_id: str, session_id: str) -> dict[str, Any]:
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_project_session"
        )
        return self._public_project_session(record["payload"], record["status"])

    def submit_project_answer(
        self, student_id: str, session_id: str, body: CareerProjectAnswerInput
    ) -> dict[str, Any]:
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_project_session"
        )
        if record["status"] == "evaluated":
            raise InputValidationError("该项目已经评价，如需修改请开始新的实训")
        answer = body.model_dump(mode="json")
        record["payload"] = {**record["payload"], "answer": answer, "submitted_at": _now()}
        record.update(status="submitted", updated_at=_now())
        self.repository.save_record(record)
        return {"session_id": session_id, "status": "submitted", "sections_received": 6}

    def submit_project_document(
        self, student_id: str, session_id: str, text: str, file_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        sections = self._parse_project_document(text)
        body = CareerProjectAnswerInput.model_validate(sections)
        result = self.submit_project_answer(student_id, session_id, body)
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_project_session"
        )
        record["payload"]["upload"] = file_metadata
        self.repository.save_record(record)
        return {**result, "upload": file_metadata}

    def evaluate_project(self, student_id: str, session_id: str) -> dict[str, Any]:
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_project_session"
        )
        if record["status"] not in {"submitted", "evaluated"}:
            raise InputValidationError("请先提交完整项目回答")
        if record["status"] == "evaluated":
            return record["payload"]["evaluation"]
        project = record["payload"]["project"]
        answer = record["payload"]["answer"]
        dimensions = self._score_project(project, answer)
        total = round(sum(item["score"] * item["weight"] for item in dimensions), 1)
        strengths = [item["strengths"][0] for item in dimensions if item["score"] >= 75]
        weaknesses = [item["weaknesses"][0] for item in dimensions if item["score"] < 75]
        evaluation_id = f"project_evaluation_{uuid4().hex}"
        skill_updates = []
        for skill_id in project["skill_ids"]:
            skill_updates.append(
                self._record_evidence(
                    student_id,
                    skill_id=skill_id,
                    event_type="project",
                    source_id=evaluation_id,
                    score=total / 100,
                    independence=0.8,
                    reasoning=0.85,
                    verification=0.75,
                    hint_level=0,
                    description=f"项目实训评价：{project['title']}",
                )
            )
        evaluation = {
            "evaluation_id": evaluation_id,
            "session_id": session_id,
            "total_score": total,
            "dimensions": dimensions,
            "overall_strengths": strengths or ["已完成所有必答章节"],
            "overall_weaknesses": weaknesses or ["可继续补充容量估算与测试细节"],
            "recommended_skills": [
                self.knowledge.career_skill(item["skill_id"])["name"]
                for item in sorted(skill_updates, key=lambda value: value["mastery"])[:3]
            ],
            "next_learning_actions": [
                "根据逐项建议修改一版项目方案",
                "进入代码练习完成对应 API / 数据库题",
                "用一页文档补充异常路径和测试策略",
            ],
            "skill_updates": skill_updates,
            "evaluated_at": _now(),
        }
        report = self._project_report(record["payload"], evaluation)
        record["payload"] = {
            **record["payload"],
            "evaluation": evaluation,
            "report": report,
        }
        record.update(status="evaluated", updated_at=_now())
        self.repository.save_record(record)
        return evaluation

    def project_document(
        self, student_id: str, session_id: str, document_type: str
    ) -> tuple[str, str]:
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_project_session"
        )
        mapping = {
            "requirement": ("requirement_doc", "requirement.md"),
            "problems": ("problem_doc", "problems.md"),
            "report": ("report", "report.md"),
        }
        if document_type not in mapping:
            raise InputValidationError("不支持的项目文档类型")
        field, filename = mapping[document_type]
        content = record["payload"].get(field)
        if not content:
            raise InputValidationError("该文档尚未生成")
        return content, filename

    def next_gaokao_programming_question(
        self, student_id: str, body: GaokaoProgrammingNextInput
    ) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        if not self.gaokao_programming_questions:
            raise InputValidationError("高考程序题库暂不可用")
        candidates = [
            item
            for item in self.gaokao_programming_questions
            if item["question_id"] != body.exclude_question_id
        ] or self.gaokao_programming_questions
        question = random.choice(candidates)
        session_id = f"gaokao_program_session_{uuid4().hex}"
        payload = {
            "session_id": session_id,
            "question_id": question["question_id"],
            "source_title": question["source"]["source_title"],
            "original_number": question["source"]["original_number"],
            "programming_level": profile["programming_level"],
            "started_at": _now(),
        }
        self._save_simple_record(
            student_id,
            session_id,
            "v1_gaokao_program_session",
            payload,
            status="active",
        )
        return {
            "session_id": session_id,
            "question": self._public_gaokao_question(question),
            "bank": {
                "scope": "高考信息技术程序真题",
                "candidate_count": len(self.gaokao_programming_questions),
                "answers_exposed": False,
            },
        }

    async def submit_gaokao_programming_answer(
        self,
        student_id: str,
        session_id: str,
        body: GaokaoProgrammingSubmissionInput,
    ) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        session = self.repository.load_record(
            session_id,
            student_id=student_id,
            record_type="v1_gaokao_program_session",
        )
        question = next(
            (
                item
                for item in self.gaokao_programming_questions
                if item["question_id"] == session["payload"]["question_id"]
            ),
            None,
        )
        if question is None:
            raise InputValidationError("本次高考程序题已失效，请重新抽题")

        generated = None
        if self.gaokao_grader.available:
            try:
                generated = await self.gaokao_grader.grade(
                    {
                        "question": self._public_gaokao_question(question),
                        "max_score": question["max_score"],
                        "standard_answer": question["_standard_answer"],
                        "official_analysis": question["_official_analysis"],
                        "student_answer": body.answer,
                        "learner_profile": {
                            "identity": profile["identity"],
                            "programming_level": profile["programming_level"],
                            "learning_goal": profile["learning_goal"],
                        },
                    }
                )
            except Exception:
                generated = None

        if generated is not None:
            feedback = generated.model_dump(mode="json")
            feedback["score"] = round(
                max(0, min(float(feedback["score"]), question["max_score"])), 1
            )
            generation_mode = "llm"
        else:
            feedback = self._fallback_gaokao_feedback(question, body.answer)
            generation_mode = "evidence_fallback"

        feedback = self._sanitize_gaokao_feedback(question, feedback)

        if question["type"] == "multiple_choice":
            is_correct = (
                body.answer.strip().upper() == str(question["_correct_option"]).strip().upper()
            )
            feedback["score"] = question["max_score"] if is_correct else 0
            if is_correct:
                feedback["diagnosis"] = (
                    "本题得分。你能够结合程序执行过程作出判断；建议继续说明关键变量"
                    "如何变化，确认不是凭直觉选择。"
                )
            else:
                feedback["diagnosis"] = (
                    "本题暂未得分。当前主要问题是程序执行过程或边界条件跟踪不够稳定，"
                    "请按提示重新手工推演，不直接查看答案。"
                )

        submission_id = f"gaokao_program_submission_{uuid4().hex}"
        result = {
            "submission_id": submission_id,
            "session_id": session_id,
            "question_id": question["question_id"],
            "score": feedback["score"],
            "max_score": question["max_score"],
            "score_percent": round(float(feedback["score"]) / max(1, question["max_score"]) * 100),
            "diagnosis": feedback["diagnosis"],
            "strengths": feedback["strengths"],
            "issues": feedback["issues"],
            "hints": feedback["hints"],
            "next_step": feedback["next_step"],
            "generation_mode": generation_mode,
            "answer_revealed": False,
            "practice_redirect": {
                "mode": "CODING",
                "label": "想刷非高考代码题，可前往代码练习",
            },
        }
        self._save_simple_record(
            student_id,
            submission_id,
            "v1_gaokao_program_submission",
            {
                **result,
                "student_answer": body.answer,
                "response_time_seconds": body.response_time_seconds,
                "source_title": question["source"]["source_title"],
            },
            status="scored",
        )
        return result

    def list_coding_questions(
        self, student_id: str, difficulty: int | None = None
    ) -> list[dict[str, Any]]:
        profile = self._require_profile(student_id)
        solved_ids = {
            item["payload"].get("question_id")
            for item in self.repository.list_records(
                student_id, record_type="v1_coding_submission", limit=200
            )
            if item["status"] in {"solved", "solved_with_hint"}
        }
        questions = self.repository.list_questions(profile["target_job_id"])
        if difficulty:
            questions = [item for item in questions if item["difficulty"] == difficulty]
        return [
            self._public_question(item)
            | {
                "difficulty_label": self._difficulty_label(item["difficulty"]),
                "completed": item["question_id"] in solved_ids,
            }
            for item in questions
        ]

    def next_coding_question(self, student_id: str, body: CareerCodingNextInput) -> dict[str, Any]:
        profile = self._require_profile(student_id)
        questions = self.repository.list_questions(profile["target_job_id"])
        language_questions = [
            item
            for item in questions
            if str(item.get("language", "python")).lower() == body.language
        ]
        if not language_questions:
            raise InputValidationError("当前编程语言暂无可用题目")
        completed = {
            item["payload"].get("question_id")
            for item in self.repository.list_records(
                student_id, record_type="v1_coding_submission", limit=200
            )
            if item["status"] in {"solved", "solved_with_hint", "viewed_solution"}
        }
        if body.question_id:
            selected = next(
                (item for item in language_questions if item["question_id"] == body.question_id),
                None,
            )
            if selected is None:
                raise InputValidationError("所选代码题不存在或已下架")
            candidates = [selected]
        else:
            candidates = [
                item for item in language_questions if item["question_id"] not in completed
            ] or language_questions
        if body.category:
            filtered = [item for item in candidates if item["category"] == body.category]
            if filtered:
                candidates = filtered
        if body.exclude_question_id:
            rotated = [
                item for item in candidates if item["question_id"] != body.exclude_question_id
            ]
            if not rotated:
                rotated = [
                    item
                    for item in language_questions
                    if item["question_id"] != body.exclude_question_id
                    and item["question_id"] not in completed
                ] or [
                    item
                    for item in language_questions
                    if item["question_id"] != body.exclude_question_id
                ]
            if rotated:
                candidates = rotated
        recommended_difficulty = {
            "beginner": 1,
            "basic": 2,
            "project": 3,
        }.get(profile.get("programming_level", "basic"), 2)
        target_difficulty = body.difficulty
        if body.selection_mode in {"recommended", "random"} and target_difficulty is None:
            target_difficulty = recommended_difficulty
        if target_difficulty and not body.question_id:
            same_level = [item for item in candidates if item["difficulty"] == target_difficulty]
            if same_level:
                candidates = same_level
            else:
                candidates.sort(key=lambda item: abs(item["difficulty"] - target_difficulty))
                nearest = abs(candidates[0]["difficulty"] - target_difficulty)
                candidates = [
                    item
                    for item in candidates
                    if abs(item["difficulty"] - target_difficulty) == nearest
                ]
        question = (
            random.choice(candidates)
            if body.selection_mode in {"random", "recommended"}
            else candidates[0]
        )
        session_id = f"coding_session_{uuid4().hex}"
        payload = {
            "session_id": session_id,
            "question_id": question["question_id"],
            "question_title": question["title"],
            "target_job_id": profile["target_job_id"],
            "started_at": _now(),
        }
        self._save_simple_record(
            student_id, session_id, "v1_coding_session", payload, status="active"
        )
        return {
            "session_id": session_id,
            "question": self._public_question(question)
            | {"difficulty_label": self._difficulty_label(question["difficulty"])},
            "selection": {
                "mode": body.selection_mode,
                "recommended_difficulty": recommended_difficulty,
                "recommended_difficulty_label": self._difficulty_label(recommended_difficulty),
            },
        }

    def submit_coding(
        self,
        student_id: str,
        session_id: str,
        body: CareerCodingSubmissionInput,
    ) -> dict[str, Any]:
        session = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_coding_session"
        )
        profile = self._require_profile(student_id)
        question = self.repository.get_question(
            session["payload"]["question_id"], profile["target_job_id"]
        )
        if question is None:
            raise InputValidationError("代码题不存在或已下架")
        history = [
            item
            for item in self.repository.list_records(
                student_id, record_type="v1_coding_submission", limit=200
            )
            if item["payload"].get("session_id") == session_id
        ]
        attempt = len(history) + 1
        execution = self.code_runner.run(body.code, question["hidden_tests"])
        passed = execution["execution_status"] == "passed"
        hint_level = 0 if body.action == "run" or passed else min(4, attempt)
        status = (
            "run_only"
            if body.action == "run"
            else "solved"
            if passed and hint_level == 0
            else "solved_with_hint"
            if passed
            else "attempted"
        )
        feedback = {
            "judge_status": "ACCEPTED" if passed else self._judge_status(execution),
            "error_type": execution["error_type"],
            "related_skills": question["skill_ids"],
            "current_hint_level": hint_level,
            "analysis": execution["message"],
            "hint": question["hints"][hint_level - 1] if hint_level else None,
            "allow_solution": False,
            "recommended_next_action": "推荐下一题" if passed else "修改后再次提交",
        }
        submission_id = f"coding_submission_{uuid4().hex}"
        skill_updates = []
        if body.action == "submit":
            score = (
                1.0
                if passed
                else max(
                    0.1,
                    execution["tests_passed"] / max(1, len(question["hidden_tests"])),
                )
            )
            for skill_id in question["skill_ids"]:
                skill_updates.append(
                    self._record_evidence(
                        student_id,
                        skill_id=skill_id,
                        event_type="coding",
                        source_id=submission_id,
                        score=score,
                        independence=max(0.3, 1 - hint_level * 0.15),
                        reasoning=0.75 if passed else 0.45,
                        verification=1.0 if passed else 0.5,
                        hint_level=hint_level,
                        description=f"代码题：{question['title']}（第 {attempt} 次）",
                    )
                )
        result = {
            "submission_id": submission_id,
            "session_id": session_id,
            "question_id": question["question_id"],
            "question_title": question["title"],
            "attempt_number": attempt,
            "action": body.action,
            "status": status,
            "judge_result": {
                "status": feedback["judge_status"],
                "passed": execution["tests_passed"],
                "total": len(question["hidden_tests"]),
                "runtime_ms": execution["runtime_ms"],
                "memory_limit_mb": execution["memory_limit_mb"],
                "runner_mode": execution["runner_mode"],
                "message": execution["message"],
            },
            "feedback": feedback,
            "hint_level": hint_level,
            "skill_updates": skill_updates,
            "created_at": _now(),
        }
        self._save_simple_record(
            student_id, submission_id, "v1_coding_submission", result, status=status
        )
        if passed and body.action == "submit":
            session.update(status=status, updated_at=_now())
            self.repository.save_record(session)
        return result

    def coding_hint(self, student_id: str, session_id: str) -> dict[str, Any]:
        session = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_coding_session"
        )
        profile = self._require_profile(student_id)
        question = self.repository.get_question(
            session["payload"]["question_id"], profile["target_job_id"]
        )
        if question is None:
            raise InputValidationError("代码题不存在")
        hints = self.repository.list_records(student_id, record_type="v1_coding_hint", limit=100)
        submissions = [
            item
            for item in self.repository.list_records(
                student_id, record_type="v1_coding_submission", limit=200
            )
            if item["payload"].get("session_id") == session_id
            and item["payload"].get("action") == "submit"
            and item["payload"].get("status") == "attempted"
        ]
        if not submissions:
            raise InputValidationError("请先提交一次未通过的答案，再查看提示")

        used = [item for item in hints if item["payload"].get("session_id") == session_id]
        level = min(4, len(used) + 1)
        result = {
            "hint_id": f"coding_hint_{uuid4().hex}",
            "session_id": session_id,
            "hint_level": level,
            "hint": question["hints"][level - 1],
            "solution_available": True,
            "solution_exposed": False,
        }
        self._save_simple_record(
            student_id,
            result["hint_id"],
            "v1_coding_hint",
            result,
            status="used",
        )
        return result

    def coding_solution(self, student_id: str, session_id: str) -> dict[str, Any]:
        session = self.repository.load_record(
            session_id, student_id=student_id, record_type="v1_coding_session"
        )
        profile = self._require_profile(student_id)
        question = self.repository.get_question(
            session["payload"]["question_id"], profile["target_job_id"]
        )
        if question is None:
            raise InputValidationError("代码题不存在")
        result = {
            "solution_id": f"coding_solution_{uuid4().hex}",
            "session_id": session_id,
            "reference_solution": question["reference_solution"],
            "solution_explanation": question["solution_explanation"],
            "mastery_notice": "查看答案只记录完成，不作为显著正向能力证据。",
        }
        self._save_simple_record(
            student_id,
            result["solution_id"],
            "v1_coding_solution",
            result,
            status="viewed_solution",
        )
        session.update(status="viewed_solution", updated_at=_now())
        self.repository.save_record(session)
        return result

    def coding_history(self, student_id: str) -> list[dict[str, Any]]:
        self._require_profile(student_id)
        return [
            item["payload"]
            for item in self.repository.list_records(
                student_id, record_type="v1_coding_submission", limit=100
            )
        ]

    def _require_profile(self, student_id: str) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        if not profile or profile.get("career_spec_version") != "1.0":
            raise InputValidationError("请先完成职业教育 Agent 首次画像")
        return profile

    def _job(self, job_id: str) -> dict[str, Any]:
        job = next((item for item in self.repository.list_jobs() if item["job_id"] == job_id), None)
        if job is None:
            raise InputValidationError("岗位不存在或未开放")
        return job

    @staticmethod
    def _public_project(project: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in project.items() if key not in {"problems"}}

    def _public_project_session(self, payload: dict[str, Any], status: str) -> dict[str, Any]:
        public_payload = {
            key: value for key, value in {**payload, "status": status}.items() if key != "project"
        }
        return public_payload | {"project": self._public_project(payload["project"])}

    @staticmethod
    def _public_question(question: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in question.items()
            if key not in {"hidden_tests", "reference_solution", "solution_explanation", "hints"}
        }

    @staticmethod
    def _difficulty_label(difficulty: int) -> str:
        return {1: "简单", 2: "中等", 3: "困难"}.get(difficulty, "中等")

    @classmethod
    def _load_gaokao_programming_bank(cls) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        seen_sources: set[tuple[str, str]] = set()
        for paper_path in sorted(GAOKAO_TECHNOLOGY_ROOT.glob("*.json")):
            answer_path = GAOKAO_TECHNOLOGY_ANSWERS_ROOT / f"{paper_path.stem}.answers.json"
            if not answer_path.exists():
                continue
            paper = json.loads(paper_path.read_text(encoding="utf-8"))
            answers = json.loads(answer_path.read_text(encoding="utf-8"))
            answer_map = {item["question_id"]: item for item in answers.get("answers", [])}
            for item in paper.get("questions", []):
                stem = str(item.get("stem_html", ""))
                if not GAOKAO_PROGRAMMING_PATTERN.search(stem):
                    continue
                source = item.get("source", {})
                source_key = (
                    str(source.get("document_sha256", "")),
                    str(source.get("original_number", "")),
                )
                if source_key in seen_sources or item["question_id"] not in answer_map:
                    continue
                seen_sources.add(source_key)
                answer = answer_map[item["question_id"]]
                raw_difficulty = float(item.get("difficulty", 0.5))
                difficulty = 1 if raw_difficulty <= 0.45 else 2 if raw_difficulty <= 0.65 else 3
                questions.append(
                    {
                        "question_id": item["question_id"],
                        "type": item["type"],
                        "stem_html": stem,
                        "options": item.get("options", []),
                        "max_score": item["max_score"],
                        "knowledge_tags": item.get("knowledge_tags", []),
                        "difficulty": difficulty,
                        "difficulty_label": cls._difficulty_label(difficulty),
                        "source": {
                            "source_title": source.get("source_title", "技术高考真题"),
                            "original_number": source.get("original_number"),
                            "document_sha256": source.get("document_sha256"),
                        },
                        "authenticity": "高考真题",
                        "_correct_option": answer.get("correct_option"),
                        "_standard_answer": answer.get("standard_answer_text", ""),
                        "_official_analysis": answer.get("analysis_text", ""),
                    }
                )
        return questions

    @staticmethod
    def _public_gaokao_question(question: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in question.items() if not key.startswith("_")}

    @staticmethod
    def _fallback_gaokao_feedback(question: dict[str, Any], student_answer: str) -> dict[str, Any]:
        if question["type"] == "multiple_choice":
            correct = (
                student_answer.strip().upper() == str(question["_correct_option"]).strip().upper()
            )
            score = question["max_score"] if correct else 0
        else:
            answer_terms = {
                term
                for term in re.split(
                    r"[\s，。；、：,:;()（）=+\-*/]+",
                    str(question["_standard_answer"]),
                )
                if len(term) >= 2
            }
            normalized = student_answer.lower()
            hit_count = sum(term.lower() in normalized for term in answer_terms)
            score = round(
                question["max_score"] * hit_count / max(3, len(answer_terms)),
                1,
            )
        return {
            "score": score,
            "diagnosis": (
                "已根据题目考查点和作答证据完成基础评分。请重点检查程序执行顺序、"
                "变量变化和循环边界；系统不会在本环节直接展示可抄写的最终作答内容。"
            ),
            "strengths": ["已经提交了可用于分析的作答过程"],
            "issues": ["需要把关键变量的每一步变化写得更明确"],
            "hints": [
                "先圈出输入、循环条件和最终输出",
                "画一张变量跟踪表，手工执行前两轮",
                "检查下标起点、终点以及循环退出条件",
            ],
            "next_step": "根据提示修改思路后重新抽取一题，比较两次推演过程。",
        }

    @classmethod
    def _sanitize_gaokao_feedback(
        cls,
        question: dict[str, Any],
        feedback: dict[str, Any],
    ) -> dict[str, Any]:
        """Block accidental answer disclosure even if a model ignores the prompt."""
        safe_fallback = cls._fallback_gaokao_feedback(question, "")
        correct_option = str(question.get("_correct_option") or "").strip().upper()
        standard_answer = re.sub(r"\s+", "", str(question.get("_standard_answer") or ""))
        disclosure_markers = (
            "标准答案",
            "正确答案",
            "正确选项",
            "最终答案",
            "完整代码",
            "应选择",
            "应该选",
        )

        def safe_text(value: Any, fallback: str) -> str:
            text = str(value or "").strip()
            compact = re.sub(r"\s+", "", text)
            reveals_option = bool(
                correct_option
                and re.search(
                    rf"(?:答案|选项|应选|选择)(?:是|为|[:：])?{re.escape(correct_option)}(?:\b|。|，)",
                    text,
                    re.IGNORECASE,
                )
            )
            reveals_constructed = bool(len(standard_answer) >= 8 and standard_answer in compact)
            if not text or reveals_option or reveals_constructed:
                return fallback
            if any(marker in text for marker in disclosure_markers):
                return fallback
            return text

        cleaned = dict(feedback)
        cleaned["diagnosis"] = safe_text(feedback.get("diagnosis"), safe_fallback["diagnosis"])
        for field in ("strengths", "issues", "hints"):
            fallback_items = safe_fallback[field]
            items = [safe_text(item, "") for item in feedback.get(field, []) if str(item).strip()]
            cleaned[field] = [item for item in items if item] or fallback_items
        cleaned["next_step"] = safe_text(feedback.get("next_step"), safe_fallback["next_step"])
        return cleaned

    @staticmethod
    def _judge_status(execution: dict[str, Any]) -> str:
        return {
            "timeout": "TIME_LIMIT_EXCEEDED",
            "security": "REJECTED",
            "syntax": "COMPILE_ERROR",
            "runtime": "RUNTIME_ERROR",
            "logic": "WRONG_ANSWER",
        }.get(execution.get("error_type"), "WRONG_ANSWER")

    def _learning_plan(
        self,
        profile: dict[str, Any],
        skills: list[dict[str, Any]],
        projects: list[dict[str, Any]],
        submissions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        weak = sorted(skills, key=lambda item: (item["mastery"], -item["importance"]))[:3]
        weekly = int(profile.get("weekly_hours", 10))
        return {
            "plan_id": f"derived_{profile.get('profile_version', 0)}",
            "current_stage": "Python 后端岗位基础",
            "weak_skills": [item["name"] for item in weak],
            "long_term_roadmap": self.knowledge.learning_phases(),
            "weekly_plan": [
                {
                    "skill_id": item["skill_id"],
                    "skill": item["name"],
                    "objective": item["outcomes"][0],
                    "estimated_hours": max(2, min(4, weekly // 3)),
                    "task": "完成 2 道代码题并写一段复盘",
                    "acceptance": "至少一次独立通过，能解释失败原因",
                }
                for item in weak
            ],
            "next_action": (
                "完成一个项目方案并获取多维评价"
                if not any(item["status"] == "evaluated" for item in projects)
                else "完成一道当前薄弱技能代码题"
                if len(submissions) < 3
                else f"继续补强 {weak[0]['name']}"
            ),
        }

    @staticmethod
    def _career_explanation(skill_id: str) -> str:
        explanations = {
            "HTTP_REST": (
                "HTTP 是后端服务与客户端协作的协议基础；REST 重点在资源建模、"
                "方法语义、状态码与一致的错误响应。"
            ),
            "FASTAPI_ROUTE": (
                "FastAPI 路由不仅是写装饰器，还要处理参数来源、响应模型、"
                "状态码、依赖注入和异常映射。"
            ),
            "MYSQL_SQL": (
                "MySQL 学习应从正确建模和查询开始，再进入索引、执行计划、事务与并发一致性。"
            ),
            "TESTING_PYTEST": (
                "测试是岗位工程能力证据。先覆盖正常、边界、异常路径，"
                "再考虑 fixture、mock 和集成测试。"
            ),
        }
        return explanations.get(
            skill_id,
            "该能力需要通过概念理解、可执行练习和结果复盘三步形成稳定证据。",
        )

    @staticmethod
    def _requirement_document(project: dict[str, Any]) -> str:
        requirements = "\n".join(
            f"{index}. {item}" for index, item in enumerate(project["requirements"], 1)
        )
        non_functional = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(project["non_functional_requirements"], 1)
        )
        constraints = "\n".join(f"- {item}" for item in project["constraints"])
        return f"""# 项目实训任务

## 一、项目名称
{project["title"]}

## 二、项目背景
{project["background"]}

## 三、业务目标
{project["business_goal"]}

## 四、功能需求
{requirements}

## 五、非功能需求
{non_functional}

## 六、项目约束
{constraints}

# 学员回答区域

## 1. 整体开发方案
<!-- 请在下方填写，说明业务流程和实施步骤 -->



## 2. 技术选型与理由
<!-- 请说明选择、适用场景和取舍 -->



## 3. 系统模块拆解
<!-- 请列出模块职责和依赖关系 -->



## 4. 数据库设计
<!-- 请给出核心表、字段、关系和索引 -->



## 5. API 设计
<!-- 请给出关键路径、方法、状态码和错误处理 -->


"""

    @staticmethod
    def _problem_document(project: dict[str, Any]) -> str:
        blocks = []
        for index, problem in enumerate(project["problems"], 1):
            blocks.append(
                f"## 问题 {index}：{problem['category']}\n\n{problem['description']}\n\n"
                f"### 请分析原因并给出解决方案\n\n<!-- 回答 {problem['problem_id']} -->\n\n\n"
            )
        return "# 项目潜在问题分析\n\n" + "\n---\n\n".join(blocks)

    @staticmethod
    def _parse_project_document(text: str) -> dict[str, Any]:
        aliases = {
            "development_plan": ["整体开发方案", "开发方案"],
            "technology_selection": ["技术选型"],
            "architecture_design": ["系统模块拆解", "架构设计", "模块拆解"],
            "database_design": ["数据库设计"],
            "api_design": ["api 设计", "接口设计"],
        }
        headings = list(re.finditer(r"(?im)^#{1,4}\s+(.+?)\s*$", text))
        result: dict[str, Any] = {}
        for index, match in enumerate(headings):
            title = match.group(1).lower()
            content = text[
                match.end() : headings[index + 1].start()
                if index + 1 < len(headings)
                else len(text)
            ]
            content = re.sub(r"<!--.*?-->", "", content, flags=re.S).strip()
            for field, names in aliases.items():
                if any(name.lower() in title for name in names) and len(content) >= 10:
                    result[field] = content
        problem_solutions: dict[str, str] = {}
        for match in re.finditer(r"(?is)(P\d{3}-\d{2}).*?(?=(?:P\d{3}-\d{2})|\Z)", text):
            problem_solutions[match.group(1)] = match.group(0).strip()
        if not problem_solutions:
            problem_sections = [
                text[
                    match.end() : headings[index + 1].start()
                    if index + 1 < len(headings)
                    else len(text)
                ].strip()
                for index, match in enumerate(headings)
                if "问题" in match.group(1)
            ]
            problem_solutions = {
                f"DOCUMENT-PROBLEM-{index}": value
                for index, value in enumerate(problem_sections, 1)
                if len(value) >= 10
            }
        result["problem_solutions"] = problem_solutions
        missing = [field for field in aliases if field not in result]
        if missing:
            raise InputValidationError(f"上传文档缺少必答章节：{', '.join(missing)}")
        return result

    def _score_project(
        self, project: dict[str, Any], answer: dict[str, Any]
    ) -> list[dict[str, Any]]:
        combined = "\n".join(
            [
                answer["development_plan"],
                answer["technology_selection"],
                answer["architecture_design"],
                answer["database_design"],
                answer["api_design"],
                *answer["problem_solutions"].values(),
            ]
        ).lower()
        requirement_hits = sum(
            item.lower().split()[0] in combined for item in project["requirements"]
        )
        reference_hits = sum(
            point.lower() in combined
            for problem in project["problems"]
            for point in problem["reference_points"]
        )
        section_lengths = {
            key: len(answer[key])
            for key in (
                "development_plan",
                "technology_selection",
                "architecture_design",
                "database_design",
                "api_design",
            )
        }
        problem_count = sum(bool(value.strip()) for value in answer["problem_solutions"].values())
        raw_scores = {
            "requirement_understanding": min(
                95, 52 + requirement_hits * 9 + (10 if "用户" in combined else 0)
            ),
            "solution_completeness": min(
                96,
                40
                + sum(length >= 60 for length in section_lengths.values()) * 10
                + min(problem_count, 3) * 4,
            ),
            "technology_selection": min(
                94,
                50
                + sum(
                    word in combined
                    for word in ["fastapi", "mysql", "redis", "pytest", "因为", "适合"]
                )
                * 7,
            ),
            "system_design": min(
                94,
                48
                + sum(word in combined for word in ["模块", "服务", "依赖", "分层", "认证", "权限"])
                * 7,
            ),
            "problem_analysis": min(96, 42 + min(problem_count, 3) * 10 + reference_hits * 5),
            "engineering_feasibility": min(
                94,
                48
                + sum(word in combined for word in ["事务", "索引", "测试", "日志", "异常", "分页"])
                * 7,
            ),
            "risk_awareness": min(
                95,
                45
                + sum(
                    word in combined for word in ["安全", "越权", "风险", "一致性", "失败", "回滚"]
                )
                * 8,
            ),
            "clarity": min(95, 55 + sum(length >= 80 for length in section_lengths.values()) * 6),
        }
        if section_lengths["database_design"] < 40:
            raw_scores["system_design"] = min(raw_scores["system_design"], 65)
            raw_scores["engineering_feasibility"] = min(raw_scores["engineering_feasibility"], 62)
        if not answer["problem_solutions"]:
            raw_scores["problem_analysis"] = 35
        results = []
        for key, label, weight in RUBRIC:
            score = float(raw_scores[key])
            good = score >= 75
            results.append(
                {
                    "key": key,
                    "name": label,
                    "weight": weight,
                    "score": score,
                    "evidence": self._dimension_evidence(
                        key, answer, requirement_hits, reference_hits
                    ),
                    "strengths": [
                        f"{label}包含可核验的项目细节" if good else f"已对{label}做出基础回答"
                    ],
                    "weaknesses": [
                        f"{label}仍缺少边界、取舍或实施细节"
                        if not good
                        else f"{label}可进一步补充容量估算和验证方法"
                    ],
                    "suggestions": [self._dimension_suggestion(key)],
                }
            )
        return results

    @staticmethod
    def _dimension_evidence(
        key: str,
        answer: dict[str, Any],
        requirement_hits: int,
        reference_hits: int,
    ) -> list[str]:
        evidence = {
            "requirement_understanding": f"回答命中 {requirement_hits} 项需求关键词",
            "solution_completeness": (
                f"5 个必答章节均存在，问题回答 {len(answer['problem_solutions'])} 项"
            ),
            "technology_selection": f"技术选型回答长度 {len(answer['technology_selection'])} 字符",
            "system_design": (
                f"架构回答 {len(answer['architecture_design'])} 字符，"
                f"数据库回答 {len(answer['database_design'])} 字符"
            ),
            "problem_analysis": (
                f"问题回答 {len(answer['problem_solutions'])} 项，"
                f"命中内部参考点 {reference_hits} 项"
            ),
            "engineering_feasibility": "基于事务、索引、测试、日志、异常和分页等工程词检查",
            "risk_awareness": "基于安全、越权、一致性、失败与回滚等风险点检查",
            "clarity": "基于必答章节结构和每节有效内容检查，不按总字数直接给高分",
        }
        return [evidence[key]]

    @staticmethod
    def _dimension_suggestion(key: str) -> str:
        suggestions = {
            "requirement_understanding": "补一张角色—用例—权限矩阵，并逐项映射核心需求。",
            "solution_completeness": "为每个模块补充输入、输出、失败路径和验收方式。",
            "technology_selection": "说明每项技术解决的具体问题、替代方案和不采用的原因。",
            "system_design": "补充模块边界、调用关系、核心表关系和事务边界。",
            "problem_analysis": "按原因—影响—方案—验证四步回答每个潜在问题。",
            "engineering_feasibility": "增加索引、日志、异常映射、测试和回滚策略。",
            "risk_awareness": "列出安全、数据一致性和故障恢复风险及监控指标。",
            "clarity": "使用小标题、列表和可核验结论，删除重复描述。",
        }
        return suggestions[key]

    @staticmethod
    def _project_report(session: dict[str, Any], evaluation: dict[str, Any]) -> str:
        rows = "\n".join(
            f"| {item['name']} | {item['score']:.0f} | {item['evidence'][0]} |"
            for item in evaluation["dimensions"]
        )
        suggestions = "\n".join(
            f"- **{item['name']}**：{item['suggestions'][0]}" for item in evaluation["dimensions"]
        )
        return f"""# 项目实训评价报告

## 基本信息
- 岗位：Python 后端开发工程师
- 项目：{session["title"]}
- 评价时间：{evaluation["evaluated_at"]}

## 总分
**{evaluation["total_score"]} / 100**

## 分项评分
| 维度 | 分数 | 评分依据 |
|---|---:|---|
{rows}

## 做得好的地方
{chr(10).join(f"- {item}" for item in evaluation["overall_strengths"])}

## 需要改进的地方
{chr(10).join(f"- {item}" for item in evaluation["overall_weaknesses"])}

## 逐项修改建议
{suggestions}

## 推荐补充技能
{chr(10).join(f"- {item}" for item in evaluation["recommended_skills"])}

## 下一步学习路线
{chr(10).join(f"- {item}" for item in evaluation["next_learning_actions"])}
"""

    @staticmethod
    def _default_profile_v1(student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        is_high_school = str(auth_profile.get("grade", "")).startswith("grade_")
        return {
            "student_id": student_id,
            "student_name": auth_profile.get("studentName", "同学"),
            "target_job_id": "JOB_PY_BACKEND",
            "identity": "high_school_student" if is_high_school else "undergraduate",
            "education_stage": "high_school" if is_high_school else "undergraduate",
            "programming_level": "beginner" if is_high_school else "basic",
            "known_languages": ["Python"],
            "weekly_hours": 10,
            "learning_goal": "gaokao" if is_high_school else "internship",
            "target_period_weeks": 16,
            "current_mode": "CAREER",
            "profile_version": 0,
        }
