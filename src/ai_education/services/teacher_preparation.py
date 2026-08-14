"""Deterministic orchestration and quality gates for teacher lesson preparation."""

from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from typing import Any

from ai_education.core.errors import DataConflictError, InputValidationError
from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import utc_now
from ai_education.domain.teacher_preparation import (
    AlignmentRow,
    AssessmentItem,
    BoardPlan,
    DifferentiationLayer,
    LearningObjective,
    LessonPlanStatus,
    LessonPlanVersion,
    LessonQualityReport,
    LessonType,
    PostLessonFeedback,
    QualityIssue,
    TeachingActivity,
    TeachingContext,
    TeachingResourceReference,
)
from ai_education.llm.teacher_preparation import (
    GeneratedActivity,
    GeneratedAssessment,
    GeneratedBoard,
    GeneratedDifferentiation,
    GeneratedLessonContent,
    GeneratedObjective,
    StructuredTeacherPreparationGenerator,
)
from ai_education.services.teacher_preparation_knowledge import TeachingKnowledgeBase
from ai_education.teacher_preparation_repository import TeacherPreparationRepository

TEACHER_GENERATION_TIMEOUT_SECONDS = 120

LESSON_TYPE_LABELS = {
    LessonType.NEW_LESSON: "新授课",
    LessonType.REVIEW: "复习课",
    LessonType.THEMATIC_REVIEW: "专题复习课",
    LessonType.LAB: "实验课",
    LessonType.PAPER_REVIEW: "试卷讲评课",
}

SUBJECT_ABILITY_DEFAULTS = {
    Subject.CHINESE: ["语言建构与运用", "思维发展与提升"],
    Subject.MATHEMATICS: ["逻辑推理", "数学运算"],
    Subject.FOREIGN_LANGUAGE: ["语言能力", "学习能力"],
    Subject.PHYSICS: ["科学思维", "科学探究"],
    Subject.CHEMISTRY: ["证据推理与模型认知", "科学探究与创新意识"],
    Subject.BIOLOGY: ["科学思维", "生命观念"],
    Subject.IDEOLOGY_POLITICS: ["政治认同", "科学精神"],
    Subject.HISTORY: ["史料实证", "历史解释"],
    Subject.GEOGRAPHY: ["综合思维", "地理实践力"],
}


