from __future__ import annotations


def diagnostic_evidence(knowledge_ids: list[str]) -> list[dict]:
    return [
        {
            "knowledge_id": knowledge_ids[index % len(knowledge_ids)],
            "score": 0.45 + (index % 4) * 0.08,
            "weight": 0.85,
            "source_type": "adaptive_diagnostic",
            "source_id": f"diagnostic_q{index + 1}",
            "description": "快速诊断客观作答证据",
        }
        for index in range(10)
    ]


def planner_payload() -> dict:
    return {
        "student_profile": {
            "student_id": "student_10001",
            "grade": "grade_11",
            "school_term": "grade_11_term_1",
            "province_code": "43",
            "school_entry_year": 2024,
            "target_exam_year": 2027,
            "curriculum_versions": {"mathematics": "people_education_a"},
            "selected_subjects": ["physics", "chemistry", "biology"],
            "subject_selection_confirmed": True,
            "class_progress": {"mathematics": "PEA-E2-C05"},
        },
        "goal_text": "我数学最近92分，希望高三一模达到120分",
        "goal_deadline": "2027-05-20",
        "weekly_available_minutes": 630,
        "knowledge_evidence": [
            {
                "knowledge_id": "math_function_foundation",
                "score": 0.45,
                "weight": 0.9,
                "source_type": "mock_exam",
                "source_id": "mock_001_q1",
                "description": "函数基础题得分证据",
                "error_tags": ["concept_confusion"],
            },
            {
                "knowledge_id": "math_derivative_application",
                "score": 0.58,
                "weight": 0.9,
                "source_type": "mock_exam",
                "source_id": "mock_001_q12",
                "description": "导数应用得分证据",
            },
            {
                "knowledge_id": "math_analytic_geometry",
                "score": 0.62,
                "weight": 0.8,
                "source_type": "self_assessment",
                "source_id": "self_001",
                "description": "解析几何自评",
            },
        ] + diagnostic_evidence(
            [
                "math_function_foundation",
                "math_derivative_application",
                "math_analytic_geometry",
            ]
        ),
        "prerequisite_edges": [
            {
                "prerequisite": "math_function_foundation",
                "target": "math_derivative_application",
                "strength": 1.0,
            }
        ],
        "daily_capacity": [
            {
                "weekday": day,
                "available_minutes": 90,
                "preferred_period": "evening",
                "energy_coefficient": 0.9,
            }
            for day in range(1, 8)
        ],
        "subject_factors": {
            "mathematics": {"goal_priority": 1, "score_gap": 1, "urgency": 0.8},
            "physics": {"goal_priority": 0.5, "score_gap": 0.6},
        },
        "plan_start": "2026-07-30",
    }



