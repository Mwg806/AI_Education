"""Evidence-grounded English analysis, reading practice and review scheduling."""

from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError
from ai_education.domain.english_learning import (
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
)
from ai_education.domain.protocols import utc_now
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.llm.english_learning import (
    GeneratedEnglishQuestion,
    GeneratedEnglishTraining,
    StructuredEnglishTrainingGenerator,
)
from ai_education.services.english_knowledge import EnglishKnowledgeService
from ai_education.services.policy import ExamPolicyService

WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "among",
    "because",
    "before",
    "being",
    "between",
    "could",
    "every",
    "first",
    "from",
    "have",
    "into",
    "many",
    "more",
    "most",
    "other",
    "over",
    "same",
    "should",
    "some",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "will",
    "with",
    "would",
    "your",
}
SKILL_LABELS = {
    "DETAIL_LOCATION": "细节定位",
    "MAIN_IDEA": "主旨概括",
    "INFERENCE": "文本推断",
    "AUTHOR_ATTITUDE": "作者态度",
    "WORD_MEANING_IN_CONTEXT": "语境词义",
    "REFERENCE_RESOLUTION": "指代判断",
    "TEXT_STRUCTURE": "篇章结构",
    "SEVEN_OF_FIVE_COHESION": "七选五衔接",
}
ERROR_LABELS = {
    "NO_TEXT_EVIDENCE": "原文没有对应证据",
    "PARTIAL_INFORMATION": "把局部信息当作完整结论",
    "OVERGENERALIZATION": "选项概括范围过大",
    "OVER_INFERENCE": "推理超出文本边界",
    "KEYWORD_MATCHING": "只匹配关键词，忽略句意",
    "LOCAL_MATCH_GLOBAL_CONFLICT": "局部能接上，但与全文逻辑冲突",
}


