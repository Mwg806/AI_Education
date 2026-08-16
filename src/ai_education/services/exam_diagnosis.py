"""Paper catalog, secure answer-bank lookup, sessions and fair grading."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError, ModelUnavailableError
from ai_education.domain.protocols import utc_now
from ai_education.llm.exam_grader import ConstructedResponseGrade, StructuredExamGrader
from ai_education.mysql_persistence import MySQLPersistence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BANK_ROOT = PROJECT_ROOT / "Knowledge" / "Exam" / "高考真题" / "diagnose"
HTML_TAG = re.compile(r"<[^>]+>")

# The imported papers retain a broad “学科综合” tag when the source document did
# not carry a chapter label.  These conservative keyword hints refine only those
# broad tags, using the original question and the private answer analysis.  The
# analysis itself is never returned to the student.
SUBJECT_TOPIC_HINTS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "mathematics": (
        ("复数", ("复数", "共轭", "复平面")),
        ("集合与逻辑", ("命题", "充分条件", "必要条件", "集合")),
        ("统计与概率", ("频数", "中位数", "平均值", "方差", "概率", "随机变量", "正态分布")),
        ("函数与导数", ("导数", "单调性", "极值", "零点", "偶函数", "奇函数")),
        ("数列", ("数列", "等差", "等比", "递推")),
        ("三角函数", ("三角函数", "正弦", "余弦", "正切")),
        ("平面向量", ("向量", "数量积")),
        ("解析几何", ("椭圆", "双曲线", "抛物线", "圆锥曲线", "直线与圆")),
        ("排列组合", ("排列", "组合", "乘法原理", "志愿者")),
        ("立体几何", ("空间几何", "三棱锥", "四棱锥", "二面角", "线面", "所成的角")),
        ("几何相似与比例", ("平面相似", "相似建立比例", "合分比")),
    ),
    "physics": (
        ("运动学", ("匀变速", "位移", "速度时间", "加速度")),
        ("力与平衡", ("受力", "平衡", "摩擦力", "弹力")),
        ("牛顿运动定律", ("牛顿第二定律", "牛顿运动定律")),
        ("机械能与动量", ("机械能", "动能定理", "动量", "碰撞")),
        ("电场与电路", ("电场", "电势", "电容", "闭合电路", "电阻")),
        ("磁场与电磁感应", ("磁场", "洛伦兹力", "安培力", "电磁感应", "楞次")),
        ("振动与波", ("简谐运动", "振动", "波长", "机械波")),
        ("光学", ("折射", "光电效应", "干涉", "衍射")),
    ),
    "chemistry": (
        ("物质的量与化学计量", ("物质的量", "摩尔", "阿伏加德罗")),
        ("氧化还原反应", ("氧化还原", "电子转移", "化合价")),
        ("离子反应", ("离子方程式", "离子反应", "沉淀")),
        ("元素及其化合物", ("元素化合物", "无机物", "元素周期")),
        ("物质结构", ("化学键", "晶体", "分子结构", "杂化")),
        ("化学反应速率与平衡", ("化学平衡", "反应速率", "平衡常数")),
        ("电化学", ("原电池", "电解池", "电化学")),
        ("有机化学", ("有机物", "同分异构", "官能团", "烃")),
        ("化学实验", ("实验装置", "实验操作", "滴定", "分离提纯")),
    ),
    "biology": (
        ("细胞结构与代谢", ("细胞器", "细胞膜", "呼吸作用", "光合作用", "酶")),
        ("遗传与变异", ("遗传", "基因", "染色体", "孟德尔", "变异")),
        ("生命活动调节", ("激素", "神经调节", "稳态", "免疫")),
        ("生态系统", ("种群", "群落", "生态系统", "食物链")),
        ("生物技术与实验", ("实验", "PCR", "基因工程", "发酵")),
    ),
    "chinese": (
        ("论述类文本阅读", ("论述类", "论证", "观点", "信息类文本阅读")),
        ("实用类文本阅读", ("实用类", "非连续性文本", "材料一", "现代文阅读")),
        ("文学类文本阅读", ("小说", "散文", "人物形象", "叙事", "文学类文本")),
        ("文言文阅读", ("文言", "实词", "虚词", "翻译", "断句")),
        ("古代诗歌阅读", ("诗歌", "诗人", "意象", "炼字", "古代诗歌")),
        ("名篇名句默写", ("名篇名句", "补写出下列句子", "默写")),
        ("语言文字运用", ("成语", "病句", "语段", "修辞", "语言文字运用", "填写成语")),
        ("写作", ("作文", "立意", "写一篇")),
    ),
    "foreign_language": (
        ("阅读理解·细节定位", ("细节理解", "according to", "mentioned", "how many", "how much", "when did", "where did", "which of", "who is", "what do the listed")),
        ("阅读理解·主旨概括", ("主旨", "best title", "main idea", "mainly tell", "main purpose")),
        ("阅读理解·词义猜测", ("underlined", "mean in paragraph", "closest in meaning")),
        ("阅读理解·推理判断", ("推断", "infer", "imply", "suggest", "what can we say", "most likely")),
        ("阅读理解·观点态度", ("attitude", "tone of the author")),
        ("七选五衔接", ("七选五", "选项中有两项为多余选项")),
        ("完形填空", ("完形", "cloze", "从每题所给的a、b、c和d")),
        ("语法填空", ("语法填空", "grammar", "阅读下面短文，在空白处填入")),
        ("书面表达", ("写作", "write", "essay", "letter", "书面表达", "应用文")),
    ),
    "geography": (
        ("大气与气候", ("气候", "气温", "降水", "大气环流")),
        ("水循环与河流", ("河流", "径流", "水循环", "水文", "流域")),
        ("地貌与地质作用", ("地貌", "地质", "岩石", "侵蚀", "堆积")),
        ("人口与城市", ("人口", "城市化", "城镇")),
        ("农业与工业区位", ("农业", "工业", "区位", "种植", "制造业")),
        ("交通与区域联系", ("交通", "铁路", "港口", "运输")),
        ("自然灾害", ("灾害", "洪涝", "干旱", "滑坡", "泥石流")),
        ("海洋地理", ("海水", "洋流", "海岸", "海洋")),
        ("区域发展与环境", ("区域发展", "生态环境", "可持续", "区域协调")),
    ),
    "history": (
        ("中国古代史", ("春秋战国", "秦汉", "魏晋", "唐朝", "宋代", "元朝", "明清", "古代中国", "新石器")),
        ("中国近现代史", ("晚清", "近代中国", "洋务", "新军", "辛亥", "民国", "抗日", "新中国", "改革开放")),
        ("世界古代史", ("古希腊", "古罗马", "中世纪")),
        ("世界近现代史", ("新航路", "航海活动", "工业革命", "俄国", "十月革命", "世界大战", "冷战", "资本主义", "布雷顿森林", "殖民")),
        ("民族解放与国家独立", ("民族独立", "民族解放", "反殖民", "非洲")),
        ("史料实证", ("史料", "材料反映", "历史解释", "史学")),
    ),
    "ideology_politics": (
        ("经济与社会", ("市场经济", "企业", "宏观调控", "收入分配")),
        ("政治与法治", ("依法治国", "人民代表大会", "政府", "民主")),
        ("哲学与文化", ("哲学", "矛盾", "实践", "认识", "文化")),
        ("当代国际政治与经济", ("国际关系", "经济全球化", "联合国")),
        ("法律与生活", ("民法", "合同", "侵权", "诉讼")),
    ),
    "technology": (
        ("信息系统与数据", ("数据", "数据库", "信息系统", "数据表")),
        ("算法与程序设计", ("算法", "程序", "循环", "变量", "流程图")),
        ("网络与信息安全", ("网络", "信息安全", "加密")),
        ("技术设计", ("设计方案", "技术试验", "结构", "流程", "加工", "工艺")),
        ("控制系统", ("控制系统", "反馈", "开环", "闭环")),
    ),
}


class ExamDiagnosticService:
    """Keep answer data server-side and expose only public papers and scored work."""

    def __init__(
        self,
        grader: StructuredExamGrader,
        bank_root: Path = DEFAULT_BANK_ROOT,
        persistence: MySQLPersistence | None = None,
    ) -> None:
        self.grader = grader
        self.bank_root = bank_root
        self.persistence = persistence
        self._manifest = self._load_json(bank_root / "manifest.json")
        self._papers: dict[str, dict[str, Any]] = {}
        self._answers: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise InputValidationError(f"高考诊断题库文件不存在：{path.name}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputValidationError(f"高考诊断题库文件损坏：{path.name}") from exc

    @property
    def available(self) -> bool:
        return bool(self._manifest.get("paper_count"))

    def catalog(self) -> dict[str, Any]:
        return {
            "schema_version": self._manifest["schema_version"],
            "paper_count": self._manifest["paper_count"],
            "subjects": copy.deepcopy(self._manifest["subjects"]),
            "answer_content_exposed": False,
            "constructed_response_grading": "multimodal_llm" if self.grader.available else "unavailable",
        }

    def teacher_assignable_paper(self, paper_id: str) -> dict[str, Any]:
        for subject in self._manifest.get("subjects", []):
            teacher_papers = subject.get("papers", [])[5:10]
            if any(item.get("paper_id") == paper_id for item in teacher_papers):
                return self.paper(paper_id)
        raise InputValidationError(
            "教师诊断卷只能选择每个科目第 6 至第 10 套，避免与平台诊断卷重复"
        )

    def paper(self, paper_id: str) -> dict[str, Any]:
        cached = self._papers.get(paper_id)
        if cached is not None:
            return copy.deepcopy(cached)
        subject = self._subject_for_paper(paper_id)
        payload = self._load_json(self.bank_root / subject / f"{paper_id}.json")
        for question in payload.get("questions", []):
            question["stem_html"] = question.get("stem_html", "").replace(
                "/agent-api/api/v1/exam-diagnostics/assets/",
                "/api/v1/exam-diagnostics/assets/",
            )
            for option in question.get("options", []):
                option["content_html"] = option.get("content_html", "").replace(
                    "/agent-api/api/v1/exam-diagnostics/assets/",
                    "/api/v1/exam-diagnostics/assets/",
                )
        if payload.get("paper_id") != paper_id:
            raise InputValidationError("诊断卷 ID 与题库内容不一致")
        if any("correct_option" in question or "standard_answer" in question for question in payload["questions"]):
            raise InputValidationError("学生端题面包含答案字段，已拒绝发布")
        self._papers[paper_id] = payload
        return copy.deepcopy(payload)

    def _answer_bank(self, paper_id: str) -> dict[str, Any]:
        cached = self._answers.get(paper_id)
        if cached is not None:
            return cached
        subject = self._subject_for_paper(paper_id)
        payload = self._load_json(
            self.bank_root / "answers" / subject / f"{paper_id}.answers.json"
        )
        if payload.get("paper_id") != paper_id or not payload.get("generated_from_source_only"):
            raise InputValidationError("标准答案库溯源校验失败")
        self._answers[paper_id] = payload
        return payload

    def _subject_for_paper(self, paper_id: str) -> str:
        for item in self._manifest.get("subjects", []):
            if any(paper.get("paper_id") == paper_id for paper in item.get("papers", [])):
                return str(item["subject"])
        raise InputValidationError("未找到指定的高考真题诊断卷")

    def create_session(
        self,
        *,
        student_id: str,
        paper_id: str,
        grade: str,
        province_code: str,
        target_exam_year: int,
        assignment_id: str | None = None,
    ) -> dict[str, Any]:
        paper = self.paper(paper_id)
        assignment = None
        if assignment_id:
            if not self.persistence:
                raise InputValidationError("教师诊断任务需要启用 MySQL 持久化")
            assignment = self.persistence.student_exam_assignment(
                student_id, assignment_id, paper_id
            )
            if not assignment:
                raise InputValidationError("诊断任务不存在、已关闭或不属于当前学生班级")
        session_id = f"examdiag_{uuid4().hex}"
        session = {
            "session_id": session_id,
            "student_id": student_id,
            "assignment_id": assignment_id,
            "assignment_title": assignment.get("title") if assignment else None,
            "assignment_classroom_id": assignment.get("classroom_id") if assignment else None,
            "assignment_class_name": assignment.get("class_name") if assignment else None,
            "paper_id": paper_id,
            "subject": paper["subject"],
            "grade": grade,
            "province_code": province_code,
            "target_exam_year": target_exam_year,
            "status": "in_progress",
            "created_at": utc_now().isoformat(),
            "objective_answers": {},
            "constructed_grades": {},
            "question_durations": {},
            "result": None,
        }
        self._sessions[session_id] = session
        if self.persistence:
            self.persistence.save_exam_session(session)
        return {"session": self._public_session(session), "paper": paper}

    def get_session(self, session_id: str, student_id: str) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        return {"session": self._public_session(session), "paper": self.paper(session["paper_id"])}

    def _session(self, session_id: str, student_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None and self.persistence:
            session = self.persistence.load_exam_session(session_id)
            if session:
                self._sessions[session_id] = session
        if session is None:
            raise InputValidationError("高考诊断会话不存在或服务已重启，请重新选卷")
        if session["student_id"] != student_id:
            raise InputValidationError("无权访问其他学生的诊断会话")
        return session

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        grades = {
            question_id: copy.deepcopy(result)
            for question_id, result in session["constructed_grades"].items()
        }
        return {
            key: copy.deepcopy(value)
            for key, value in session.items()
            if key not in {"objective_answers", "constructed_grades"}
        } | {
            "answered_objective_count": len(session["objective_answers"]),
            "graded_constructed_count": len(grades),
            "constructed_grades": grades,
        }

    async def grade_constructed(
        self,
        *,
        session_id: str,
        student_id: str,
        question_id: str,
        image_data_urls: list[str],
        ocr_text: str,
        image_warnings: list[str],
        duration_seconds: int,
    ) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        if session["status"] != "in_progress":
            raise InputValidationError("诊断卷已提交，不能重复修改主观题")
        paper = self.paper(session["paper_id"])
        question = next((item for item in paper["questions"] if item["question_id"] == question_id), None)
        if question is None or question["type"] != "constructed_response":
            raise InputValidationError("该题不是可拍照评分的主观题")
        if not image_data_urls:
            raise InputValidationError("请至少上传一张清晰的学生作答图片")
        if not self.grader.available:
            raise ModelUnavailableError("主观题多模态评分模型当前不可用，未使用规则分数替代")
        answer_bank = self._answer_bank(session["paper_id"])
        answer = next(item for item in answer_bank["answers"] if item["question_id"] == question_id)
        candidate = await self.grader.grade(
            question=question,
            answer=answer,
            image_data_urls=image_data_urls,
            ocr_text=ocr_text,
        )
        if candidate is None:
            raise ModelUnavailableError("主观题多模态评分模型未返回结果")
        grade_result = self._validated_grade(candidate, answer, image_warnings)
        session["question_durations"][question_id] = max(1, min(duration_seconds, 14_400))
        session["constructed_grades"][question_id] = grade_result
        if self.persistence:
            self.persistence.save_exam_session(session)
        return {
            "session_id": session_id,
            "question_id": question_id,
            "grading": copy.deepcopy(grade_result),
            "standard_answer_exposed": False,
        }

    @staticmethod
    def _validated_grade(
        candidate: ConstructedResponseGrade,
        answer: dict[str, Any],
        image_warnings: list[str],
    ) -> dict[str, Any]:
        expected = float(answer["max_score"])
        criteria_total = sum(item.possible for item in candidate.criteria)
        invalid_scale = (
            abs(candidate.max_score - expected) > 0.01
            or candidate.score > expected
            or (candidate.criteria and abs(criteria_total - expected) > 0.05)
        )
        requires_review = (
            candidate.requires_manual_review
            or not candidate.image_is_legible
            or candidate.confidence < 0.65
            or invalid_scale
        )
        score = None if invalid_scale or not candidate.image_is_legible else round(candidate.score, 2)
        review_reasons = [candidate.review_reason] if candidate.review_reason else []
        if invalid_scale:
            review_reasons.append("模型评分量表与本题满分不一致")
        if candidate.confidence < 0.65:
            review_reasons.append("模型评分置信度低于 65%")
        review_reasons.extend(image_warnings)
        return {
            "score": score,
            "max_score": expected,
            "recognized_student_work": candidate.recognized_student_work,
            "criteria": [item.model_dump(mode="json") for item in candidate.criteria],
            "strengths": candidate.strengths,
            "issues": candidate.issues,
            "feedback": candidate.feedback,
            "confidence": candidate.confidence,
            "image_is_legible": candidate.image_is_legible,
            "requires_manual_review": requires_review,
            "review_reason": "；".join(dict.fromkeys(item for item in review_reasons if item)),
            "graded_by": "multimodal_llm",
        }

    def submit(
        self,
        *,
        session_id: str,
        student_id: str,
        objective_answers: list[dict[str, Any]],
        question_durations: dict[str, int],
    ) -> dict[str, Any]:
        session = self._session(session_id, student_id)
        if session["status"] != "in_progress":
            return copy.deepcopy(session["result"])
        paper = self.paper(session["paper_id"])
        bank = self._answer_bank(session["paper_id"])
        questions = {item["question_id"]: item for item in paper["questions"]}
        answer_map = {item["question_id"]: item for item in bank["answers"]}
        unknown_duration_ids = set(question_durations) - set(questions)
        if unknown_duration_ids:
            raise InputValidationError(
                "题目用时包含不属于本卷的题目",
                details={"unknown_question_ids": sorted(unknown_duration_ids)},
            )
        invalid_durations = {
            question_id: value
            for question_id, value in question_durations.items()
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 14_400
        }
        if invalid_durations:
            raise InputValidationError("题目用时必须为 1 到 14400 秒的整数")
        required_objective = {
            item["question_id"] for item in paper["questions"] if item["type"] == "multiple_choice"
        }
        submitted = {item["question_id"]: item for item in objective_answers}
        if len(submitted) != len(objective_answers):
            raise InputValidationError("同一道选择题不能重复提交")
        if set(submitted) != required_objective:
            missing = sorted(required_objective - set(submitted))
            raise InputValidationError("请完成全部选择题后再提交", details={"missing": missing})

        objective_results: list[dict[str, Any]] = []
        session["objective_answers"] = copy.deepcopy(submitted)
        session["question_durations"].update(copy.deepcopy(question_durations))
        for question_id, answer in submitted.items():
            duration = answer.get("duration_seconds")
            if duration is not None:
                session["question_durations"][question_id] = duration
        for question_id in sorted(required_objective, key=lambda item: questions[item]["sequence"]):
            selected = submitted[question_id]["selected_option"]
            correct = answer_map[question_id]["correct_option"]
            score = float(questions[question_id]["max_score"] if selected == correct else 0)
            objective_results.append({
                "question_id": question_id,
                "selected_option": selected,
                "score": score,
                "max_score": questions[question_id]["max_score"],
                "is_correct": selected == correct,
            })

        constructed_results = [
            {"question_id": question_id, **copy.deepcopy(result)}
            for question_id, result in session["constructed_grades"].items()
        ]
        required_constructed = {
            item["question_id"] for item in paper["questions"] if item["type"] == "constructed_response"
        }
        graded_ids = set(session["constructed_grades"])
        pending = sorted(required_constructed - graded_ids)
        review_ids = sorted(
            question_id
            for question_id, result in session["constructed_grades"].items()
            if result["requires_manual_review"] or result["score"] is None
        )
        earned = sum(item["score"] for item in objective_results)
        earned += sum(item["score"] or 0 for item in constructed_results)
        possible_scored = sum(item["max_score"] for item in objective_results)
        possible_scored += sum(item["max_score"] for item in constructed_results if item["score"] is not None)
        status = "completed"
        if review_ids:
            status = "manual_review_required"
        elif pending:
            status = "provisional"
        evidence_records = self._evidence_records(
            session, paper, answer_map, objective_results, constructed_results
        )
        completed_at = utc_now().isoformat()
        learning_record = self._learning_record(
            session,
            paper,
            answer_map,
            objective_results,
            constructed_results,
            completed_at,
            status,
        )
        result = {
            "session_id": session_id,
            "paper_id": session["paper_id"],
            "subject": session["subject"],
            "status": status,
            "score": round(earned, 2),
            "scored_max": round(possible_scored, 2),
            "paper_max": paper["total_score"],
            "objective_results": objective_results,
            "constructed_results": constructed_results,
            "pending_constructed_question_ids": pending,
            "manual_review_question_ids": review_ids,
            "evidence_records": evidence_records,
            "learning_record": learning_record,
            "standard_answer_exposed": False,
            "completed_at": completed_at,
        }
        session["status"] = status
        session["result"] = result
        if self.persistence:
            self.persistence.save_exam_session(session)
        return copy.deepcopy(result)

    def attach_learning_diagnosis(
        self,
        session_id: str,
        student_id: str,
        diagnosis: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Persist the agent report beside the exam learning record for later retrieval."""
        session = self._session(session_id, student_id)
        if session["result"] is None:
            raise InputValidationError("诊断卷尚未提交")
        session["result"]["learning_diagnosis"] = copy.deepcopy(diagnosis)
        if self.persistence:
            self.persistence.save_exam_session(session)
        return copy.deepcopy(session["result"])

    @classmethod
    def _learning_record(
        cls,
        session: dict[str, Any],
        paper: dict[str, Any],
        answer_map: dict[str, dict[str, Any]],
        objective_results: list[dict[str, Any]],
        constructed_results: list[dict[str, Any]],
        completed_at: str,
        status: str,
    ) -> dict[str, Any]:
        """Build a student-facing record from the same evidence used by diagnosis."""
        result_map = {
            item["question_id"]: item for item in [*objective_results, *constructed_results]
        }
        knowledge: dict[str, dict[str, Any]] = {}
        question_records: list[dict[str, Any]] = []
        for question in paper["questions"]:
            question_id = question["question_id"]
            scored = result_map.get(question_id)
            score = scored.get("score") if scored else None
            max_score = float(question["max_score"])
            duration = int(session["question_durations"].get(question_id, 1))
            is_correct: bool | None = None
            if scored is not None and score is not None:
                is_correct = bool(scored.get("is_correct", abs(float(score) - max_score) < 0.01))
            knowledge_tags = cls._knowledge_tags(
                paper["subject"], question, answer_map.get(question_id, {})
            )
            question_records.append({
                "question_id": question_id,
                "sequence": question["sequence"],
                "question_type": question["type"],
                "knowledge_tags": knowledge_tags,
                "duration_seconds": duration,
                "score": score,
                "max_score": max_score,
                "is_correct": is_correct,
                "requires_manual_review": bool(scored and scored.get("requires_manual_review")),
                "source_title": question["source"]["source_title"],
                "source_question_number": question["source"]["original_number"],
            })
            for tag in knowledge_tags:
                summary = knowledge.setdefault(tag, {
                    "knowledge_tag": tag,
                    "question_count": 0,
                    "scored_question_count": 0,
                    "full_credit_count": 0,
                    "score": 0.0,
                    "max_score": 0.0,
                    "duration_seconds": 0,
                    "question_sequences": [],
                })
                summary["question_count"] += 1
                summary["duration_seconds"] += duration
                summary["question_sequences"].append(question["sequence"])
                if score is not None:
                    summary["scored_question_count"] += 1
                    summary["score"] += float(score)
                    summary["max_score"] += max_score
                    if abs(float(score) - max_score) < 0.01:
                        summary["full_credit_count"] += 1

        knowledge_statistics = []
        for item in knowledge.values():
            item["score"] = round(item["score"], 2)
            item["max_score"] = round(item["max_score"], 2)
            item["accuracy"] = round(item["score"] / item["max_score"], 4) if item["max_score"] else None
            item["average_duration_seconds"] = round(
                item["duration_seconds"] / item["question_count"]
            )
            knowledge_statistics.append(item)
        knowledge_statistics.sort(
            key=lambda item: (item["accuracy"] is None, item["accuracy"] or 0, -item["question_count"])
        )
        objective_correct = sum(1 for item in objective_results if item["is_correct"])
        earned = sum(float(item["score"] or 0) for item in result_map.values())
        score_accuracy = (
            round(earned / float(paper["total_score"]), 4)
            if paper["total_score"]
            else 0.0
        )
        student_analysis = cls._student_analysis(
            paper, question_records, knowledge_statistics, score_accuracy, status
        )
        return {
            "record_type": "gaokao_diagnostic",
            "assessment_id": session["session_id"],
            "student_id": session["student_id"],
            "subject": session["subject"],
            "paper_id": session["paper_id"],
            "paper_title": paper["title"],
            "started_at": session["created_at"],
            "completed_at": completed_at,
            "total_duration_seconds": sum(item["duration_seconds"] for item in question_records),
            "objective_accuracy": round(objective_correct / len(objective_results), 4) if objective_results else 0.0,
            "score_accuracy": score_accuracy,
            "is_provisional": status != "completed",
            "knowledge_statistics": knowledge_statistics,
            "question_records": question_records,
            "student_analysis": student_analysis,
        }

    @classmethod
    def _evidence_records(
        cls,
        session: dict[str, Any],
        paper: dict[str, Any],
        answer_map: dict[str, dict[str, Any]],
        objective_results: list[dict[str, Any]],
        constructed_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        question_map = {item["question_id"]: item for item in paper["questions"]}
        scored = [*objective_results]
        scored.extend(item for item in constructed_results if item["score"] is not None)
        records: list[dict[str, Any]] = []
        for result in scored:
            question = question_map[result["question_id"]]
            knowledge_tags = cls._knowledge_tags(
                paper["subject"], question, answer_map.get(question["question_id"], {})
            )
            error_tags: list[str] = []
            if result["score"] < result["max_score"]:
                error_tags.append(
                    "incorrect_option" if question["type"] == "multiple_choice" else "constructed_response_gap"
                )
            records.append({
                "assessment_id": session["session_id"],
                "assessment_type": "diagnostic",
                "question_id": question["question_id"],
                "knowledge_tags": knowledge_tags,
                "question_type": "选择题" if question["type"] == "multiple_choice" else "解答题",
                "ability_tags": [],
                "difficulty": question["difficulty"],
                "score": result["score"],
                "max_score": result["max_score"],
                "duration_seconds": session["question_durations"].get(question["question_id"], 1),
                "error_tags": error_tags,
                "step_trace": result.get("recognized_student_work"),
                "source_id": f"gaokao:{question['source']['document_sha256']}:{question['source']['original_number']}",
                "occurred_at": datetime.fromisoformat(session["created_at"]).isoformat(),
            })
        return records

    @staticmethod
    def _knowledge_tags(
        subject: str, question: dict[str, Any], answer: dict[str, Any]
    ) -> list[str]:
        original = [
            str(item).strip()
            for item in question.get("knowledge_tags") or []
            if str(item).strip()
        ]
        broad = not original or all(item.endswith("综合") for item in original)
        if not broad:
            return list(dict.fromkeys(original))
        searchable = " ".join(
            (
                HTML_TAG.sub(" ", str(question.get("stem_html") or "")),
                str(answer.get("analysis_text") or ""),
            )
        ).lower()
        matched = [
            label
            for label, keywords in SUBJECT_TOPIC_HINTS.get(subject, ())
            if any(keyword.lower() in searchable for keyword in keywords)
        ]
        matched = list(dict.fromkeys(matched))[:2]
        if matched:
            return matched
        if subject == "foreign_language":
            original_number = question.get("source", {}).get("original_number")
            try:
                number = int(original_number)
            except (TypeError, ValueError):
                number = 0
            if question.get("type") == "multiple_choice":
                if 21 <= number <= 35:
                    return ["阅读理解·信息定位与整合"]
                if 36 <= number <= 40:
                    return ["七选五衔接"]
                if 41 <= number <= 60:
                    return ["完形填空·语境词汇"]
                return ["语言知识运用"]
            if 55 <= number <= 65:
                return ["语法填空·语法与词形"]
            if number >= 66:
                return ["书面表达"]
            return ["阅读表达"]
        if subject == "history":
            period = re.search(
                r"准确时空(?:是|时)?[：:]\s*([^。；，]{2,28})", searchable
            )
            if period:
                return [f"历史专题·{period.group(1).strip(' ：:')}"]
        return original or ["暂未细分知识点"]

    @classmethod
    def _student_analysis(
        cls,
        paper: dict[str, Any],
        question_records: list[dict[str, Any]],
        knowledge_statistics: list[dict[str, Any]],
        score_accuracy: float,
        status: str,
    ) -> dict[str, Any]:
        if score_accuracy >= 0.85:
            level = "本卷表现突出"
        elif score_accuracy >= 0.7:
            level = "本卷基础较扎实"
        elif score_accuracy >= 0.55:
            level = "本卷处于发展阶段"
        elif score_accuracy >= 0.4:
            level = "本卷基础仍需巩固"
        else:
            level = "本卷需要重点补强"

        scored_knowledge = [
            item
            for item in knowledge_statistics
            if item["accuracy"] is not None
            and not str(item["knowledge_tag"]).endswith("综合")
        ]
        unresolved_sequences = sorted(
            {
                sequence
                for item in knowledge_statistics
                if str(item["knowledge_tag"]).endswith("综合")
                and item["accuracy"] is not None
                and float(item["accuracy"]) < 0.6
                for sequence in item["question_sequences"]
            }
        )
        weak = [item for item in scored_knowledge if float(item["accuracy"]) < 0.6][:5]
        strong = sorted(
            (item for item in scored_knowledge if float(item["accuracy"]) >= 0.75),
            key=lambda item: (-float(item["accuracy"]), -int(item["question_count"])),
        )[:4]
        durations = [int(item["duration_seconds"]) for item in question_records]
        typical_duration = median(durations) if durations else 0
        fast_wrong = [
            item
            for item in question_records
            if item["score"] is not None
            and float(item["score"]) < float(item["max_score"])
            and int(item["duration_seconds"]) <= max(15, typical_duration * 0.5)
        ]
        slow_low = [
            item
            for item in question_records
            if item["score"] is not None
            and float(item["score"]) / max(float(item["max_score"]), 1) < 0.6
            and int(item["duration_seconds"]) >= max(60, typical_duration * 1.75)
        ]
        total_duration = sum(durations)
        expected_duration = int(paper.get("duration_minutes") or 0) * 60
        pace_ratio = total_duration / expected_duration if expected_duration else 0
        if pace_ratio and pace_ratio < 0.55:
            pace = "整卷记录用时明显短于建议时长，速度较快，但需要结合失分题检查是否存在审题或验算不足。"
        elif pace_ratio and pace_ratio > 1.1:
            pace = "整卷记录用时超过建议时长，部分知识调用或解题路径可能不够熟练。"
        else:
            pace = "整卷记录用时处于建议时长的常见范围，时间分配总体可控。"
        behavior = [pace]
        if fast_wrong:
            sequences = "、".join(str(item["sequence"]) for item in fast_wrong[:6])
            behavior.append(
                f"第 {sequences} 题属于相对较快但未得满分的题目，建议优先复查题干条件、选项比较或最后一步验算。"
            )
        if slow_low:
            sequences = "、".join(str(item["sequence"]) for item in slow_low[:6])
            behavior.append(
                f"第 {sequences} 题用时相对较长且得分不足，更像是知识提取或解题路径受阻，应按对应知识点做针对性复盘。"
            )
        if not fast_wrong and not slow_low:
            behavior.append("本卷没有出现明显集中的“过快失分”或“长时间低得分”题组。")

        weak_names = "、".join(item["knowledge_tag"] for item in weak) or "暂无足够细分证据"
        strong_names = "、".join(item["knowledge_tag"] for item in strong) or "暂无达到稳定展示条件的知识点"
        score_note = "当前含待评分或待复核题目，结论会随最终成绩更新。" if status != "completed" else "当前所有题目已完成评分。"
        next_actions = [
            (
                f"先复盘“{item['knowledge_tag']}”：本卷 {item['question_count']} 题得分率"
                f" {float(item['accuracy']):.0%}，逐题标出失分发生在审题、知识调用还是运算/表达环节。"
            )
            for item in weak[:3]
        ]
        if not next_actions:
            next_actions.append("继续用同难度、不同题型的题目复测，确认本卷优势能否稳定迁移。")
        if unresolved_sequences:
            next_actions.append(
                f"第 {'、'.join(str(value) for value in unresolved_sequences[:8])} 题的原题库只提供学科大类标签，"
                "系统没有猜测具体知识点；请先按逐题记录核对题干与失分步骤，再由后续细分题验证。"
            )
        if fast_wrong:
            next_actions.append("对相对较快的失分题执行“圈条件—写依据—验结果”三步检查，再做同类题验证。")
        if slow_low:
            next_actions.append("对长时间低得分题先不限时梳理解法，再进行一次同类限时复测并比较用时。")
        return {
            "level_label": level,
            "level_summary": (
                f"本次《{paper['title']}》整卷得分率为 {score_accuracy:.0%}。"
                f"从已评分结果看，较有把握的知识点集中在{strong_names}；"
                f"需要优先补强的知识点集中在{weak_names}。{score_note}"
            ),
            "weak_knowledge": [
                {
                    "knowledge_tag": item["knowledge_tag"],
                    "accuracy": item["accuracy"],
                    "question_count": item["question_count"],
                    "duration_seconds": item["duration_seconds"],
                    "evidence": (
                        f"对应第 {'、'.join(str(value) for value in item['question_sequences'])} 题，"
                        f"共 {item['question_count']} 题，得分率 {float(item['accuracy']):.0%}，"
                        f"累计用时 {item['duration_seconds']} 秒。"
                    ),
                }
                for item in weak
            ],
            "strong_knowledge": [
                {
                    "knowledge_tag": item["knowledge_tag"],
                    "accuracy": item["accuracy"],
                    "question_count": item["question_count"],
                    "evidence": (
                        f"对应第 {'、'.join(str(value) for value in item['question_sequences'])} 题，"
                        f"共 {item['question_count']} 题，得分率 {float(item['accuracy']):.0%}。"
                    ),
                }
                for item in strong
            ],
            "answering_behavior": behavior,
            "fast_incomplete_question_sequences": [item["sequence"] for item in fast_wrong],
            "slow_low_score_question_sequences": [item["sequence"] for item in slow_low],
            "unresolved_knowledge_question_sequences": unresolved_sequences,
            "next_actions": next_actions[:5],
            "evidence_boundary": (
                "以上只描述本次试卷中可核验的得分、知识点和作答用时；"
                "不据此推断学生性格、心理或长期学习态度。长期水平需结合不同日期、不同题型的独立测次确认。"
            ),
        }
