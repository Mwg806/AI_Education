"""Evidence-grounded English analysis, reading practice and review scheduling."""

from __future__ import annotations

import copy
import logging
import re
from collections import Counter
from datetime import timedelta
from typing import Any
from uuid import uuid4

from ai_education.core.errors import InputValidationError, ModelUnavailableError
from ai_education.domain.english_learning import (
    EnglishLearnerProfileInput,
    EnglishReadingHintInput,
    EnglishTaskInput,
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
)
from ai_education.domain.protocols import utc_now
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.llm.english_learning import (
    GeneratedEnglishQuestion,
    GeneratedEnglishTraining,
    GeneratedLanguageTask,
    LanguageCorrection,
    LanguageQualityCheck,
    LanguageVocabularyItem,
    ReadingEvidenceItem,
    StructuredEnglishTrainingGenerator,
    StructuredLanguageTutorGenerator,
)
from ai_education.services.english_knowledge import EnglishKnowledgeService
from ai_education.services.policy import ExamPolicyService

logger = logging.getLogger(__name__)

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

NATIONAL_I_BLUEPRINT = {
    "paper_variant": "新高考全国Ⅰ卷",
    "target_users": "参加新高考全国Ⅰ卷的高中英语考生",
    "score": 150,
    "sections": [
        {"id": "listening", "label": "听力", "score": 30, "status": "planned"},
        {
            "id": "reading",
            "label": "阅读理解",
            "score": 30,
            "question_count": 15,
            "status": "ready",
        },
        {
            "id": "seven_of_five",
            "label": "七选五",
            "score": 10,
            "question_count": 5,
            "status": "ready",
        },
        {
            "id": "cloze",
            "label": "完形填空",
            "score": 15,
            "question_count": 15,
            "status": "planned",
        },
        {
            "id": "grammar_fill",
            "label": "语法填空",
            "score": 15,
            "question_count": 10,
            "status": "planned",
        },
        {"id": "writing", "label": "写作", "score": 40, "status": "ready"},
        {"id": "translation", "label": "语言表达与翻译", "score": 10, "status": "ready"},
    ],
    "notes": [
        "本 Agent 面向全国Ⅰ卷考生，训练反馈使用全国卷题型和评分边界。",
        "听力、完形和语法填空保留接口，待对应题库与音频资源接入后启用。",
        "当前评分是学习诊断证据，不是高考官方成绩预测。",
    ],
}