class EnglishLearningService:
    def __init__(
        self,
        repository: EnglishLearningRepository,
        generator: StructuredEnglishTrainingGenerator,
        knowledge: EnglishKnowledgeService | None = None,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.knowledge = knowledge or EnglishKnowledgeService()
        self.policy = ExamPolicyService()

    def analyze(
        self,
        student_id: str,
        body: EnglishTextAnalysisInput,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        text = self._normalize_and_validate(body.text)
        sentences = self._sentences(text)
        words = WORD_PATTERN.findall(text)
        lowered = [item.lower() for item in words]
        unique_ratio = len(set(lowered)) / max(1, len(lowered))
        long_word_ratio = sum(len(item) >= 8 for item in words) / max(1, len(words))
        average_sentence_words = len(words) / max(1, len(sentences))
        clause_markers = sum(
            lowered.count(item)
            for item in ("although", "because", "which", "while", "unless", "whereas")
        )
        lexical = min(0.95, 0.25 + long_word_ratio * 1.8 + unique_ratio * 0.35)
        syntactic = min(
            0.95,
            0.2 + average_sentence_words / 55 + clause_markers / max(8, len(sentences) * 4),
        )
        discourse = min(
            0.9,
            0.3
            + sum(lowered.count(item) for item in ("however", "therefore", "instead"))
            / max(4, len(sentences)),
        )
        absolute = round(lexical * 0.42 + syntactic * 0.38 + discourse * 0.2, 3)
        grade_baseline = {"grade_10": 0.48, "grade_11": 0.58, "grade_12": 0.66}.get(
            str(profile.get("grade")), 0.55
        )
        references = self.knowledge.curriculum_basis()
        analysis = {
            "analysis_id": f"eng_analysis_{uuid4().hex[:18]}",
            "student_id": student_id,
            "title": body.title,
            "normalized_text": text,
            "language": "en",
            "statistics": {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "average_sentence_words": round(average_sentence_words, 1),
                "lexical_diversity": round(unique_ratio, 3),
            },
            "difficulty": {
                "absolute_score": absolute,
                "relative_load": round(absolute - grade_baseline, 3),
                "dimensions": {
                    "lexical": round(lexical, 3),
                    "syntactic": round(syntactic, 3),
                    "discourse": round(discourse, 3),
                },
                "recommendation": self._difficulty_recommendation(absolute - grade_baseline),
            },
            "vocabulary_coverage": {
                "status": "needs_learner_evidence",
                "message": "未使用一次性自评推断已掌握词汇；完成训练后再累计客观证据。",
            },
            "core_vocabulary": self._core_vocabulary(sentences, lowered),
            "grammar_points": self._grammar_points(text),
            "complex_sentences": self._complex_sentences(sentences),
            "exam_skill_mapping": self._exam_skill_mapping(text, sentences),
            "source_references": references,
            "confidence": 0.86 if references else 0.72,
            "created_at": utc_now().isoformat(),
        }
        self.repository.save_analysis(analysis)
        return analysis

    async def create_training(
        self,
        student_id: str,
        body: EnglishTrainingCreateInput,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        text = self._normalize_and_validate(body.text)
        question_count = 5 if body.mode == "seven_of_five" else body.question_count
        exam_profile = self._exam_profile(profile)
        references = self.knowledge.curriculum_basis()
        generated = await self.generator.generate(
            {
                "exam_profile": exam_profile,
                "mode": body.mode,
                "question_count": question_count,
                "title": body.title,
                "text": text,
                "knowledge_references": references,
            }
        )
        generation_mode = "llm"
        if generated is None:
            generated = self._fallback_training(text, body.mode, question_count)
            generation_mode = "evidence_template"
        self._validate_training(generated, text, body.mode, question_count)
        analysis = self.analyze(
            student_id,
            EnglishTextAnalysisInput(title=body.title, text=text),
            profile,
        )
        session_id = f"eng_session_{uuid4().hex[:18]}"
        session = {
            "session_id": session_id,
            "student_id": student_id,
            "mode": body.mode,
            "title": body.title,
            "article_text": text,
            "display_text": generated.display_text,
            "status": "in_progress",
            "difficulty": analysis["difficulty"],
            "questions": [
                {"question_id": f"{session_id}_q{index + 1}", **item.model_dump(mode="json")}
                for index, item in enumerate(generated.questions)
            ],
            "exam_profile": exam_profile,
            "source_references": references,
            "generation_mode": generation_mode,
            "quality_status": "passed",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.repository.save_session(session)
        return self._public_session(session)

    def submit_training(
        self,
        student_id: str,
        session_id: str,
        body: EnglishTrainingSubmissionInput,
    ) -> dict[str, Any]:
        session = self.repository.get_session(session_id, student_id=student_id)
        if session["status"] != "in_progress":
            raise InputValidationError("该英语训练已经提交，不能重复计入学习证据")
        questions = {item["question_id"]: item for item in session["questions"]}
        if set(questions) != {item.question_id for item in body.answers}:
            raise InputValidationError("请完成全部题目后统一提交")
        current_states = {
            item["skill_id"]: item for item in self.repository.list_mastery_states(student_id)
        }
        results: list[dict[str, Any]] = []
        states: list[dict[str, Any]] = []
        reviews: list[dict[str, Any]] = []
        correct_count = 0
        now = utc_now()
        for answer in body.answers:
            question = questions[answer.question_id]
            is_correct = answer.selected_option == question["correct_option"]
            correct_count += int(is_correct)
            mechanism = question["distractor_mechanisms"][answer.selected_option]
            error_type = "NONE" if is_correct else mechanism
            weight = [1.0, 0.8, 0.65, 0.35, 0.15][min(answer.hint_count, 4)]
            skill = question["skill"]
            previous = current_states.get(skill, {})
            prior = float(previous.get("mastery_probability", 0.5))
            evidence_target = 1.0 if is_correct else 0.0
            updated = max(0.05, min(0.95, prior + (evidence_target - prior) * 0.22 * weight))
            old_stability = float(previous.get("stability_days", 2.0))
            stability = max(1.0, old_stability * (1.24 if is_correct else 0.68))
            due_days = max(1, min(30, round(stability * (0.8 if is_correct else 0.35))))
            state = {
                "student_id": student_id,
                "skill_id": skill,
                "skill_label": SKILL_LABELS.get(skill, skill),
                "mastery_probability": round(updated, 4),
                "stability_days": round(stability, 2),
                "evidence_count": int(previous.get("evidence_count", 0)) + 1,
                "confidence": round(
                    min(0.92, 0.42 + int(previous.get("evidence_count", 0)) * 0.06 + weight * 0.12),
                    3,
                ),
                "last_reviewed_at": now.isoformat(),
                "next_review_at": (now + timedelta(days=due_days)).isoformat(),
                "recent_error_type": None if is_correct else error_type,
            }
            states.append(state)
            current_states[skill] = state
            if not is_correct:
                reviews.append(
                    {
                        "review_id": f"eng_review_{uuid4().hex[:18]}",
                        "student_id": student_id,
                        "session_id": session_id,
                        "skill_id": skill,
                        "skill_label": SKILL_LABELS.get(skill, skill),
                        "prompt": (
                            f"回看“{session['title']}”中的{SKILL_LABELS.get(skill, skill)}证据"
                        ),
                        "evidence_quote": question["evidence_quote"],
                        "due_at": (now + timedelta(days=1)).isoformat(),
                        "status": "pending",
                    }
                )
            results.append(
                {
                    "question_id": answer.question_id,
                    "is_correct": is_correct,
                    "selected_option": answer.selected_option,
                    "correct_option": question["correct_option"],
                    "skill": skill,
                    "skill_label": SKILL_LABELS.get(skill, skill),
                    "evidence_quote": question["evidence_quote"],
                    "reasoning": question["reasoning"],
                    "error_type": error_type,
                    "error_label": ERROR_LABELS.get(error_type, error_type),
                    "recommended_strategy": self._strategy(skill, error_type),
                    "evidence_weight": weight,
                }
            )
        attempt = {
            "attempt_id": f"eng_attempt_{uuid4().hex[:18]}",
            "session_id": session_id,
            "student_id": student_id,
            "correct_count": correct_count,
            "question_count": len(questions),
            "score": round(correct_count / len(questions), 4),
            "results": results,
            "created_at": now.isoformat(),
        }
        session["status"] = "completed"
        session["updated_at"] = now.isoformat()
        self.repository.save_attempt_bundle(session, attempt, states, reviews)
        return {
            "session": self._public_session(session),
            "attempt": attempt,
            "mastery_states": states,
            "new_reviews": reviews,
        }

    def dashboard(self, student_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        states = self.repository.list_mastery_states(student_id)
        return {
            "exam_profile": self._exam_profile(profile),
            "mastery_states": states,
            "due_reviews": self.repository.list_reviews(student_id, status="pending"),
            "recent_sessions": [
                self._public_session(item)
                for item in self.repository.list_sessions(student_id, limit=8)
            ],
            "recent_analyses": self.repository.list_analyses(student_id, limit=6),
            "data_sufficiency": {
                "evidence_count": sum(int(item.get("evidence_count", 0)) for item in states),
                "score_prediction_available": False,
                "message": "单次练习不形成稳定高考分数预测；继续积累独立训练证据。",
            },
        }

    def complete_review(self, student_id: str, review_id: str, result: str) -> dict[str, Any]:
        saved = self.repository.complete_review(student_id, review_id, result)
        if not saved:
            raise InputValidationError("复习任务不存在、已完成或不属于当前学生")
        return saved

    @staticmethod
    def _normalize_and_validate(text: str) -> str:
        normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
        letters = len(re.findall(r"[A-Za-z]", normalized))
        visible = len(re.findall(r"[A-Za-z\u3400-\u9fff]", normalized))
        if letters < 60 or letters / max(1, visible) < 0.65:
            raise InputValidationError("请输入以英语为主、至少约 80 个字符的完整阅读材料")
        return normalized

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [item.strip() for item in SENTENCE_PATTERN.split(text) if item.strip()]

    @staticmethod
    def _difficulty_recommendation(relative_load: float) -> str:
        if relative_load <= -0.1:
            return "适合独立完成，可用于速度与流利度训练。"
        if relative_load <= 0.2:
            return "处于适宜挑战区，建议先独立作答再查看分析。"
        return "认知负荷较高，建议先查看核心词汇和长难句支架。"

    @staticmethod
    def _core_vocabulary(sentences: list[str], lowered: list[str]) -> list[dict[str, Any]]:
        counts = Counter(item for item in lowered if len(item) >= 6 and item not in STOP_WORDS)
        ranked = sorted(counts, key=lambda item: (counts[item], len(item)), reverse=True)[:10]
        return [
            {
                "word": word,
                "occurrences": counts[word],
                "context": next(
                    (
                        sentence
                        for sentence in sentences
                        if re.search(rf"\b{re.escape(word)}\b", sentence, re.I)
                    ),
                    "",
                ),
                "learning_priority": "核心理解词" if counts[word] > 1 else "语境学习词",
            }
            for word in ranked
        ]

    @staticmethod
    def _grammar_points(text: str) -> list[dict[str, str]]:
        patterns = [
            (r"\b(which|that|who|whom|whose)\b", "定语从句", "阅读长难句与指代判断"),
            (
                r"\b(having|being)\s+\w+(ed|en|ing)?\b|\bto\s+\w+",
                "非谓语动词",
                "语法填空与句子主干",
            ),
            (r"\b(has|have|had)\s+\w+(ed|en)\b", "完成时态", "事件时间关系"),
            (r"\balthough\b|\bthough\b|\bwhile\b", "让步与转折", "作者观点和篇章逻辑"),
            (r"\b(if|unless|provided)\b", "条件关系", "推理边界"),
        ]
        return [
            {"grammar_point": label, "evidence": match.group(0), "gaokao_relevance": relevance}
            for pattern, label, relevance in patterns
            if (match := re.search(pattern, text, re.I))
        ]

    @staticmethod
    def _complex_sentences(sentences: list[str]) -> list[dict[str, Any]]:
        results = []
        for sentence in sorted(
            sentences, key=lambda item: len(WORD_PATTERN.findall(item)), reverse=True
        ):
            words = WORD_PATTERN.findall(sentence)
            if len(words) < 24:
                continue
            segments = [item.strip() for item in re.split(r"[,;:]", sentence) if item.strip()]
            results.append(
                {
                    "sentence": sentence,
                    "word_count": len(words),
                    "segments": segments,
                    "guidance": "先找主句谓语，再判断逗号后的从句、非谓语或逻辑补充。",
                    "gaokao_risks": ["句子主干", "逻辑关系", "指代范围"],
                }
            )
            if len(results) == 3:
                break
        return results

    @staticmethod
    def _exam_skill_mapping(text: str, sentences: list[str]) -> list[dict[str, Any]]:
        mappings = [
            {"skill": "DETAIL_LOCATION", "label": "细节定位", "suitability": 0.9},
            {"skill": "MAIN_IDEA", "label": "主旨概括", "suitability": 0.84},
            {"skill": "INFERENCE", "label": "文本推断", "suitability": 0.76},
        ]
        if len(sentences) >= 7 and len(text) >= 600:
            mappings.append(
                {"skill": "SEVEN_OF_FIVE_COHESION", "label": "七选五衔接", "suitability": 0.74}
            )
        return mappings

    def _exam_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        province = str(profile.get("provinceCode") or profile.get("province_code") or "43")
        target_year = int(profile.get("targetExamYear") or profile.get("target_exam_year") or 2027)
        resolved = self.policy.resolve(province, target_year - 3, target_year)
        return {
            "exam_profile_id": resolved.exam_profile_id,
            "paper_variant": "NEW_GAOKAO_NATIONAL_I",
            "subject": "english",
            "province_code": province,
            "exam_year": target_year,
            "policy_version": resolved.policy_version,
            "requires_annual_reconfirmation": resolved.requires_annual_reconfirmation,
            "verification_note": resolved.verification_note,
        }

    @staticmethod
    def _fallback_training(text: str, mode: str, question_count: int) -> GeneratedEnglishTraining:
        sentences = [item for item in EnglishLearningService._sentences(text) if len(item) >= 25]
        if len(sentences) < question_count:
            raise InputValidationError("材料句子过少，无法生成可校验的阅读训练")
        selected = sentences[:question_count]
        if mode == "seven_of_five":
            option_pool = [
                *selected,
                "This idea is not supported by the passage.",
                "The writer changes to an unrelated topic here.",
            ]
            display = text
            questions = []
            for index, sentence in enumerate(selected):
                display = display.replace(sentence, f"[{index + 1}]", 1)
                questions.append(
                    GeneratedEnglishQuestion(
                        stem=f"第 {index + 1} 空应选择哪一项？",
                        skill="SEVEN_OF_FIVE_COHESION",
                        options=option_pool,
                        correct_option=index,
                        evidence_quote=sentence,
                        reasoning="将原句回填后，语义、指代与上下文顺序保持一致。",
                        distractor_mechanisms=[
                            "CORRECT_EVIDENCE"
                            if item == sentence
                            else "LOCAL_MATCH_GLOBAL_CONFLICT"
                            for item in option_pool
                        ],
                    )
                )
            return GeneratedEnglishTraining(display_text=display, questions=questions)
        skills = ["DETAIL_LOCATION", "MAIN_IDEA", "INFERENCE", "TEXT_STRUCTURE"]
        questions = []
        for index, sentence in enumerate(selected):
            short = sentence[:180]
            options = [
                short,
                f"The passage denies that {short[:100].lower()}",
                f"Only background knowledge suggests that {short[:90].lower()}",
                f"The passage gives no evidence about {short[:85].lower()}",
            ]
            questions.append(
                GeneratedEnglishQuestion(
                    stem="Which statement is directly supported by the passage?",
                    skill=skills[index % len(skills)],
                    options=options,
                    correct_option=0,
                    evidence_quote=sentence,
                    reasoning="正确选项直接复述原文证据，其余选项加入了否定或无文本依据的信息。",
                    distractor_mechanisms=[
                        "CORRECT_EVIDENCE",
                        "NO_TEXT_EVIDENCE",
                        "BACKGROUND_KNOWLEDGE_OVERRIDE",
                        "NO_TEXT_EVIDENCE",
                    ],
                )
            )
        return GeneratedEnglishTraining(display_text=text, questions=questions)

    @staticmethod
    def _validate_training(
        generated: GeneratedEnglishTraining, source: str, mode: str, count: int
    ) -> None:
        if len(generated.questions) != count:
            raise InputValidationError("生成题量与训练蓝图不一致，已阻止发布")
        compact_source = re.sub(r"\s+", " ", source).lower()
        for question in generated.questions:
            quote = re.sub(r"\s+", " ", question.evidence_quote).lower()
            if quote not in compact_source:
                raise InputValidationError("阅读题缺少可追溯原文证据，已阻止发布")
            expected_options = 7 if mode == "seven_of_five" else 4
            if len(question.options) != expected_options:
                raise InputValidationError("题目选项数量不符合训练模式")
        if mode == "seven_of_five" and not all(
            f"[{index}]" in generated.display_text for index in range(1, count + 1)
        ):
            raise InputValidationError("七选五空位未通过回填结构校验")
        if mode == "seven_of_five":
            option_pools = [tuple(item.options) for item in generated.questions]
            if any(pool != option_pools[0] for pool in option_pools[1:]):
                raise InputValidationError("七选五各空必须共享同一组选项，已阻止发布")
            correct_options = {item.correct_option for item in generated.questions}
            if len(correct_options) != count:
                raise InputValidationError("七选五正确选项存在重复，已阻止发布")

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        safe = {key: value for key, value in session.items() if key != "article_text"}
        if session.get("status") == "in_progress":
            safe["questions"] = [
                {
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "correct_option",
                        "evidence_quote",
                        "reasoning",
                        "distractor_mechanisms",
                    }
                }
                for item in session["questions"]
            ]
        return safe

    @staticmethod
    def _strategy(skill: str, error_type: str) -> str:
        if skill == "MAIN_IDEA":
            return "先概括每段功能，再比较选项覆盖的是全文还是局部。"
        if skill == "SEVEN_OF_FIVE_COHESION":
            return "先判断空位所在段落功能，再核对逻辑词、代词和上下句语义。"
        if error_type == "KEYWORD_MATCHING":
            return "找到关键词后继续核对主语、逻辑关系和结论范围。"
        return "返回原文定位完整证据句，逐项排除无证据或过度推断的选项。"