class FakeStructuredDiagnosticGenerator:
    """Deterministic model boundary for the ten-item diagnostic API tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return True

    async def generate(self, context: dict):
        import json

        from ai_education.llm.diagnostic_generator import (
            DiagnosticQuestionDraft,
            DiagnosticQuestionSet,
        )

        self.calls.append(context)
        slots = json.loads(context["slot_blueprint"])
        sources = json.loads(context["knowledge_sources"])
        return DiagnosticQuestionSet(
            questions=[
                DiagnosticQuestionDraft(
                    slot_id=slot["slot_id"],
                    knowledge_focus=(
                        f"{slot['scope_label']} · {slot['dimension']}"
                    ),
                    scope_id=slot["scope_id"],
                    scope_label=slot["scope_label"],
                    source_chunk_id=next(
                        item["source_id"]
                        for item in sources
                        if item["scope_id"] == slot["scope_id"]
                    ),
                    source_excerpt=next(
                        item["content"][:120]
                        for item in sources
                        if item["scope_id"] == slot["scope_id"]
                    ),
                    dimension=slot["dimension"],
                    difficulty=0.35 + index * 0.04,
                    prompt=f"诊断题 {index + 1}：请选择最合理的一项。",
                    options=["选项 A", "选项 B", "选项 C", "选项 D"],
                    correct_option=index % 4,
                    explanation="依据当前章节知识进行判断。",
                    expected_seconds=60,
                )
                for index, slot in enumerate(slots)
            ]
        )


class FakeStructuredHomeworkTutor:
    """Deterministic test double proving that every reply goes through the model boundary."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return True

    async def generate(self, payload: dict, *, image_data_urls: list[str] | None = None):
        from ai_education.domain.enums import Subject
        from ai_education.llm.homework_tutor import TutorCandidate
        from ai_education.prompts.homework import SUBJECT_POLICIES
        from ai_education.services.homework_feedback import content_feedback

        self.calls.append({"payload": payload, "image_count": len(image_data_urls or [])})
        subject = next(
            (
                item
                for item, policy in SUBJECT_POLICIES.items()
                if policy == payload["subject_policy"]
            ),
            Subject.MATHEMATICS,
        )
        message = payload["student_message"]
        question = payload["question"]
        work = payload["student_work"] if payload["student_work"] != "尚未作答" else ""
        feedback = content_feedback(subject, question, f"{work} {message}")
        task = payload["task_type"]
        action = payload["requested_action"]
        if task == "general_chat":
            acknowledgement = "你好，我是测试中的自然语言辅导老师。"
            guidance = "我可以自然交流，也可以结合知识库帮助你分析文字或图片题目。"
            next_question = "你今天想聊什么？"
        elif task == "knowledge_question":
            acknowledgement = f"这个问题问得很好：{message}"
            guidance = f"{feedback.concept}{feedback.method}"
            next_question = feedback.next_prompt
        elif task == "direct_answer_safety_guidance":
            acknowledgement = "我不能直接给可抄写答案，但可以带你理解关键步骤。"
            guidance = f"{feedback.topic}：{feedback.method}"
            next_question = feedback.next_prompt
        elif task == "student_step_check":
            acknowledgement = f"你当前写的是：{work}"
            guidance = f"{feedback.topic}：重点检查{feedback.checkpoint}。"
            next_question = feedback.next_prompt
        elif image_data_urls:
            acknowledgement = f"我结合原图识别并分析了题目：{question}"
            guidance = f"{feedback.topic}：{feedback.method}"
            next_question = feedback.next_prompt
        else:
            acknowledgement = f"我们来具体分析这道题：{question}"
            guidance = f"{feedback.topic}：{feedback.method}"
            next_question = feedback.next_prompt
        return TutorCandidate(
            action=action,
            student_visible_content={
                "acknowledgement": acknowledgement,
                "guidance": guidance,
                "question_to_student": next_question,
                "warning": "",
            },
            verification=(
                {"result": "model_review", "issues": [], "next_action": "check_step"}
                if task == "completed_answer_review"
                else {}
            ),
            confidence=0.91,
        )


class FakeStructuredPlanNarrator:
    """Test double proving that planner explanations cross the model boundary."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return True

    async def explain(self, plan_context: dict):
        from ai_education.llm.plan_narrator import PlanNarrative

        self.calls.append(plan_context)
        tasks = plan_context["plan"]["tasks"]
        return PlanNarrative(
            student="这是模型结合当前目标、薄弱证据和可用时间生成的个性化规划说明。",
            teacher="这是模型生成的教师版证据与约束说明。",
            strategy="先修复薄弱基础，再做限时训练，并根据完成证据调整。",
            task_rationales=[
                {
                    "task_id": task["task_id"],
                    "rationale": "模型根据该任务的知识状态安排：" + task["task_type"],
                }
                for task in tasks
            ],
        )


class FakeStructuredDiagnosisReporter:
    """Model boundary test double for evidence-grounded diagnosis reports."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return True

    async def generate(self, diagnosis_context: dict):
        from ai_education.llm.diagnosis_reporter import DiagnosisNarrative

        self.calls.append(diagnosis_context)
        gate = diagnosis_context["state"]["evidence_gate"]
        return DiagnosisNarrative(
            student_summary=f"模型已根据 {gate['valid_evidence_count']} 条有效证据解释当前学情。",
            teacher_summary="模型已区分观察事实、稳定模式与待验证原因假设。",
            evidence_boundary=gate["allowed_conclusion"],
            next_evidence_request="请按缺失证据清单补充独立测次和不同题型。",
        )


class FakeStructuredExamGrader:
    """Deterministic multimodal grader for source-answer integration tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return True

    async def grade(self, *, question, answer, image_data_urls, ocr_text=""):
        from ai_education.llm.exam_grader import (
            ConstructedResponseGrade,
            GradingCriterion,
        )

        self.calls.append({
            "question_id": question["question_id"],
            "source_answer": answer["standard_answer_text"],
            "image_count": len(image_data_urls),
        })
        maximum = float(answer["max_score"])
        return ConstructedResponseGrade(
            recognized_student_work="学生写出了一个可核验的中间步骤。",
            score=maximum * 0.6,
            max_score=maximum,
            criteria=[GradingCriterion(
                criterion="按来源答案核对关键步骤",
                awarded=maximum * 0.6,
                possible=maximum,
                evidence="上传图片中存在对应步骤",
            )],
            strengths=["关键方向正确"],
            issues=["论证尚不完整"],
            feedback="关键方向有依据，下一步需要补全推导。",
            confidence=0.91,
            image_is_legible=True,
            requires_manual_review=False,
        )