class TeacherPreparationService:
    def __init__(
        self,
        repository: TeacherPreparationRepository,
        knowledge_base: TeachingKnowledgeBase,
        generator: StructuredTeacherPreparationGenerator,
        *,
        model_name: str = "",
    ) -> None:
        self.repository = repository
        self.knowledge_base = knowledge_base
        self.generator = generator
        self.model_name = model_name or "unavailable"

    @staticmethod
    def aggregate_class_diagnosis(members: list[dict[str, Any]]) -> dict[str, Any]:
        """Return anonymous class-level patterns without names, accounts or raw responses."""

        weak_points: Counter[str] = Counter()
        error_patterns: Counter[str] = Counter()
        diagnosed = 0
        support_needed = 0
        advanced = 0
        versions: list[int] = []
        for member in members:
            diagnosis = member.get("latest_diagnosis")
            if not isinstance(diagnosis, dict):
                continue
            diagnosed += 1
            versions.append(int(diagnosis.get("state_version") or 0))
            weak_for_student = False
            states = diagnosis.get("knowledge_states") or []
            for state in states:
                if state.get("mastery_level") in {"needs_support", "developing"}:
                    label = str(state.get("dimension_label") or state.get("dimension_id") or "")
                    if label:
                        weak_points[label] += 1
                        weak_for_student = True
            for pattern in diagnosis.get("stable_error_patterns") or []:
                label = str(
                    pattern.get("description")
                    or pattern.get("error_tag")
                    or pattern.get("pattern_id")
                    or ""
                )
                if label:
                    error_patterns[label] += 1
            if weak_for_student:
                support_needed += 1
            elif diagnosis.get("diagnosis_status") == "stable":
                advanced += 1
        denominator = max(diagnosed, 1)
        common_weak_points = [
            {
                "knowledge_label": label,
                "affected_student_ratio": round(count / denominator, 3),
                "observed_student_count": count,
            }
            for label, count in weak_points.most_common(8)
        ]
        return {
            "diagnosis_version": f"class_diag_v{max(versions, default=0)}",
            "class_student_count": len(members),
            "diagnosed_student_count": diagnosed,
            "coverage_ratio": round(diagnosed / max(len(members), 1), 3),
            "common_weak_points": common_weak_points,
            "common_error_patterns": [
                {
                    "error_label": label,
                    "affected_student_ratio": round(count / denominator, 3),
                }
                for label, count in error_patterns.most_common(8)
            ],
            "group_profiles": [
                {
                    "group_id": "support_needed",
                    "ratio": round(support_needed / denominator, 3),
                    "recommended_support": ["步骤模板", "示例对照", "即时反馈"],
                },
                {
                    "group_id": "core",
                    "ratio": round(max(0, diagnosed - support_needed - advanced) / denominator, 3),
                    "recommended_support": ["核心任务", "同伴互证"],
                },
                {
                    "group_id": "advanced",
                    "ratio": round(advanced / denominator, 3),
                    "recommended_support": ["迁移任务", "开放解释"],
                },
            ],
            "privacy_mode": "anonymous_aggregate_only",
            "adaptation_available": diagnosed > 0,
        }

    def build_context(self, teacher_id: str, payload: dict[str, Any]) -> TeachingContext:
        classroom = payload.get("classroom") or {}
        if not classroom or int(classroom.get("id") or 0) != int(payload["classroom_id"]):
            raise InputValidationError("缺少已授权的班级上下文")
        requested_subject = Subject(payload["subject"])
        classroom_subject = classroom.get("subject")
        if classroom_subject and classroom_subject != requested_subject.value:
            raise InputValidationError("备课学科必须与班级主要学科一致")
        diagnosis = payload.get("diagnosis_summary") or {}
        duration = int(payload.get("duration_minutes", 45))
        buffer_minutes = max(2, min(8, round(duration * 0.07)))
        return TeachingContext(
            teacher_id=teacher_id,
            classroom_id=int(classroom["id"]),
            grade=Grade(classroom["grade"]),
            subject=requested_subject,
            lesson_type=LessonType(payload.get("lesson_type", LessonType.NEW_LESSON)),
            topic=payload["topic"],
            lesson_request=payload["lesson_request"],
            lesson_count=int(payload.get("lesson_count", 1)),
            duration_minutes=duration,
            buffer_minutes=buffer_minutes,
            teaching_stage=payload.get("teaching_stage", "日常教学"),
            textbook_version=payload.get("textbook_version", "教师指定教材"),
            exam_year=int(payload.get("exam_year", 2027)),
            exam_blueprint_version=(
                f"{requested_subject.value}_national_v1_{payload.get('exam_year', 2027)}"
            ),
            class_size=int(classroom.get("student_count") or 0),
            available_equipment=payload.get("available_equipment") or [],
            diagnosis_summary=diagnosis,
            diagnosis_adapted=bool(diagnosis.get("adaptation_available")),
        )

    async def create_plan(
        self,
        *,
        teacher_id: str,
        payload: dict[str, Any],
    ) -> LessonPlanVersion:
        context = self.build_context(teacher_id, payload)
        resources = self.knowledge_base.search(
            f"{context.topic} {context.lesson_request}",
            subject=context.subject,
            limit=3,
        )
        generated, generation_mode, generation_issue = await self._generate(
            context=context,
            resources=resources,
            homework_limit=int(payload.get("homework_time_limit_minutes", 25)),
        )
        return self.repository.save_version(
            self._assemble_plan(
                context=context,
                generated=generated,
                resources=resources,
                generation_mode=generation_mode,
                generation_issue=generation_issue,
            )
        )

    async def revise_plan(
        self,
        *,
        teacher_id: str,
        lesson_plan_id: str,
        payload: dict[str, Any],
    ) -> LessonPlanVersion:
        current = self.repository.get(lesson_plan_id, teacher_id)
        expected = int(payload["expected_version"])
        if current.version != expected:
            raise DataConflictError(
                "备课方案版本已更新，请刷新后重试",
                details={"current_version": current.version, "expected_version": expected},
            )
        locked = list(
            dict.fromkeys(
                [*current.locked_component_ids, *(payload.get("locked_component_ids") or [])]
            )
        )
        generated, generation_mode, generation_issue = await self._generate(
            context=current.context,
            resources=current.resources,
            homework_limit=25,
            revision_context={
                "component": payload.get("component", "full"),
                "revision_request": payload["revision_request"],
                "locked_component_ids": locked,
                "output_requirement": (
                    "必须返回一份字段齐全、可直接用于课堂的完整教案，不能只返回改动摘要、"
                    "差异片段或省略号。未修订部分也要完整保留；修订后的目标、活动、板书、"
                    "评价、分层支持和应急路径的细节量不得低于当前版本。"
                ),
                "current_plan": current.model_dump(
                    mode="json", exclude={"resources", "alignment_matrix", "quality_report"}
                ),
            },
        )
        candidate = self._assemble_plan(
            context=current.context,
            generated=generated,
            resources=current.resources,
            generation_mode=generation_mode,
            generation_issue=generation_issue,
            lesson_plan_id=current.lesson_plan_id,
            version=current.version + 1,
            parent_version=current.version,
            locked_component_ids=locked,
            change_summary=[
                f"局部修订 {payload.get('component', 'full')}：{payload['revision_request']}"
            ],
            revision_prompt=payload["revision_request"],
            revision_component=payload.get("component", "full"),
            revision_locked_component_ids=locked,
        )
        merged = self._merge_revision(
            current=current,
            candidate=candidate,
            component=payload.get("component", "full"),
            locked=locked,
        )
        return self.repository.save_version(merged)

    def rollback_plan(
        self,
        *,
        teacher_id: str,
        lesson_plan_id: str,
        expected_version: int,
        target_version: int,
    ) -> LessonPlanVersion:
        current = self.repository.get(lesson_plan_id, teacher_id)
        if current.version != expected_version:
            raise DataConflictError(
                "备课方案版本已更新，请刷新后重试",
                details={
                    "current_version": current.version,
                    "expected_version": expected_version,
                },
            )
        if current.status not in {
            LessonPlanStatus.DRAFT,
            LessonPlanStatus.TEACHER_REVIEW,
        }:
            raise InputValidationError("只有待审核方案可以回退历史版本")
        if target_version >= current.version:
            raise InputValidationError("只能回退到早于当前版本的历史版本")
        target = self.repository.get(lesson_plan_id, teacher_id, target_version)
        restored = target.model_copy(
            update={
                "version": current.version + 1,
                "parent_version": current.version,
                "status": LessonPlanStatus.TEACHER_REVIEW,
                "approved_by": None,
                "approved_at": None,
                "published_at": None,
                "created_at": utc_now(),
                "change_summary": [f"从第 {current.version} 版回退至第 {target_version} 版内容"],
                "revision_prompt": None,
                "revision_component": None,
                "revision_locked_component_ids": [],
            }
        )
        return self.repository.save_version(restored)

    def transition(
        self,
        *,
        teacher_id: str,
        lesson_plan_id: str,
        expected_version: int,
        action: str,
        note: str = "",
    ) -> LessonPlanVersion:
        current = self.repository.get(lesson_plan_id, teacher_id)
        if current.version != expected_version:
            raise DataConflictError(
                "备课方案版本已更新，请刷新后重试",
                details={"current_version": current.version, "expected_version": expected_version},
            )
        if action == "approve":
            if current.status not in {LessonPlanStatus.TEACHER_REVIEW, LessonPlanStatus.DRAFT}:
                raise InputValidationError("只有待教师审核的方案可以批准")
            if (
                current.quality_report.alignment_status != "pass"
                or current.quality_report.feasibility_status != "pass"
                or current.quality_report.resource_compliance_status == "fail"
            ):
                raise InputValidationError("方案未通过一致性、课时或资源门控，不能批准")
            status = LessonPlanStatus.APPROVED
            approved_by = teacher_id
            approved_at = utc_now()
            published_at = None
            summary = "教师批准备课方案"
        elif action == "publish":
            if current.status != LessonPlanStatus.APPROVED:
                raise InputValidationError("只有教师已批准的方案可以发布")
            status = LessonPlanStatus.PUBLISHED
            approved_by = current.approved_by
            approved_at = current.approved_at
            published_at = utc_now()
            summary = "教师发布正式教案与评价蓝图"
        else:
            raise InputValidationError(f"不支持的备课状态操作：{action}")
        if note.strip():
            summary += f"：{note.strip()}"
        return self.repository.save_version(
            current.model_copy(
                update={
                    "version": current.version + 1,
                    "parent_version": current.version,
                    "status": status,
                    "approved_by": approved_by,
                    "approved_at": approved_at,
                    "published_at": published_at,
                    "change_summary": [summary],
                    "revision_prompt": None,
                    "revision_component": None,
                    "revision_locked_component_ids": [],
                }
            )
        )

    def record_feedback(
        self,
        *,
        teacher_id: str,
        lesson_plan_id: str,
        payload: dict[str, Any],
    ) -> tuple[PostLessonFeedback, LessonPlanVersion]:
        feedback = PostLessonFeedback(
            lesson_plan_id=lesson_plan_id,
            teacher_id=teacher_id,
            lesson_version=int(payload["lesson_version"]),
            actual_duration_minutes=int(payload["actual_duration_minutes"]),
            completed_activity_ids=payload.get("completed_activity_ids") or [],
            skipped_activity_ids=payload.get("skipped_activity_ids") or [],
            class_check_accuracy=payload.get("class_check_accuracy"),
            teacher_rating=int(payload["teacher_rating"]),
            effective_components=payload.get("effective_components") or [],
            issues=payload.get("issues") or [],
            teacher_notes=payload.get("teacher_notes", ""),
        )
        saved = self.repository.save_feedback(feedback)
        current = self.repository.get(lesson_plan_id, teacher_id)
        updated = self.repository.save_version(
            current.model_copy(
                update={
                    "version": current.version + 1,
                    "parent_version": current.version,
                    "status": LessonPlanStatus.FEEDBACK_RECORDED,
                    "change_summary": [
                        (
                            f"记录授课反馈：评分 {feedback.teacher_rating}/5，"
                            f"实际 {feedback.actual_duration_minutes} 分钟"
                        )
                    ],
                    "revision_prompt": None,
                    "revision_component": None,
                    "revision_locked_component_ids": [],
                }
            )
        )
        return saved, updated

    async def _generate(
        self,
        *,
        context: TeachingContext,
        resources: list[TeachingResourceReference],
        homework_limit: int,
        revision_context: dict[str, Any] | None = None,
    ) -> tuple[GeneratedLessonContent, str, bool]:
        resource_payload = [
            item.model_dump(mode="json", exclude={"relative_path"}) for item in resources
        ]
        if self.generator.available:
            try:
                generated = await asyncio.wait_for(
                    self.generator.generate(
                        teaching_context={
                            **context.model_dump(mode="json"),
                            "homework_time_limit_minutes": homework_limit,
                        },
                        diagnosis_summary=context.diagnosis_summary,
                        resource_references=resource_payload,
                        revision_context=revision_context,
                    ),
                    timeout=TEACHER_GENERATION_TIMEOUT_SECONDS,
                )
                if generated is not None:
                    return generated, "llm", False
            except Exception:
                pass
        return self._fallback_content(context, resources), "reference_template", True

    def _fallback_content(
        self,
        context: TeachingContext,
        resources: list[TeachingResourceReference],
    ) -> GeneratedLessonContent:
        topic = context.topic
        abilities = SUBJECT_ABILITY_DEFAULTS[context.subject]
        source_title = resources[0].title if resources else "课程标准与教师指定范围"
        objectives = [
            GeneratedObjective(
                description=f"能够准确说明{topic}的核心概念、条件与适用边界",
                priority="must",
                observable_behavior=f"用自己的语言和规范学科表达完成{topic}概念卡",
                exam_ability_tags=abilities,
            ),
            GeneratedObjective(
                description=f"能够运用{topic}解决一个典型课堂任务并解释关键依据",
                priority="must",
                observable_behavior="独立完成任务、标出关键步骤并接受同伴核验",
                exam_ability_tags=abilities,
            ),
            GeneratedObjective(
                description=f"能够识别{topic}中的常见错误并迁移到新情境",
                priority="recommended",
                observable_behavior="比较正反例并写出一条可复用的判断规则",
                exam_ability_tags=abilities,
            ),
        ]
        durations = self._stage_durations(context.duration_minutes - context.buffer_minutes, 5)
        activities = [
            GeneratedActivity(
                stage="诊断导入",
                duration_minutes=durations[0],
                objective_indexes=[1],
                teacher_action=f"呈现与{topic}相关的真实问题或易错样例，收集初始判断",
                student_action="独立作答并用一句话说明依据，再与同伴核对差异",
                organization="个人思考+同伴互证",
                expected_output="初始判断与理由",
                assessment_method="快速投票、随机追问与理由采样",
                decision_rule="错误率超过40%时先补偿前置概念",
            ),
            GeneratedActivity(
                stage="证据研读",
                duration_minutes=durations[1],
                objective_indexes=[1],
                teacher_action=f"依据《{source_title}》的教学结构组织概念、例证与反例",
                student_action="提取关键信息，完成概念—条件—证据三栏表",
                organization="个人阅读+全班核验",
                expected_output="概念证据表",
                assessment_method="表格要素核对",
                decision_rule="关键条件遗漏时追加反例辨析",
            ),
            GeneratedActivity(
                stage="核心探究",
                duration_minutes=durations[2],
                objective_indexes=[1, 2],
                teacher_action="分步释放核心任务，巡视并追问结论所依据的证据",
                student_action="小组完成任务、形成可展示作品并标出关键推理步骤",
                organization="四人小组+代表展示",
                expected_output="结构化解题或解释作品",
                assessment_method="目标对照量规+同伴质询",
                decision_rule="完成率低于60%时提供步骤支架并减少展示组数",
            ),
            GeneratedActivity(
                stage="变式应用",
                duration_minutes=durations[3],
                objective_indexes=[2, 3],
                teacher_action="提供条件变化的变式任务，比较不同路径的适用边界",
                student_action="独立迁移后与同伴互评，修正不完整表达",
                organization="个人练习+同伴互评",
                expected_output="变式答案与纠错记录",
                assessment_method="课堂检测与错因标签",
                decision_rule="正确率低于60%进入补讲，高于85%进入拓展任务",
            ),
            GeneratedActivity(
                stage="总结评价",
                duration_minutes=durations[4],
                objective_indexes=[1, 2, 3],
                teacher_action="回扣目标，组织学生用证据说明本课达成情况",
                student_action="完成出口条并写出仍需解决的一个问题",
                organization="个人反思+全班归纳",
                expected_output="出口条与个人待办",
                assessment_method="目标达成自评与教师抽检",
                decision_rule="依据出口条确定下一课补偿任务",
            ),
        ]
        safety = self._subject_safety_note(context.subject)
        return GeneratedLessonContent(
            title=f"{topic}｜{LESSON_TYPE_LABELS[context.lesson_type]}教学设计",
            summary=(
                f"围绕{topic}建立目标—活动—评价闭环，参考三份同学科优秀教案的结构，"
                f"在{context.duration_minutes}分钟内完成诊断、探究、迁移与评价。{safety}"
            ),
            key_points=[f"{topic}的核心概念与适用条件", "从证据到结论的规范表达"],
            difficult_points=[f"{topic}在变式情境中的迁移", "常见错误的识别与纠正"],
            objectives=objectives,
            activities=activities,
            board_plan=GeneratedBoard(
                layout={
                    "左侧": "核心问题、已有判断与前置知识",
                    "中部": f"{topic}概念结构、主流程与关键证据",
                    "右侧": "易错点、评价结论与迁移规则",
                },
                timeline=[
                    "导入后保留核心问题",
                    "探究时逐步生成主流程",
                    "变式后补充易错点",
                    "总结时形成迁移规则",
                ],
                persistent_content=[f"{topic}核心结构", "判断或解决流程", "易错点与边界"],
                slide_only_content=["长材料、完整任务情境和学生作品"],
                compact_version=[f"{topic}核心概念", "三步解决流程", "一个典型易错点"],
                estimated_writing_minutes=min(10, max(4, context.duration_minutes // 6)),
            ),
            assessments=[
                GeneratedAssessment(
                    objective_indexes=[1],
                    purpose="in_class_check",
                    prompt=f"用规范学科语言说明{topic}的核心条件，并给出一个反例或边界。",
                    answer_outline="包含核心概念、成立条件、边界说明和对应证据。",
                    scoring_rubric=["概念准确", "条件完整", "证据与结论对应"],
                    difficulty=0.45,
                    knowledge_tags=[topic],
                    ability_tags=abilities,
                    common_error_tags=["概念边界遗漏", "证据不足"],
                    decision_rule="正确率低于60%时回到证据研读环节",
                ),
                GeneratedAssessment(
                    objective_indexes=[2],
                    purpose="in_class_check",
                    prompt=f"解决一个{topic}典型任务，并标出关键步骤或证据链。",
                    answer_outline="任务结论正确，步骤完整，关键依据明确。",
                    scoring_rubric=["结论正确", "过程完整", "表达规范"],
                    difficulty=0.58,
                    knowledge_tags=[topic],
                    ability_tags=abilities,
                    common_error_tags=["关键步骤遗漏", "表达不规范"],
                    decision_rule="错误集中时使用步骤支架重新作答",
                ),
                GeneratedAssessment(
                    objective_indexes=[1, 2],
                    purpose="homework",
                    prompt=f"完成一项{topic}基础巩固任务，并解释所用规则。",
                    answer_outline="准确使用本课核心规则并说明理由。",
                    scoring_rubric=["规则选择", "过程证据", "结论"],
                    difficulty=0.5,
                    knowledge_tags=[topic],
                    ability_tags=abilities,
                    common_error_tags=["规则误用"],
                ),
                GeneratedAssessment(
                    objective_indexes=[2, 3],
                    purpose="homework",
                    prompt=f"在条件变化的新情境中迁移{topic}方法，并比较与课堂任务的异同。",
                    answer_outline="识别变化条件，迁移方法，说明相同点与限制。",
                    scoring_rubric=["条件识别", "迁移过程", "边界反思"],
                    difficulty=0.72,
                    knowledge_tags=[topic],
                    ability_tags=abilities,
                    common_error_tags=["忽略条件变化", "迁移结论过度"],
                ),
            ],
            differentiation_plan=[
                GeneratedDifferentiation(
                    layer_id="support",
                    target_profile="当前证据显示需要更多步骤支架的学生",
                    task_adjustment="保持核心目标，减少同时处理的信息量并增加一次即时反馈",
                    scaffolds=["步骤模板", "正反例对照", "关键词提示"],
                    objective_indexes=[1, 2],
                ),
                GeneratedDifferentiation(
                    layer_id="core",
                    target_profile="已具备前置知识、需要稳定完成核心任务的学生",
                    task_adjustment="完成标准课堂任务并用评价量规自检",
                    scaffolds=["目标核对表"],
                    objective_indexes=[1, 2, 3],
                ),
                GeneratedDifferentiation(
                    layer_id="advanced",
                    target_profile="核心任务稳定、需要增加迁移深度的学生",
                    task_adjustment="增加开放条件或多路径比较，不提前提供步骤",
                    scaffolds=[],
                    objective_indexes=[2, 3],
                ),
            ],
            contingency_paths=[
                "核心探究超时：减少展示组数，保留核心检测并将第二个变式移至课后",
                "设备故障：使用打印材料、板书和口头任务替代电子展示",
                "前置知识不足：启用5分钟补偿任务并取消非必达拓展环节",
            ],
        )

    @staticmethod
    def _stage_durations(available: int, count: int) -> list[int]:
        weights = [0.12, 0.18, 0.32, 0.24, 0.14][:count]
        durations = [max(1, round(available * weight)) for weight in weights]
        while sum(durations) > available:
            index = max(range(len(durations)), key=durations.__getitem__)
            if durations[index] <= 1:
                break
            durations[index] -= 1
        while sum(durations) < available:
            durations[2 if len(durations) > 2 else 0] += 1
        return durations

    @staticmethod
    def _subject_safety_note(subject: Subject) -> str:
        if subject == Subject.CHEMISTRY:
            return "涉及实验时必须由教师核对药品、通风、防护和废液处置条件。"
        if subject == Subject.BIOLOGY:
            return "健康与生理案例仅用于教学，不形成个体诊断。"
        if subject == Subject.IDEOLOGY_POLITICS:
            return "现实议题数据作为教学化材料，授课前必须核验时效和正式来源。"
        return "所有材料需由教师结合本校教材进度和课堂条件最终确认。"

    def _assemble_plan(
        self,
        *,
        context: TeachingContext,
        generated: GeneratedLessonContent,
        resources: list[TeachingResourceReference],
        generation_mode: str,
        generation_issue: bool,
        lesson_plan_id: str | None = None,
        version: int = 1,
        parent_version: int | None = None,
        locked_component_ids: list[str] | None = None,
        change_summary: list[str] | None = None,
        revision_prompt: str | None = None,
        revision_component: str | None = None,
        revision_locked_component_ids: list[str] | None = None,
    ) -> LessonPlanVersion:
        objective_ids = [f"obj_{index}" for index in range(1, len(generated.objectives) + 1)]
        source_ids = [item.resource_id for item in resources]
        objectives = [
            LearningObjective(
                objective_id=objective_ids[index - 1],
                description=item.description,
                priority=item.priority,
                observable_behavior=item.observable_behavior,
                exam_ability_tags=item.exam_ability_tags,
                source_ref_ids=source_ids,
            )
            for index, item in enumerate(generated.objectives, start=1)
        ]
        activities = []
        fitted_durations = self._fit_activity_times(
            [item.duration_minutes for item in generated.activities],
            context.duration_minutes - context.buffer_minutes,
        )
        for index, item in enumerate(generated.activities, start=1):
            activities.append(
                TeachingActivity(
                    activity_id=f"act_{index}",
                    stage=item.stage,
                    duration_minutes=fitted_durations[index - 1],
                    objective_ids=self._objective_ids(item.objective_indexes, objective_ids),
                    teacher_action=item.teacher_action,
                    student_action=item.student_action,
                    organization=item.organization,
                    expected_output=item.expected_output,
                    assessment_method=item.assessment_method,
                    decision_rule=item.decision_rule,
                )
            )
        assessments = []
        counters = {"in_class_check": 0, "homework": 0}
        for item in generated.assessments:
            counters[item.purpose] += 1
            prefix = "check" if item.purpose == "in_class_check" else "home"
            assessments.append(
                AssessmentItem(
                    question_id=f"q_{prefix}_{counters[item.purpose]}",
                    objective_ids=self._objective_ids(item.objective_indexes, objective_ids),
                    purpose=item.purpose,
                    prompt=item.prompt,
                    answer_outline=item.answer_outline,
                    scoring_rubric=item.scoring_rubric,
                    difficulty=item.difficulty,
                    knowledge_tags=item.knowledge_tags,
                    ability_tags=item.ability_tags,
                    common_error_tags=item.common_error_tags,
                    decision_rule=item.decision_rule,
                )
            )
        differentiation = [
            DifferentiationLayer(
                layer_id=item.layer_id,
                target_profile=item.target_profile,
                task_adjustment=item.task_adjustment,
                scaffolds=item.scaffolds,
                objective_ids=self._objective_ids(item.objective_indexes, objective_ids),
            )
            for item in generated.differentiation_plan
        ]
        board = BoardPlan(**generated.board_plan.model_dump())
        alignment = self._alignment(objectives, activities, assessments, board, context)
        quality = self._quality_report(
            context=context,
            alignment=alignment,
            activities=activities,
            resources=resources,
            generation_issue=generation_issue,
        )
        payload = {
            "version": version,
            "parent_version": parent_version,
            "status": LessonPlanStatus.TEACHER_REVIEW,
            "context": context,
            "title": generated.title,
            "summary": generated.summary,
            "key_points": generated.key_points,
            "difficult_points": generated.difficult_points,
            "objectives": objectives,
            "activities": activities,
            "resources": resources,
            "board_plan": board,
            "assessments": assessments,
            "differentiation_plan": differentiation,
            "contingency_paths": generated.contingency_paths,
            "alignment_matrix": alignment,
            "quality_report": quality,
            "locked_component_ids": locked_component_ids or [],
            "change_summary": change_summary or ["生成教师备课候选方案"],
            "revision_prompt": revision_prompt,
            "revision_component": revision_component,
            "revision_locked_component_ids": revision_locked_component_ids or [],
            "generation_mode": generation_mode,
            "source_versions": {
                "curriculum": context.curriculum_version,
                "textbook": context.textbook_version,
                "exam_blueprint": context.exam_blueprint_version,
                "class_diagnosis": str(
                    context.diagnosis_summary.get("diagnosis_version", "unavailable")
                ),
                "teaching_resource_collection": "v3",
            },
            "model_versions": {
                "generator": (
                    self.model_name if generation_mode == "llm" else "reference_template_v1"
                ),
                "validator": "teacher_preparation_rules_v1",
            },
        }
        if lesson_plan_id:
            payload["lesson_plan_id"] = lesson_plan_id
        return LessonPlanVersion.model_validate(payload)

    @staticmethod
    def _objective_ids(indexes: list[int], objective_ids: list[str]) -> list[str]:
        valid = [objective_ids[index - 1] for index in indexes if 1 <= index <= len(objective_ids)]
        return list(dict.fromkeys(valid)) or [objective_ids[0]]

    @staticmethod
    def _fit_activity_times(durations: list[int], available: int) -> list[int]:
        fitted = [max(1, value) for value in durations]
        while sum(fitted) > available:
            index = max(range(len(fitted)), key=fitted.__getitem__)
            if fitted[index] <= 1:
                break
            fitted[index] -= 1
        return fitted

    @staticmethod
    def _alignment(
        objectives: list[LearningObjective],
        activities: list[TeachingActivity],
        assessments: list[AssessmentItem],
        board: BoardPlan,
        context: TeachingContext,
    ) -> list[AlignmentRow]:
        rows = []
        for objective in objectives:
            activity_ids = [
                item.activity_id
                for item in activities
                if objective.objective_id in item.objective_ids
            ]
            assessment_ids = [
                item.question_id
                for item in assessments
                if objective.objective_id in item.objective_ids
            ]
            passed = bool(
                activity_ids
                and assessment_ids
                and objective.source_ref_ids
                and board.persistent_content
            )
            rows.append(
                AlignmentRow(
                    objective_id=objective.objective_id,
                    objective_description=objective.description,
                    source_ref_ids=objective.source_ref_ids,
                    ability_tags=objective.exam_ability_tags,
                    activity_ids=activity_ids,
                    board_evidence=board.persistent_content[:3],
                    assessment_ids=assessment_ids,
                    diagnosis_adaptation=(
                        "使用班级匿名聚合学情调整支架与难度"
                        if context.diagnosis_adapted
                        else "未进行学情适配，采用通用课程方案"
                    ),
                    status="pass" if passed else "fail",
                )
            )
        return rows

    def _quality_report(
        self,
        *,
        context: TeachingContext,
        alignment: list[AlignmentRow],
        activities: list[TeachingActivity],
        resources: list[TeachingResourceReference],
        generation_issue: bool,
    ) -> LessonQualityReport:
        issues: list[QualityIssue] = []
        activity_minutes = sum(item.duration_minutes for item in activities)
        feasibility = (
            "pass"
            if activity_minutes <= context.duration_minutes - context.buffer_minutes
            else "fail"
        )
        if feasibility == "fail":
            issues.append(
                QualityIssue(
                    code="LESSON_TIME_EXCEEDED",
                    severity="high",
                    message="课堂活动总时长超过扣除缓冲后的课时预算",
                    action="blocked",
                )
            )
        if context.lesson_type == LessonType.LAB and not context.available_equipment:
            issues.append(
                QualityIssue(
                    code="LAB_SETUP_TEACHER_CONFIRMATION",
                    severity="medium",
                    message="实验设备输入已从生成表单移除；实施前请教师按本校条件确认材料与安全要求",
                    action="teacher_review",
                )
            )
        alignment_status = "pass" if all(item.status == "pass" for item in alignment) else "fail"
        if alignment_status == "fail":
            issues.append(
                QualityIssue(
                    code="OBJECTIVE_ALIGNMENT_INCOMPLETE",
                    severity="high",
                    message="存在未映射课堂活动、板书或评价任务的教学目标",
                    action="blocked",
                )
            )
        if not resources:
            resource_status = "fail"
        elif all(item.checksum_verified for item in resources):
            resource_status = "pass"
        else:
            resource_status = "review_required"
        if resource_status != "pass":
            issues.append(
                QualityIssue(
                    code="RESOURCE_PROVENANCE_REVIEW",
                    severity="high" if resource_status == "fail" else "medium",
                    message="至少一项教学资源的来源或校验状态需要教师复核",
                    action="blocked" if resource_status == "fail" else "teacher_review",
                )
            )
        if not context.diagnosis_adapted:
            issues.append(
                QualityIssue(
                    code="CLASS_DIAGNOSIS_UNAVAILABLE",
                    severity="low",
                    message="当前班级缺少可用的匿名聚合学情，方案按通用课程要求生成",
                    action="teacher_review",
                )
            )
        if generation_issue:
            issues.append(
                QualityIssue(
                    code="TEACHING_LLM_UNAVAILABLE",
                    severity="medium",
                    message="大模型生成不可用，已使用优秀教案依据和确定性模板生成最小可用草稿",
                    action="teacher_review",
                )
            )
        return LessonQualityReport(
            alignment_status=alignment_status,
            feasibility_status=feasibility,
            resource_compliance_status=resource_status,
            estimated_activity_minutes=activity_minutes,
            buffer_minutes=context.buffer_minutes,
            issues=issues,
            teacher_review_required=True,
            publishable=False,
        )

    def _merge_revision(
        self,
        *,
        current: LessonPlanVersion,
        candidate: LessonPlanVersion,
        component: str,
        locked: list[str],
    ) -> LessonPlanVersion:
        updates: dict[str, Any] = {
            "version": candidate.version,
            "parent_version": candidate.parent_version,
            "status": LessonPlanStatus.TEACHER_REVIEW,
            "locked_component_ids": locked,
            "change_summary": candidate.change_summary,
            "revision_prompt": candidate.revision_prompt,
            "revision_component": candidate.revision_component,
            "revision_locked_component_ids": candidate.revision_locked_component_ids,
            "generation_mode": candidate.generation_mode,
            "model_versions": candidate.model_versions,
            "approved_by": None,
            "approved_at": None,
            "published_at": None,
            "created_at": candidate.created_at,
        }
        if component in {"full", "objectives"}:
            updates.update(
                {
                    "title": candidate.title,
                    "summary": candidate.summary,
                    "key_points": candidate.key_points,
                    "difficult_points": candidate.difficult_points,
                    "objectives": self._preserve_locked(
                        current.objectives,
                        candidate.objectives,
                        "objective_id",
                        locked,
                    ),
                }
            )
        if component in {"full", "objectives", "activities"}:
            updates["activities"] = self._preserve_locked(
                current.activities, candidate.activities, "activity_id", locked
            )
        if component in {"full", "objectives", "activities", "board"}:
            updates["board_plan"] = (
                current.board_plan if "board_1" in locked else candidate.board_plan
            )
        if component in {"full", "objectives", "assessments"}:
            updates["assessments"] = self._preserve_locked(
                current.assessments, candidate.assessments, "question_id", locked
            )
        if component in {"full", "objectives", "assessments", "differentiation"}:
            updates["differentiation_plan"] = candidate.differentiation_plan
        if component == "full":
            updates["contingency_paths"] = candidate.contingency_paths
        draft = current.model_copy(update=updates)
        alignment = self._alignment(
            draft.objectives,
            draft.activities,
            draft.assessments,
            draft.board_plan,
            draft.context,
        )
        quality = self._quality_report(
            context=draft.context,
            alignment=alignment,
            activities=draft.activities,
            resources=draft.resources,
            generation_issue=draft.generation_mode != "llm",
        )
        return draft.model_copy(update={"alignment_matrix": alignment, "quality_report": quality})

    @staticmethod
    def _preserve_locked(
        current: list[Any],
        candidate: list[Any],
        id_field: str,
        locked: list[str],
    ) -> list[Any]:
        current_by_id = {getattr(item, id_field): item for item in current}
        merged = []
        for item in candidate:
            component_id = getattr(item, id_field)
            merged.append(
                deepcopy(current_by_id[component_id])
                if component_id in locked and component_id in current_by_id
                else item
            )
        for component_id in locked:
            if component_id in current_by_id and not any(
                getattr(item, id_field) == component_id for item in merged
            ):
                merged.append(deepcopy(current_by_id[component_id]))
        return merged
