"""Deterministic teaching workflow for the student programming growth Agent."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError
from ai_education.domain.programming_learning import (
    ProgrammingCodeReviewInput,
    ProgrammingDiagnosticSubmission,
    ProgrammingInterviewAnswerInput,
    ProgrammingInterviewCreateInput,
    ProgrammingProfileInput,
    ProgrammingProjectHintInput,
    ProgrammingProjectRecommendationInput,
)
from ai_education.programming_learning_repository import ProgrammingLearningRepository
from ai_education.services.programming_knowledge import ProgrammingKnowledgeService


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _level(score: float) -> str:
    if score < 0.18:
        return "L0"
    if score < 0.35:
        return "L1"
    if score < 0.55:
        return "L2"
    if score < 0.72:
        return "L3"
    if score < 0.88:
        return "L4"
    return "L5"


class ProgrammingLearningService:
    def __init__(
        self,
        repository: ProgrammingLearningRepository,
        knowledge: ProgrammingKnowledgeService,
    ) -> None:
        self.repository = repository
        self.knowledge = knowledge

    def dashboard(self, student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        configured = profile is not None
        if profile is None:
            profile = self._default_profile(student_id, auth_profile)
        states = self._decorated_states(student_id)
        projects = [
            item["payload"]
            for item in self.repository.list_records(student_id, record_type="project", limit=4)
        ]
        roadmaps = self.repository.list_records(student_id, record_type="roadmap", limit=1)
        return {
            "target_user": "采用全国一卷能力导向的中国普通高中学生",
            "profile": {**profile, "configured": configured},
            "major_direction": self._major_direction(profile),
            "roadmap": roadmaps[0]["payload"] if roadmaps else None,
            "skill_states": states,
            "active_projects": projects,
            "weekly_report": self.weekly_report(student_id, profile=profile),
            "knowledge": {
                "content_version": self.knowledge.version,
                "source_references": self.knowledge.sources(),
                "supported_languages": ["Python"],
            },
            "safety": {
                "full_answer_default": False,
                "code_execution": "disabled_static_analysis_only",
                "minor_protection": True,
                "ability_claims_require_evidence": True,
            },
        }

    def update_profile(
        self,
        student_id: str,
        body: ProgrammingProfileInput,
        auth_profile: dict[str, Any],
    ) -> dict[str, Any]:
        effective_weekly = body.weekly_available_minutes
        if body.exam_period:
            effective_weekly = max(30, min(effective_weekly // 2, 90))
        now = _now()
        profile = {
            "student_id": student_id,
            "grade": auth_profile.get("grade", "grade_10"),
            "exam_context": "national_paper_1",
            **body.model_dump(mode="json"),
            "effective_weekly_minutes": effective_weekly,
            "profile_version": (self.repository.load_profile(student_id) or {}).get(
                "profile_version", 0
            )
            + 1,
            "content_version": self.knowledge.version,
            "updated_at": now,
        }
        self.repository.save_profile(profile)
        roadmap = self._roadmap(profile)
        self.repository.save_record(
            {
                "record_id": roadmap["roadmap_id"],
                "student_id": student_id,
                "record_type": "roadmap",
                "status": "active",
                "payload": roadmap,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {**profile, "configured": True, "roadmap": roadmap}

    def create_diagnostic(self, student_id: str) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        if not profile:
            raise InputValidationError("请先完成编程学习画像，再开始低门槛诊断")
        diagnostic_id = f"prog_diag_{uuid4().hex}"
        questions = self.knowledge.diagnostic_questions()
        now = _now()
        private_payload = {
            "diagnostic_id": diagnostic_id,
            "status": "in_progress",
            "questions": questions,
            "created_at": now,
        }
        self.repository.save_record(
            {
                "record_id": diagnostic_id,
                "student_id": student_id,
                "record_type": "diagnostic",
                "status": "in_progress",
                "payload": private_payload,
                "created_at": now,
                "updated_at": now,
            }
        )
        visible = [
            {
                key: value
                for key, value in item.items()
                if key not in {"answer_index", "explanation"}
            }
            for item in questions
        ]
        return {
            "diagnostic_id": diagnostic_id,
            "status": "in_progress",
            "estimated_minutes": 20,
            "questions": visible,
            "answer_content_exposed": False,
        }

    def submit_diagnostic(
        self,
        student_id: str,
        diagnostic_id: str,
        body: ProgrammingDiagnosticSubmission,
    ) -> dict[str, Any]:
        record = self.repository.load_record(
            diagnostic_id, student_id=student_id, record_type="diagnostic"
        )
        if record["status"] != "in_progress":
            raise InputValidationError("该诊断已经提交")
        questions = record["payload"]["questions"]
        by_id = {item["question_id"]: item for item in questions}
        if {item.question_id for item in body.answers} != set(by_id):
            raise InputValidationError("请完成全部诊断题后再提交")
        results = []
        correct_count = 0
        for answer in body.answers:
            question = by_id[answer.question_id]
            correct = answer.selected_option == question["answer_index"]
            correct_count += int(correct)
            state = self._record_evidence(
                student_id,
                skill_id=question["skill_id"],
                event_type="baseline_diagnostic",
                source_id=diagnostic_id,
                score=1.0 if correct else 0.0,
                independence=max(0.4, answer.confidence),
                reasoning=0.55,
                verification=0.5,
                hint_level=0,
                description=f"低门槛诊断：{question['dimension']}",
            )
            results.append(
                {
                    "question_id": answer.question_id,
                    "dimension": question["dimension"],
                    "skill_id": question["skill_id"],
                    "correct": correct,
                    "correct_option": question["answer_index"],
                    "explanation": question["explanation"],
                    "mastery_update": state,
                }
            )
        score = round(correct_count / len(questions), 4)
        completed = {
            "diagnostic_id": diagnostic_id,
            "status": "completed",
            "correct_count": correct_count,
            "question_count": len(questions),
            "score": score,
            "results": results,
            "conclusion": self._diagnostic_conclusion(score),
            "completed_at": _now(),
            "single_assessment_not_deterministic": True,
        }
        record.update(status="completed", payload=completed, updated_at=_now())
        self.repository.save_record(record)
        return completed

    def review_code(self, student_id: str, body: ProgrammingCodeReviewInput) -> dict[str, Any]:
        review_id = f"code_review_{uuid4().hex}"
        findings: list[dict[str, Any]] = []
        parsed = False
        try:
            tree = ast.parse(body.code)
            parsed = True
        except SyntaxError as exc:
            findings.append(
                {
                    "finding_id": f"finding_{uuid4().hex[:10]}",
                    "severity": "high",
                    "category": "syntax",
                    "line_start": exc.lineno or 1,
                    "line_end": exc.lineno or 1,
                    "message": self._syntax_message(exc),
                    "skill_ids": ["programming.debugging"],
                    "confidence": 0.98,
                }
            )
            tree = None
        if tree is not None:
            findings.extend(self._static_findings(tree, body.code))
        primary = findings[0] if findings else None
        allowed_level = body.hint_level
        if allowed_level == 5 and not (body.review_stage or body.teacher_authorized):
            allowed_level = 4
        hint = self.knowledge.hint(allowed_level)
        if primary:
            hint = f"{hint} 当前优先检查：{primary['message']}"
        score = (
            0.78 if parsed and not any(item["severity"] == "high" for item in findings) else 0.35
        )
        state = self._record_evidence(
            student_id,
            skill_id="programming.debugging" if findings else "thinking.verification",
            event_type="code_review",
            source_id=review_id,
            score=score,
            independence=max(0.25, 1 - allowed_level * 0.14),
            reasoning=0.65 if body.observed_problem else 0.5,
            verification=0.65 if body.expected_behavior else 0.45,
            hint_level=allowed_level,
            description="Python 静态检查与调试证据",
        )
        result = {
            "review_id": review_id,
            "language": "python",
            "parse_coverage": 1.0 if parsed else 0.0,
            "execution": {
                "status": "not_executed",
                "reason": "当前首期仅提供静态分析；未进入隔离沙箱，不声称运行成功",
            },
            "findings": findings,
            "root_causes": [
                {
                    "rank": index + 1,
                    "finding_id": item["finding_id"],
                    "reason": item["message"],
                    "confidence": item["confidence"],
                }
                for index, item in enumerate(findings[:3])
            ],
            "next_hint": {
                "hint_level": allowed_level,
                "content": hint,
                "answer_leakage_blocked": body.hint_level == 5 and allowed_level < 5,
            },
            "validation_plan": [
                "先用题目给出的普通样例核对输入输出",
                "再补充空值、单元素或最小值等边界样例",
                "最后解释每个关键变量在一轮处理前后的变化",
            ],
            "must_fix_count": sum(item["severity"] == "high" for item in findings),
            "optimization_count": sum(item["severity"] != "high" for item in findings),
            "evidence_update": state,
            "created_at": _now(),
        }
        self._save_simple_record(student_id, review_id, "code_review", result)
        return result

    def recommend_project(
        self,
        student_id: str,
        body: ProgrammingProjectRecommendationInput,
    ) -> dict[str, Any]:
        profile = self.repository.load_profile(student_id)
        if not profile:
            raise InputValidationError("请先完成编程学习画像，再推荐项目")
        templates = self.knowledge.projects()
        interest = body.interest.lower()
        ranked = sorted(
            templates,
            key=lambda item: (
                not any(
                    token.lower() in interest or interest in token.lower()
                    for token in item["interests"]
                ),
                abs(item["duration_weeks"] - body.available_weeks),
                item["difficulty"],
            ),
        )
        template = ranked[0]
        instance_id = f"project_{uuid4().hex}"
        task_minutes = min(
            profile["max_session_minutes"], 40 if profile["learning_mode"] == "beginner" else 60
        )
        milestones = []
        for milestone_index, milestone in enumerate(template["milestones"], start=1):
            tasks = []
            for task_index, title in enumerate(milestone["tasks"], start=1):
                task_id = f"{instance_id}_m{milestone_index}_t{task_index}"
                tasks.append(
                    {
                        "task_id": task_id,
                        "title": title,
                        "estimated_minutes": task_minutes,
                        "required_skills": template["target_skills"][:3],
                        "deliverables": [f"可展示成果：{title}"],
                        "acceptance_criteria": [
                            "能够演示本步骤的可观察结果",
                            "至少记录一个正常样例和一个边界样例",
                        ],
                        "hint_policy": "progressive_H0_H5",
                        "reflection_questions": ["本步最容易出错的条件是什么？"],
                        "status": "pending",
                    }
                )
            milestones.append(
                {
                    "milestone_id": f"{instance_id}_m{milestone_index}",
                    "title": milestone["title"],
                    "acceptance": "所有原子任务均产生可演示结果",
                    "tasks": tasks,
                }
            )
        result = {
            "project_instance_id": instance_id,
            "project_id": template["project_id"],
            "title": template["title"],
            "difficulty": template["difficulty"],
            "duration_weeks": min(body.available_weeks, template["duration_weeks"]),
            "estimated_total_minutes": sum(
                task["estimated_minutes"] for milestone in milestones for task in milestone["tasks"]
            ),
            "target_skills": template["target_skills"],
            "cross_subject_links": template["cross_subject_links"],
            "milestones": milestones,
            "portfolio_use": body.use_for_portfolio,
            "portfolio_rule": "只记录学生真实完成并可说明的成果，不代写或编造项目经历",
            "source_references": self.knowledge.sources(),
            "status": "active",
            "created_at": _now(),
        }
        self._save_simple_record(student_id, instance_id, "project", result, status="active")
        return result

    def next_project_hint(
        self,
        student_id: str,
        project_id: str,
        body: ProgrammingProjectHintInput,
    ) -> dict[str, Any]:
        record = self.repository.load_record(
            project_id, student_id=student_id, record_type="project"
        )
        tasks = [
            task for milestone in record["payload"]["milestones"] for task in milestone["tasks"]
        ]
        task = next((item for item in tasks if item["task_id"] == body.task_id), None)
        if not task:
            raise InputValidationError("项目任务不存在")
        next_level = min(
            (max(body.previous_hint_levels) + 1) if body.previous_hint_levels else 0,
            body.max_allowed_level,
        )
        if next_level == 5 and not (body.review_stage or body.teacher_authorized):
            next_level = 4
        hint_id = f"project_hint_{uuid4().hex}"
        result = {
            "hint_id": hint_id,
            "project_instance_id": project_id,
            "task_id": task["task_id"],
            "hint_level": next_level,
            "hint": self.knowledge.hint(next_level),
            "observed_problem": body.observed_problem,
            "check_questions": [
                "当前最小可运行或可展示的结果是什么？",
                "哪一条验收标准还没有可核验证据？",
            ],
            "verification_action": task["acceptance_criteria"][1],
            "answer_leakage_risk": round(0.05 + next_level * 0.08, 2),
            "full_reference_available": next_level == 5,
            "created_at": _now(),
        }
        self._record_evidence(
            student_id,
            skill_id=task["required_skills"][0],
            event_type="project_hint",
            source_id=hint_id,
            score=0.5,
            independence=max(0.2, 1 - next_level * 0.15),
            reasoning=0.5,
            verification=0.5,
            hint_level=next_level,
            description="项目任务渐进提示记录（不作为失败标签）",
        )
        return result

    def create_interview(
        self, student_id: str, body: ProgrammingInterviewCreateInput
    ) -> dict[str, Any]:
        session_id = f"programming_interview_{uuid4().hex}"
        questions = self.knowledge.interview_questions()
        ordered = sorted(questions, key=lambda item: item["topic"] != body.focus)
        selected = ordered[: min(4, max(2, body.available_minutes // 5))]
        result = {
            "session_id": session_id,
            **body.model_dump(mode="json"),
            "status": "in_progress",
            "questions": selected,
            "answers": [],
            "rules": [
                "只使用自己的真实经历；没有项目时可以说明尚未完成",
                "评分用于训练表达，不据此断言专业适配性",
            ],
            "created_at": _now(),
        }
        self._save_simple_record(student_id, session_id, "interview", result)
        return result

    def score_interview_answer(
        self,
        student_id: str,
        session_id: str,
        body: ProgrammingInterviewAnswerInput,
    ) -> dict[str, Any]:
        record = self.repository.load_record(
            session_id, student_id=student_id, record_type="interview"
        )
        question = next(
            (
                item
                for item in record["payload"]["questions"]
                if item["question_id"] == body.question_id
            ),
            None,
        )
        if not question:
            raise InputValidationError("面试问题不存在")
        text = body.answer_text
        length_score = min(len(text) / 180, 1.0)
        dimensions = {
            "relevance": round(min(0.55 + length_score * 0.35, 0.9), 2),
            "logic": round(
                0.45 + 0.12 * sum(token in text for token in ("首先", "其次", "因为", "所以")), 2
            ),
            "accuracy": 0.72,
            "evidence": round(
                min(
                    0.4 + 0.15 * sum(token in text for token in ("例如", "我", "测试", "结果")), 0.9
                ),
                2,
            ),
            "reflection": round(
                min(0.35 + 0.2 * sum(token in text for token in ("改进", "不足", "下次")), 0.85), 2
            ),
            "expression": round(min(0.5 + length_score * 0.35, 0.9), 2),
            "time_control": 0.75,
        }
        weights = {
            "relevance": 0.2,
            "logic": 0.2,
            "accuracy": 0.2,
            "evidence": 0.15,
            "reflection": 0.1,
            "expression": 0.1,
            "time_control": 0.05,
        }
        overall = round(sum(dimensions[key] * weight for key, weight in weights.items()), 3)
        missing = []
        if dimensions["evidence"] < 0.6:
            missing.append("补充一个自己确实做过、能够核验的具体例子")
        if dimensions["reflection"] < 0.55:
            missing.append("说明一次不足以及下一步如何改进")
        if dimensions["logic"] < 0.65:
            missing.append("使用“观点—依据—结果”的结构重新组织")
        result = {
            "score_id": f"interview_score_{uuid4().hex}",
            "question_id": body.question_id,
            "overall_score": overall,
            "dimension_scores": dimensions,
            "strengths": ["回答内容来自学生当前输入，未补写不存在的经历"],
            "missing_points": missing,
            "recommended_followup": "你能补充一个验证结果或失败后改进的具体细节吗？",
            "authenticity_notice": "奖项、数据和个人贡献需要由学生本人确认，系统不会代为编造",
            "created_at": _now(),
        }
        record["payload"]["answers"].append({**result, "answer_text": text})
        record["updated_at"] = _now()
        self.repository.save_record(record)
        result["evidence_update"] = self._record_evidence(
            student_id,
            skill_id="project.presentation",
            event_type="interview_answer",
            source_id=result["score_id"],
            score=overall,
            independence=0.8,
            reasoning=dimensions["logic"],
            verification=dimensions["evidence"],
            hint_level=0,
            description="项目陈述模拟的维度评分证据",
        )
        return result

    def weekly_report(
        self, student_id: str, *, profile: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        profile = profile or self.repository.load_profile(student_id)
        events = self.repository.list_events(student_id, limit=50)
        week_start = datetime.now(UTC) - timedelta(days=7)
        recent = [
            item
            for item in events
            if datetime.fromisoformat(item["created_at"]).astimezone(UTC) >= week_start
        ]
        hint_events = [item for item in recent if item["hint_level"] > 0]
        states = self._decorated_states(student_id)
        return {
            "period_days": 7,
            "completed_learning_events": len(recent),
            "evidence_count": len(recent),
            "hint_usage_count": len(hint_events),
            "average_hint_level": round(
                sum(item["hint_level"] for item in hint_events) / len(hint_events), 2
            )
            if hint_events
            else 0,
            "skill_changes": states[:6],
            "completed_outputs": [
                item["description"] for item in recent if item["event_type"] != "project_hint"
            ][:6],
            "pace_adjustment": self._pace_adjustment(profile),
            "data_quality": {
                "coverage": round(min(len(recent) / 8, 1.0), 2),
                "limitations": []
                if len(recent) >= 3
                else ["当前证据较少，不生成稳定能力或专业适配结论"],
            },
            "next_step": self._next_step(states, bool(profile)),
        }

    def _record_evidence(
        self,
        student_id: str,
        *,
        skill_id: str,
        event_type: str,
        source_id: str,
        score: float,
        independence: float,
        reasoning: float,
        verification: float,
        hint_level: int,
        description: str,
    ) -> dict[str, Any]:
        previous = self.repository.get_skill_state(student_id, skill_id)
        previous_mastery = float(previous["mastery"] if previous else 0.15)
        evidence_weight = max(
            0.05, min(1.0, independence * 0.4 + reasoning * 0.3 + verification * 0.3)
        )
        raw_delta = (score - previous_mastery) * 0.2 * evidence_weight
        bounded_delta = max(-0.08, min(0.12, raw_delta))
        new_mastery = round(max(0.0, min(1.0, previous_mastery + bounded_delta)), 4)
        count = int(previous["evidence_count"] if previous else 0) + 1
        event_id = f"programming_event_{uuid4().hex}"
        created_at = _now()
        event = {
            "event_id": event_id,
            "student_id": student_id,
            "event_type": event_type,
            "source_id": source_id,
            "skill_id": skill_id,
            "score": round(score, 4),
            "independence": round(independence, 4),
            "reasoning": round(reasoning, 4),
            "verification": round(verification, 4),
            "evidence_weight": round(evidence_weight, 4),
            "hint_level": hint_level,
            "description": description,
            "created_at": created_at,
        }
        state = {
            "student_id": student_id,
            "skill_id": skill_id,
            "previous_mastery": round(previous_mastery, 4),
            "mastery": new_mastery,
            "level": _level(new_mastery),
            "confidence": round(min(0.9, 0.25 + count * 0.1), 2),
            "evidence_count": count,
            "last_evidence_id": event_id,
            "change": round(new_mastery - previous_mastery, 4),
            "change_bounded": True,
            "updated_at": created_at,
        }
        self.repository.save_evidence_bundle(event, state)
        return state

    def _decorated_states(self, student_id: str) -> list[dict[str, Any]]:
        states = self.repository.list_skill_states(student_id)
        return [
            {**item, "label": self.knowledge.skill(item["skill_id"])["label"]}
            for item in sorted(states, key=lambda value: value["mastery"], reverse=True)
        ]

    def _save_simple_record(
        self,
        student_id: str,
        record_id: str,
        record_type: str,
        payload: dict[str, Any],
        *,
        status: str = "in_progress",
    ) -> None:
        now = _now()
        self.repository.save_record(
            {
                "record_id": record_id,
                "student_id": student_id,
                "record_type": record_type,
                "status": status,
                "payload": payload,
                "created_at": payload.get("created_at", now),
                "updated_at": now,
            }
        )

    @staticmethod
    def _default_profile(student_id: str, auth_profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "student_id": student_id,
            "grade": auth_profile.get("grade", "grade_10"),
            "learning_mode": "beginner",
            "target_direction": "computer_science_exploration",
            "weekly_available_minutes": 120,
            "effective_weekly_minutes": 120,
            "max_session_minutes": 40,
            "exam_period": False,
            "programming_months": 0,
            "project_count": 0,
            "interests": ["学习工具"],
            "profile_version": 0,
        }

    def _roadmap(self, profile: dict[str, Any]) -> dict[str, Any]:
        stage_names = [
            ("编程体验与计算思维", ["输入输出", "变量", "规则推理"]),
            ("Python 基础问题求解", ["条件", "循环", "函数"]),
            ("跨学科小项目", ["需求拆解", "数据处理", "测试验证"]),
            ("项目展示与专业探索", ["项目陈述", "反思改进", "专业认知"]),
        ]
        weekly = profile["effective_weekly_minutes"]
        return {
            "roadmap_id": f"programming_roadmap_{uuid4().hex}",
            "duration_weeks": 16,
            "weekly_minutes": weekly,
            "stages": [
                {
                    "stage": index,
                    "weeks": f"第 {(index - 1) * 4 + 1}—{index * 4} 周",
                    "title": title,
                    "focus": focus,
                    "weekly_output": "至少一个可运行或可展示的小成果",
                    "checkpoint": "用新场景任务、边界测试和口头解释共同验收",
                }
                for index, (title, focus) in enumerate(stage_names, start=1)
            ],
            "exam_period_adjustment": {
                "active": profile["exam_period"],
                "new_knowledge_ratio": 0.2 if profile["exam_period"] else 0.45,
                "review_ratio": 0.6 if profile["exam_period"] else 0.35,
                "reason": "高考主科学习优先，考试期自动减量"
                if profile["exam_period"]
                else "当前按常规低负荷节奏安排",
            },
            "adjustment_triggers": [
                "连续两周完成率低于 60%",
                "实际耗时持续超过预计 1.5 倍",
                "进入周测、月考或模拟考试密集期",
            ],
            "content_version": self.knowledge.version,
        }

    @staticmethod
    def _major_direction(profile: dict[str, Any]) -> dict[str, Any]:
        labels = {
            "computer_science_exploration": "计算机科学探索",
            "artificial_intelligence": "人工智能体验",
            "data_science": "数据科学体验",
            "software_engineering": "软件工程与项目体验",
            "algorithm_advanced": "算法与信息学拔高",
        }
        return {
            "direction_id": profile["target_direction"],
            "label": labels[profile["target_direction"]],
            "positioning": "探索建议，不是专业适配结论",
            "high_school_preparation": ["Python 基础", "问题分解", "测试验证", "项目表达"],
            "uncertainties": ["需要通过后续练习和真实项目持续验证"],
        }

    @staticmethod
    def _diagnostic_conclusion(score: float) -> dict[str, Any]:
        if score >= 0.8:
            return {"starting_point": "有基础拔高入口", "next": "挑战式代码排错与小项目"}
        if score >= 0.4:
            return {"starting_point": "基础体验入口", "next": "变量、条件与循环的短周期练习"}
        return {"starting_point": "零基础入门入口", "next": "规则推理、输入输出与可视化小步骤"}

    @staticmethod
    def _syntax_message(exc: SyntaxError) -> str:
        messages = {
            "expected ':'": "这一行末尾可能缺少冒号，请先检查条件、循环或函数定义。",
            "unexpected indent": "这一行出现了意外缩进，请比较它与上一层代码的对齐关系。",
            "unterminated string literal": "字符串引号可能没有成对结束。",
        }
        return messages.get(exc.msg, f"Python 无法解析这一行：{exc.msg}")

    @staticmethod
    def _static_findings(tree: ast.AST, code: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.While)
                and isinstance(node.test, ast.Constant)
                and node.test.value is True
                and not any(isinstance(child, ast.Break) for child in ast.walk(node))
            ):
                findings.append(
                    {
                        "finding_id": f"finding_{uuid4().hex[:10]}",
                        "severity": "high",
                        "category": "logic",
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno),
                        "message": "while True 中没有发现退出路径，程序可能无法结束。",
                        "skill_ids": ["programming.loop", "programming.debugging"],
                        "confidence": 0.88,
                    }
                )
            if isinstance(node, ast.For):
                assigned = {
                    target.id
                    for child in node.body
                    if isinstance(child, ast.Assign)
                    for target in child.targets
                    if isinstance(target, ast.Name)
                }
                suspicious = assigned & {"max_value", "maximum", "total", "result"}
                if suspicious:
                    findings.append(
                        {
                            "finding_id": f"finding_{uuid4().hex[:10]}",
                            "severity": "medium",
                            "category": "loop_state",
                            "line_start": node.lineno,
                            "line_end": getattr(node, "end_lineno", node.lineno),
                            "message": (
                                f"变量 {sorted(suspicious)[0]} 在循环体内赋值，"
                                "请确认它是否被每轮意外重置。"
                            ),
                            "skill_ids": ["programming.loop", "programming.debugging"],
                            "confidence": 0.72,
                        }
                    )
        if "print(" not in code and not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)
        ):
            findings.append(
                {
                    "finding_id": f"finding_{uuid4().hex[:10]}",
                    "severity": "low",
                    "category": "observable_output",
                    "line_start": 1,
                    "line_end": max(1, len(code.splitlines())),
                    "message": "没有发现可观察输出；请对照题目确认结果是否需要显示。",
                    "skill_ids": ["programming.input_output"],
                    "confidence": 0.65,
                }
            )
        return findings[:8]

    @staticmethod
    def _pace_adjustment(profile: dict[str, Any] | None) -> dict[str, Any]:
        if not profile:
            return {"status": "profile_needed", "recommended_weekly_minutes": 0}
        return {
            "status": "exam_period_limited" if profile["exam_period"] else "normal",
            "recommended_weekly_minutes": profile["effective_weekly_minutes"],
            "new_knowledge_ratio": 0.2 if profile["exam_period"] else 0.45,
            "restore_condition": "考试结束且连续一周负荷正常" if profile["exam_period"] else None,
        }

    @staticmethod
    def _next_step(states: list[dict[str, Any]], has_profile: bool) -> str:
        if not has_profile:
            return "先完成最少必要画像，系统再安排低门槛诊断"
        if not states:
            return "完成 20 分钟基础诊断，建立第一批客观学习证据"
        weakest = min(states, key=lambda item: item["mastery"])
        return f"围绕“{weakest['label']}”完成一个短练习，并补充边界测试"