class EnglishLearningService:
    def __init__(
        self,
        repository: EnglishLearningRepository,
        generator: StructuredEnglishTrainingGenerator,
        knowledge: EnglishKnowledgeService | None = None,
        tutor_generator: StructuredLanguageTutorGenerator | None = None,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.knowledge = knowledge or EnglishKnowledgeService()
        self.tutor_generator = tutor_generator or StructuredLanguageTutorGenerator(None)
        self.policy = ExamPolicyService()

    def learner_profile(self, student_id: str, account_profile: dict[str, Any]) -> dict[str, Any]:
        stored = self.repository.load_learner_profile(student_id)
        if stored:
            return stored
        default_level = {
            "grade_10": "A2",
            "grade_11": "B1",
            "grade_12": "B1",
        }.get(str(account_profile.get("grade")), "B1")
        now = utc_now().isoformat()
        return {
            "student_id": student_id,
            "native_language": "zh-CN",
            "target_language": "en",
            "estimated_level": default_level,
            "self_reported_level": default_level,
            "daily_minutes": 30,
            "level_confidence": 0.35,
            "preferred_mode": "teaching",
            "explanation_depth": "medium",
            "show_examples": True,
            "show_exercises": True,
            "learning_goals": ["新高考全国Ⅰ卷英语"],
            "weaknesses": [],
            "evidence_count": 0,
            "updated_at": now,
        }

    def update_learner_profile(
        self,
        student_id: str,
        body: EnglishLearnerProfileInput,
        account_profile: dict[str, Any],
    ) -> dict[str, Any]:
        self._exam_profile(account_profile)
        current = self.learner_profile(student_id, account_profile)
        payload = {
            **current,
            **body.model_dump(mode="json"),
            "student_id": student_id,
            "estimated_level": current.get("estimated_level") or body.self_reported_level,
            "updated_at": utc_now().isoformat(),
        }
        self.repository.save_learner_profile(payload)
        return payload

    async def execute_task(
        self,
        student_id: str,
        body: EnglishTaskInput,
        account_profile: dict[str, Any],
    ) -> dict[str, Any]:
        exam_profile = self._exam_profile(account_profile)
        source_text = self._validate_task_source(body.task_type, body.source_text)
        learner = self.learner_profile(student_id, account_profile)
        existing = self.repository.learning_records(student_id)
        shared_learning_context = {
            "unified_student_profile": account_profile.get("unified_student_profile", {}),
            "recent_learning_events": account_profile.get("recent_learning_events", [])[-20:],
        }
        learner_for_generation = {
            **learner,
            "shared_learning_context": shared_learning_context,
            "recent_writing_history": self._recent_writing_history(existing["events"]),
        }
        references = self.knowledge.curriculum_basis()
        generation_mode = "llm"
        generated = None
        generation_error: Exception | None = None
        for _ in range(2):
            try:
                generated = await self.tutor_generator.generate(
                    {
                        **body.model_dump(mode="json"),
                        "source_text": source_text,
                        "learner_profile": learner_for_generation,
                        "exam_profile": exam_profile,
                        "knowledge_references": references,
                    }
                )
                if generated is not None:
                    generated = self._normalize_writing_profile(generated, body)
                    self._validate_language_task(
                        generated, body, source_text, learner_for_generation
                    )
                break
            except Exception as exc:
                generation_error = exc
                generated = None
        if generated is None:
            if body.task_type == "writing_revision":
                raise ModelUnavailableError(
                    "写作评价未通过五维证据与详细度校验，请稍后重新提交；系统没有用简短模板冒充客观评价"
                ) from generation_error
            if generation_error is not None:
                logger.warning(
                    "English language generation failed after retry; using safe fallback: %s",
                    generation_error,
                )
            generated = self._fallback_language_task(body, source_text, learner)
            generation_mode = "rule_fallback"
            self._validate_language_task(generated, body, source_text, learner)
        now = utc_now()
        vocabulary = self._vocabulary_updates(
            student_id, generated.vocabulary, existing["vocabulary"], now
        )
        grammar = self._grammar_updates(student_id, generated.corrections, existing["grammar"], now)
        event_id = f"eng_evt_{uuid4().hex[:18]}"
        event = {
            "event_id": event_id,
            "student_id": student_id,
            "task_type": body.task_type,
            "response_mode": body.response_mode,
            "source_excerpt": source_text[:800],
            "learner_level": generated.learner_level,
            "result": generated.model_dump(mode="json"),
            "generation_mode": generation_mode,
            "quality_status": "passed",
            "training_context": {
                "title": body.training_title,
                "prompt": body.training_prompt,
                "requirements": body.training_requirements,
                "target_word_count": body.target_word_count,
                "elapsed_seconds": body.elapsed_seconds,
            },
            "created_at": now.isoformat(),
        }
        writing = None
        if body.task_type == "writing_revision":
            writing = {
                "submission_id": f"eng_write_{uuid4().hex[:18]}",
                "student_id": student_id,
                "event_id": event_id,
                "revision_level": body.revision_level,
                "source_text": source_text,
                "revised_text": generated.revised_text,
                "corrections": [item.model_dump(mode="json") for item in generated.corrections],
                "scores": generated.scores,
                "writing_assessment": (
                    generated.writing_assessment.model_dump(mode="json")
                    if generated.writing_assessment
                    else None
                ),
                "training_context": copy.deepcopy(event["training_context"]),
                "created_at": now.isoformat(),
            }
        speaking = None
        if body.task_type == "speaking_practice":
            speaking = {
                "speaking_session_id": f"eng_speak_{uuid4().hex[:18]}",
                "student_id": student_id,
                "event_id": event_id,
                "scenario": body.scenario,
                "feedback_mode": body.feedback_mode,
                "transcript": source_text,
                "feedback": generated.model_dump(mode="json"),
                "pronunciation_scored": False,
                "created_at": now.isoformat(),
            }
        reviews = self._task_reviews(student_id, event_id, vocabulary, grammar, now)
        if body.include_learning_record:
            self.repository.save_learning_task_bundle(
                event, vocabulary, grammar, writing, speaking, reviews
            )
            if body.task_type == "exam_practice":
                self.repository.save_national_exam_attempt(
                    {
                        "attempt_id": f"eng_exam_{uuid4().hex[:18]}",
                        "student_id": student_id,
                        "section": body.exam_section,
                        "score": None,
                        "max_score": next(
                            (
                                item["score"]
                                for item in NATIONAL_I_BLUEPRINT["sections"]
                                if item["id"] == body.exam_section
                            ),
                            None,
                        ),
                        "evidence_count": len(generated.reading_evidence),
                        "task_type": body.task_type,
                        "created_at": now.isoformat(),
                    }
                )
            learner = {
                **learner,
                "evidence_count": int(learner.get("evidence_count", 0)) + 1,
                "level_confidence": min(
                    0.9, 0.35 + (int(learner.get("evidence_count", 0)) + 1) * 0.05
                ),
                "updated_at": now.isoformat(),
            }
            self.repository.save_learner_profile(learner)
        return {
            "task": {
                "primary_intent": generated.primary_intent,
                "response_mode": body.response_mode,
                "learner_level": generated.learner_level,
                "national_i_candidate": True,
            },
            "answer": generated.model_dump(mode="json"),
            "learning_record": {
                "saved": body.include_learning_record,
                "event_id": event_id if body.include_learning_record else None,
                "new_vocabulary": vocabulary,
                "grammar_updates": grammar,
                "review_items": reviews,
            },
            "learner_profile": learner,
            "exam_profile": exam_profile,
            "source_references": references,
            "generation_mode": generation_mode,
            "national_i_blueprint": NATIONAL_I_BLUEPRINT,
        }

    @staticmethod
    def exam_blueprint() -> dict[str, Any]:
        return {**NATIONAL_I_BLUEPRINT, "version": "national1-2026.1"}

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
        generation_mode = "llm"
        generated = None
        generation_error: Exception | None = None
        for _ in range(2):
            try:
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
                if generated is not None:
                    self._validate_training(generated, text, body.mode, question_count)
                break
            except Exception as exc:
                generation_error = exc
                generated = None
        if generated is None:
            if generation_error is not None:
                logger.warning(
                    "English reading generation failed after retry; using evidence fallback: %s",
                    generation_error,
                )
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
            "analysis": analysis,
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

    def reading_hint(
        self,
        student_id: str,
        session_id: str,
        body: EnglishReadingHintInput,
    ) -> dict[str, Any]:
        session = self.repository.get_session(session_id, student_id=student_id)
        if session["status"] != "in_progress":
            raise InputValidationError("训练已经提交，请直接查看提交后的完整解析")
        question = next(
            (item for item in session["questions"] if item["question_id"] == body.question_id),
            None,
        )
        if question is None:
            raise InputValidationError("阅读题不存在或不属于当前训练")
        paragraphs = [
            item.strip() for item in re.split(r"\n\s*\n", session["article_text"]) if item.strip()
        ] or [session["article_text"]]
        quote = re.sub(r"\s+", " ", question["evidence_quote"]).strip()
        paragraph_number = next(
            (
                index
                for index, paragraph in enumerate(paragraphs, start=1)
                if quote.lower() in re.sub(r"\s+", " ", paragraph).lower()
            ),
            1,
        )
        if body.level == 1:
            content = f"先回到第 {paragraph_number} 段定位，不要只凭选项中的重复词判断。"
        elif body.level == 2:
            content = f"重点核对这句原文：“{quote}”"
        elif body.level == 3:
            content = self._strategy(question["skill"], "")
        else:
            option = int(question["correct_option"])
            content = (
                f"正确选项是 {chr(65 + option)}：{question['options'][option]}。"
                f"{question['reasoning']}"
            )
        return {
            "session_id": session_id,
            "question_id": body.question_id,
            "level": body.level,
            "content": content,
            "answer_exposed": body.level == 4,
            "next_level": body.level + 1 if body.level < 4 else None,
        }

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
        records = self._normalize_mastery_records(self.repository.learning_records(student_id))
        sessions = self.repository.list_sessions(student_id, limit=30)
        ability_profile = self._ability_profile(states, records)
        due_reviews = self.repository.list_reviews(student_id, status="pending")
        return {
            "exam_profile": self._exam_profile(profile),
            "target_user": "新高考全国Ⅰ卷考生",
            "exam_blueprint": self.exam_blueprint(),
            "learner_profile": self.learner_profile(student_id, profile),
            "mastery_states": states,
            "due_reviews": due_reviews,
            "recent_sessions": [
                self._public_session(item)
                for item in sessions[:8]
            ],
            "recent_analyses": self.repository.list_analyses(student_id, limit=6),
            "learning_records": records,
            "training_archives": self._training_archives(sessions, records),
            "weekly_report": self._weekly_report(records),
            "ability_profile": ability_profile,
            "recommendation": self._recommendation(ability_profile, due_reviews),
            "data_sufficiency": {
                "evidence_count": sum(int(item.get("evidence_count", 0)) for item in states),
                "score_prediction_available": False,
                "message": "单次练习不形成稳定高考分数预测；继续积累独立训练证据。",
            },
        }

    @staticmethod
    def _training_archives(
        sessions: list[dict[str, Any]], records: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        grammar = []
        for session in sessions:
            if (
                session.get("mode") != "grammar_ai_three_question"
                or session.get("status") != "completed"
                or not session.get("assessment")
            ):
                continue
            grammar.append(
                {
                    "archive_id": session.get("session_id"),
                    "archive_type": "grammar",
                    "title": session.get("title") or "语法训练",
                    "focus": session.get("focus") or session.get("article_text") or "",
                    "level": session.get("level"),
                    "elapsed_seconds": int(session.get("elapsed_seconds") or 0),
                    "questions": list(session.get("questions") or []),
                    "answers": list(session.get("answers") or []),
                    "assessment": dict(session.get("assessment") or {}),
                    "generation_mode": session.get("generation_mode"),
                    "evaluation_mode": session.get("evaluation_mode"),
                    "created_at": session.get("created_at"),
                    "updated_at": session.get("updated_at"),
                }
            )

        events_by_id = {
            item.get("event_id"): item
            for item in records.get("events", [])
            if item.get("event_id")
        }
        writing = []
        for submission in records.get("writing", []):
            event = events_by_id.get(submission.get("event_id"), {})
            result = dict(event.get("result") or {})
            context = dict(
                submission.get("training_context")
                or event.get("training_context")
                or {}
            )
            writing.append(
                {
                    "archive_id": submission.get("submission_id"),
                    "archive_type": "writing",
                    "title": context.get("title") or result.get("title") or "写作训练",
                    "prompt": context.get("prompt") or "",
                    "requirements": list(context.get("requirements") or []),
                    "target_word_count": context.get("target_word_count") or "",
                    "elapsed_seconds": int(context.get("elapsed_seconds") or 0),
                    "source_text": submission.get("source_text") or "",
                    "revised_text": submission.get("revised_text") or result.get("revised_text") or "",
                    "scores": dict(submission.get("scores") or result.get("scores") or {}),
                    "writing_assessment": submission.get("writing_assessment")
                    or result.get("writing_assessment"),
                    "strengths": list(result.get("strengths") or []),
                    "priority_improvements": list(
                        result.get("priority_improvements") or []
                    ),
                    "corrections": list(
                        submission.get("corrections") or result.get("corrections") or []
                    ),
                    "generation_mode": event.get("generation_mode"),
                    "created_at": submission.get("created_at") or event.get("created_at"),
                }
            )
        return {"grammar": grammar[:20], "writing": writing[:20]}

    def delete_learning_record(
        self, student_id: str, record_type: str, record_id: str
    ) -> dict[str, Any]:
        if record_type not in {"event", "vocabulary"}:
            raise InputValidationError("仅支持删除学习事件或生词本条目")
        if not self.repository.delete_learning_record(student_id, record_type, record_id):
            raise InputValidationError("学习记录不存在或不属于当前学生")
        return {"deleted": True, "record_type": record_type, "record_id": record_id}

    def complete_review(self, student_id: str, review_id: str, result: str) -> dict[str, Any]:
        saved = self.repository.complete_review(student_id, review_id, result)
        if not saved:
            raise InputValidationError("复习任务不存在、已完成或不属于当前学生")
        return saved

    @staticmethod
    def _validate_task_source(task_type: str, source: str) -> str:
        normalized = re.sub(r"[ \t]+", " ", source.replace("\r\n", "\n")).strip()
        letters = len(re.findall(r"[A-Za-z]", normalized))
        if task_type in {"learning_plan", "progress_query"}:
            return normalized
        minimum = 40 if task_type in {"reading_comprehension", "exam_practice"} else 1
        if letters < minimum:
            message = (
                "阅读理解需要较完整的英语材料（至少约 40 个英文字母）"
                if task_type == "reading_comprehension"
                else "请输入需要学习或修改的英语内容"
            )
            raise InputValidationError(message)
        return normalized

    @staticmethod
    def _validate_language_task(
        generated: GeneratedLanguageTask,
        body: EnglishTaskInput,
        source: str,
        learner: dict[str, Any],
    ) -> None:
        if generated.primary_intent != body.task_type:
            raise InputValidationError("任务路由结果与用户选择不一致，已阻止发布")
        checks = generated.quality_check
        if not all(
            (
                checks.task_completed,
                checks.language_correct,
                checks.level_adapted,
                checks.facts_preserved,
                checks.format_valid,
                not checks.unsupported_claims,
            )
        ):
            raise InputValidationError("语言学习结果未通过事实、难度或格式质量门禁")
        compact = re.sub(r"\s+", " ", source).lower()
        if body.task_type in {"reading_comprehension", "exam_practice"}:
            if not generated.reading_evidence:
                raise InputValidationError("阅读结论缺少原文依据，已阻止发布")
            for item in generated.reading_evidence:
                if re.sub(r"\s+", " ", item.evidence_quote).lower() not in compact:
                    raise InputValidationError("阅读依据无法在原文中定位，已阻止发布")
        if body.task_type == "writing_revision":
            if not generated.revised_text:
                raise InputValidationError("写作修改缺少完整修改稿")
            source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", source))
            revised_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", generated.revised_text))
            if not source_numbers.issubset(revised_numbers):
                raise InputValidationError("写作修改丢失原文数值事实，已阻止发布")
            expected_dimensions = {
                "task_fulfillment",
                "content",
                "organization",
                "language",
                "mechanics",
            }
            if set(generated.scores) != expected_dimensions or any(
                generated.scores[key] is None for key in expected_dimensions
            ):
                raise InputValidationError("写作评价没有完整返回五个客观维度分数")
            assessment = generated.writing_assessment
            if assessment is None:
                raise InputValidationError("写作评价缺少当前水平、提升点与不足分析")
            by_dimension = {item.dimension: item for item in assessment.dimensions}
            compact_source = re.sub(r"\s+", "", source).lower()
            for dimension in expected_dimensions:
                item = by_dimension[dimension]
                if item.score != generated.scores[dimension]:
                    raise InputValidationError("写作逐维分析分数与五维总表不一致")
                evidence = re.sub(r"\s+", "", item.evidence_quote).lower()
                if not evidence or evidence not in compact_source:
                    raise InputValidationError("写作逐维评价引用的证据无法在学生原文中定位")
            if len(generated.strengths) < 2 or len(generated.priority_improvements) < 2:
                raise InputValidationError("写作评价的优势或优先改进说明过于简单")
            has_history = bool(learner.get("recent_writing_history"))
            expected_basis = "compared_with_history" if has_history else "current_only"
            if assessment.historical_comparison_basis != expected_basis:
                raise InputValidationError("写作进步结论与可用历史档案证据不一致")
        if (
            body.task_type == "speaking_practice"
            and generated.scores.get("pronunciation") is not None
        ):
            raise InputValidationError("当前只有文本证据，不允许生成发音评分")
        limits = {"A1": 3, "A2": 3, "B1": 5, "B2": 5, "C1": 8, "C2": 8}
        level = str(learner.get("estimated_level", "B1"))
        if len(generated.corrections) > limits.get(level, 5):
            raise InputValidationError("本轮纠错重点过多，不符合认知负荷约束")

    @classmethod
    def _normalize_writing_profile(
        cls, generated: GeneratedLanguageTask, body: EnglishTaskInput
    ) -> GeneratedLanguageTask:
        if body.task_type != "writing_revision" or generated.writing_assessment is None:
            return generated
        score_values = [
            int(value)
            for key in (
                "task_fulfillment",
                "content",
                "organization",
                "language",
                "mechanics",
            )
            if (value := generated.scores.get(key)) is not None
        ]
        if len(score_values) != 5:
            return generated
        average_score = sum(score_values) / len(score_values)
        overall_level = cls._writing_level(average_score)
        assessment = generated.writing_assessment.model_copy(
            update={"overall_level": overall_level}
        )
        return generated.model_copy(update={"writing_assessment": assessment})

    @staticmethod
    def _writing_level(average_score: float) -> str:
        if average_score >= 85:
            return "表现突出"
        if average_score >= 75:
            return "较熟练"
        if average_score >= 60:
            return "稳步发展"
        if average_score >= 45:
            return "基本达成"
        return "基础起步"

    @classmethod
    def _recent_writing_history(
        cls, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for event in events:
            if event.get("task_type") != "writing_revision":
                continue
            result = dict(event.get("result") or {})
            scores = {
                key: value
                for key, value in dict(result.get("scores") or {}).items()
                if value is not None
            }
            if not scores:
                continue
            profile = dict(result.get("writing_assessment") or {})
            history.append(
                {
                    "created_at": event.get("created_at"),
                    "title": (event.get("training_context") or {}).get("title")
                    or result.get("title"),
                    "scores": scores,
                    "overall_level": profile.get("overall_level")
                    or cls._writing_level(sum(scores.values()) / len(scores)),
                    "strengths": list(result.get("strengths") or [])[:3],
                    "priority_improvements": list(
                        result.get("priority_improvements") or []
                    )[:3],
                }
            )
            if len(history) >= 3:
                break
        return history

    @staticmethod
    def _fallback_language_task(
        body: EnglishTaskInput, source: str, learner: dict[str, Any]
    ) -> GeneratedLanguageTask:
        level = str(learner.get("estimated_level", "B1"))
        quality = LanguageQualityCheck(
            task_completed=True,
            language_correct=True,
            level_adapted=True,
            facts_preserved=True,
            unsupported_claims=False,
            format_valid=True,
        )
        base: dict[str, Any] = {
            "primary_intent": body.task_type,
            "learner_level": level,
            "title": "新高考全国Ⅰ卷英语学习反馈",
            "quality_check": quality,
        }
        if body.task_type == "learning_plan":
            return GeneratedLanguageTask(
                **base,
                display_markdown=(
                    "## 全国Ⅰ卷英语本周学习计划\n\n"
                    "1. 阅读理解：完成 2 篇文章，先定位证据再选择答案。\n"
                    "2. 七选五：完成 1 组，重点检查代词、连接词和段落功能。\n"
                    "3. 语言知识：复习待复习词汇，完成 10 题语法专项。\n"
                    "4. 写作表达：完成 1 次应用文或读后续写段落，保留修改前后对照。"
                ),
                exercises=["完成今日 20 分钟阅读并提交每道题的证据位置。"],
            )
        if body.task_type == "progress_query":
            return GeneratedLanguageTask(
                **base,
                display_markdown=(
                    "## 全国Ⅰ卷英语学习进度\n\n"
                    "当前报告基于已保存的学习事件生成；完成更多独立训练后，"
                    "系统会分别更新阅读、七选五、词汇、语法和写作证据。"
                ),
            )
        if body.task_type == "exam_practice":
            sentence = (EnglishLearningService._sentences(source) or [source])[0]
            return GeneratedLanguageTask(
                **base,
                display_markdown=(
                    f"## 全国Ⅰ卷 {body.exam_section} 训练\n\n"
                    "本题仅依据你提供的材料生成学习任务。\n\n"
                    f"**证据句**：{sentence}\n\n"
                    "**作答要求**：先写出依据位置，再说明你排除干扰项的理由。"
                ),
                key_facts=[sentence],
                reading_evidence=[
                    ReadingEvidenceItem(claim="材料中的可核验事实", evidence_quote=sentence)
                ],
                exercises=["请写出本题对应的全国Ⅰ卷能力标签和证据句。"],
            )
        if body.task_type == "translation":
            return GeneratedLanguageTask(
                **base,
                translation="离线模式保留原文，待模型或教师核验后生成正式译文：" + source,
                display_markdown=(
                    "## 翻译任务\n\n当前离线模式不会伪造译文，请提交后由模型或教师核验。"
                ),
            )
        if body.task_type == "speaking_practice":
            return GeneratedLanguageTask(
                **base,
                agent_reply="That is a useful starting point. Could you give one specific example?",
                next_question="Please answer in two or three complete sentences.",
                scores={
                    "fluency": None,
                    "accuracy": None,
                    "coherence": None,
                    "pronunciation": None,
                },
                display_markdown=(
                    "## 全国Ⅰ卷英语表达训练\n\n请先用英语回答下一问；当前没有音频，因此不评价发音。"
                ),
            )
        if body.task_type == "reading_comprehension":
            sentence = EnglishLearningService._sentences(source)[0]
            return GeneratedLanguageTask(
                **base,
                main_idea="文章围绕首段提出的核心信息展开；离线模式仅给出可核验的基础分析。",
                summary=sentence,
                structure=["首段：提出核心信息", "后续：补充说明与例证"],
                key_facts=[sentence],
                reading_evidence=[
                    ReadingEvidenceItem(claim="首段包含文章的核心信息", evidence_quote=sentence)
                ],
                display_markdown=f"## 基础理解\n\n{sentence}\n\n## 原文依据\n\n{sentence}",
            )
        source_words = WORD_PATTERN.findall(source)
        source_lookup = {item.lower(): item for item in source_words}
        requested_words = [
            source_lookup[item.lower()]
            for item in WORD_PATTERN.findall(body.user_message)
            if item.lower() in source_lookup and item.lower() not in STOP_WORDS
        ]
        meaningful_source_words = [item for item in source_words if item.lower() not in STOP_WORDS]
        word = (requested_words or meaningful_source_words or source_words or [source])[0]
        if body.task_type == "vocabulary_explanation":
            vocab = LanguageVocabularyItem(
                word=word,
                contextual_meaning="当前离线词库未提供可靠释义，已保留该词等待模型或教师核验。",
                example=f"Please use {word} in a sentence about your studies.",
                common_mistake="不要脱离上下文只记一个中文意思。",
            )
            return GeneratedLanguageTask(
                **base,
                vocabulary=[vocab],
                exercises=[f"请结合原语境解释 {word}。"],
                display_markdown=f"## {word}\n\n已加入待核验生词，建议结合上下文学习。",
            )
        corrected = source
        corrections: list[LanguageCorrection] = []
        if re.search(r"\bhave went\b", source, re.I) and re.search(r"\blast year\b", source, re.I):
            corrected = re.sub(r"\bhave went\b", "went", source, flags=re.I)
            corrections.append(
                LanguageCorrection(
                    original="have went",
                    corrected="went",
                    category="grammar",
                    severity="major",
                    explanation=(
                        "last year 是明确过去时间，应使用一般过去时；went 已是 go 的过去式。"
                    ),
                    alternatives=[],
                )
            )
        if re.search(r"\bvery like\b", source, re.I):
            corrected = re.sub(r"\bvery like\b", "really like", corrected, flags=re.I)
            corrections.append(
                LanguageCorrection(
                    original="very like",
                    corrected="really like",
                    category="naturalness",
                    severity="major",
                    explanation="very 通常不直接修饰动词 like，可用 really。",
                    alternatives=["like it very much", "like it a lot"],
                )
            )
        if body.task_type == "writing_revision":
            corrected = re.sub(r"\bfor improve\b", "for improving", corrected, flags=re.I)
            corrected = re.sub(
                r"\bhas very important meaning\b",
                "is highly significant",
                corrected,
                flags=re.I,
            )
        if body.task_type in {"grammar_correction", "writing_revision"}:
            return GeneratedLanguageTask(
                **base,
                revised_text=corrected if body.task_type == "writing_revision" else "",
                short_answer=corrected,
                corrections=corrections,
                display_markdown=f"## 修改结果\n\n{corrected}",
            )
        if body.task_type == "translation":
            return GeneratedLanguageTask(
                **base,
                translation=source,
                display_markdown="当前处于离线保守模式，原文已保留，未生成未经核验的翻译。",
                priority_improvements=["模型恢复后重新提交可获得可靠翻译"],
            )
        return GeneratedLanguageTask(
            **base,
            agent_reply=(
                "Thank you for sharing your answer. Let's make it clearer and more natural."
            ),
            next_question="What is the strongest reason for your opinion?",
            scores={
                "fluency": None,
                "accuracy": 70,
                "coherence": 70,
                "vocabulary": 65,
                "naturalness": 65,
                "pronunciation": None,
            },
            display_markdown="## 对话回应\n\nWhat is the strongest reason for your opinion?",
        )

    @staticmethod
    def _vocabulary_updates(
        student_id: str,
        items: list[LanguageVocabularyItem],
        existing: list[dict[str, Any]],
        now: Any,
    ) -> list[dict[str, Any]]:
        by_key = {item["word_key"]: item for item in existing}
        updates = []
        for item in items[:10]:
            key = re.sub(r"[^a-z0-9'-]", "", item.word.lower())[:96]
            if not key:
                continue
            old = by_key.get(key, {})
            contexts = int(old.get("contexts_seen", 0)) + 1
            previous = float(old.get("mastery_score", 0.2))
            if previous > 1:
                previous /= 3
            score = min(0.9, previous + (0.68 - previous) * 0.22)
            updates.append(
                {
                    "student_id": student_id,
                    "word_key": key,
                    "word": item.word,
                    "phonetic": item.phonetic,
                    "part_of_speech": item.part_of_speech,
                    "contextual_meaning": item.contextual_meaning,
                    "collocations": item.collocations,
                    "example": item.example,
                    "common_mistake": item.common_mistake,
                    "contexts_seen": contexts,
                    "encounter_count": contexts,
                    "correct_count": int(old.get("correct_count", 0)),
                    "wrong_count": int(old.get("wrong_count", 0)),
                    "mastery_score": round(score, 4),
                    "status": ("new" if score < 0.3 else "learning" if score < 0.7 else "mastered"),
                    "next_review_at": (now + timedelta(days=1)).isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
        return updates

    @staticmethod
    def _grammar_updates(
        student_id: str,
        corrections: list[LanguageCorrection],
        existing: list[dict[str, Any]],
        now: Any,
    ) -> list[dict[str, Any]]:
        by_key = {item["grammar_key"]: item for item in existing}
        updates = []
        for item in corrections:
            tokens = WORD_PATTERN.findall(item.original.lower())[:4]
            key = f"{item.category}_{'_'.join(tokens) or 'general'}"[:96]
            old = by_key.get(key, {})
            count = int(old.get("error_count", 0)) + 1
            previous = float(old.get("mastery_score", 0.65))
            if previous > 1:
                previous /= 3
            updates.append(
                {
                    "student_id": student_id,
                    "grammar_key": key,
                    "label": item.explanation[:120],
                    "error_count": count,
                    "practice_count": int(old.get("practice_count", 0)) + 1,
                    "correct_count": int(old.get("correct_count", 0)),
                    "wrong_count": int(old.get("wrong_count", 0)) + 1,
                    "mastery_score": round(max(0.05, previous * 0.9), 4),
                    "confidence": round(min(0.95, count / 3), 3),
                    "stable_weakness": count >= 3,
                    "example_error": item.original,
                    "recommended_action": "targeted_practice" if count >= 3 else "observe",
                    "next_review_at": (now + timedelta(days=1)).isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
        return updates

    @staticmethod
    def _task_reviews(
        student_id: str,
        event_id: str,
        vocabulary: list[dict[str, Any]],
        grammar: list[dict[str, Any]],
        now: Any,
    ) -> list[dict[str, Any]]:
        reviews = []
        for item in [*vocabulary, *grammar][:8]:
            is_vocab = "word_key" in item
            key = item.get("word_key") or item["grammar_key"]
            reviews.append(
                {
                    "review_id": f"eng_review_{uuid4().hex[:18]}",
                    "student_id": student_id,
                    "session_id": None,
                    "event_id": event_id,
                    "skill_id": f"vocabulary:{key}" if is_vocab else f"grammar:{key}",
                    "skill_label": item.get("word") or "语法纠错复习",
                    "prompt": (
                        f"请不看解释，回忆 {item['word']} 在本次语境中的含义。"
                        if is_vocab
                        else f"请改正并解释：{item['example_error']}"
                    ),
                    "evidence_quote": item.get("example") or item.get("example_error", ""),
                    "due_at": (now + timedelta(days=1)).isoformat(),
                    "status": "pending",
                }
            )
        return reviews

    @staticmethod
    def _weekly_report(records: dict[str, Any]) -> dict[str, Any]:
        cutoff = (utc_now() - timedelta(days=7)).isoformat()
        events = [item for item in records["events"] if item["created_at"] >= cutoff]
        task_counts = Counter(item["task_type"] for item in events)
        stable = [item for item in records["grammar"] if item.get("stable_weakness")]
        return {
            "period_days": 7,
            "completed_tasks": len(events),
            "task_counts": dict(task_counts),
            "vocabulary_count": len(records["vocabulary"]),
            "stable_grammar_weaknesses": stable[:5],
            "next_step": (
                "优先完成到期复习，并针对重复语法错误进行一次主动输出。"
                if events
                else "先完成一次阅读、词汇或写作任务，建立首条客观学习记录。"
            ),
        }

    @staticmethod
    def _normalize_mastery_records(records: dict[str, Any]) -> dict[str, Any]:
        for group in ("vocabulary", "grammar"):
            for item in records[group]:
                score = float(item.get("mastery_score", 0))
                item["mastery_score"] = round(min(1.0, score / 3 if score > 1 else score), 4)
        return records

    @staticmethod
    def _ability_profile(states: list[dict[str, Any]], records: dict[str, Any]) -> dict[str, Any]:
        reading_dimensions = {
            item["skill_id"]: {
                "label": item.get("skill_label", item["skill_id"]),
                "score": float(item.get("mastery_probability", 0)),
                "evidence_count": int(item.get("evidence_count", 0)),
            }
            for item in states
        }

        def average(items: list[dict[str, Any]], key: str) -> float | None:
            values = [float(item.get(key, 0)) for item in items]
            return round(sum(values) / len(values), 4) if values else None

        writing_scores = []
        for event in records["events"]:
            if event.get("task_type") != "writing_revision":
                continue
            scores = event.get("result", {}).get("scores", {})
            values = [float(value) / 100 for value in scores.values() if value is not None]
            if values:
                writing_scores.append(sum(values) / len(values))
        reading_values = [item["score"] for item in reading_dimensions.values()]
        return {
            "reading": round(sum(reading_values) / len(reading_values), 4)
            if reading_values
            else None,
            "vocabulary": average(records["vocabulary"], "mastery_score"),
            "grammar": average(records["grammar"], "mastery_score"),
            "writing": round(sum(writing_scores) / len(writing_scores), 4)
            if writing_scores
            else None,
            "speaking": None,
            "reading_dimensions": reading_dimensions,
        }

    @staticmethod
    def _recommendation(
        ability_profile: dict[str, Any], due_reviews: list[dict[str, Any]]
    ) -> dict[str, Any]:
        dimensions = ability_profile["reading_dimensions"]
        weakest = sorted(dimensions.items(), key=lambda item: item[1]["score"])
        next_learning = [item[1]["label"] for item in weakest[:2]]
        if not next_learning:
            next_learning = ["完成一篇阅读训练，建立客观能力证据"]
        reading_score = ability_profile.get("reading")
        difficulty = 55 if reading_score is None else round(45 + reading_score * 30)
        return {
            "review": [item["skill_label"] for item in due_reviews[:5]],
            "next_learning": next_learning,
            "suggested_task": {
                "type": "reading",
                "difficulty": difficulty,
                "reason": "优先训练当前证据最弱的阅读能力，并在完成后更新画像。",
            },
        }

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
            "national_paper_type": resolved.national_paper_type,
            "target_user": "新高考全国Ⅰ卷考生",
            "audience_eligible": resolved.national_paper_type == "national_paper_i",
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
