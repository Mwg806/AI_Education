"""LLM-generated, deterministically scored quick diagnostic sessions."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from ai_education.config import Settings
from ai_education.core.errors import InputValidationError, PlannerModelUnavailableError
from ai_education.llm.diagnostic_generator import StructuredDiagnosticGenerator
from ai_education.services.curriculum_catalog import (
    ALL_CHAPTERS_ID,
    SUBJECT_LABELS,
    CurriculumCatalogService,
)
from ai_education.services.diagnostic_knowledge import DiagnosticKnowledgeRetriever
from ai_education.services.quick_diagnostic_bank import QuickDiagnosticBank

FOUNDATION_DIMENSIONS = {"prerequisite", "concept", "basic_application"}
APPLICATION_DIMENSIONS = {"integrated_application", "transfer"}
DIAGNOSTIC_DIMENSIONS = [
    "prerequisite",
    "concept",
    "basic_application",
    "integrated_application",
    "transfer",
] * 2
LOGGER = logging.getLogger(__name__)


class DiagnosticService:
    def __init__(
        self,
        catalog: CurriculumCatalogService,
        generator: StructuredDiagnosticGenerator,
        settings: Settings,
    ) -> None:
        self.catalog = catalog
        self.generator = generator
        self.settings = settings
        self.fixed_bank = QuickDiagnosticBank()
        self.knowledge_retriever = DiagnosticKnowledgeRetriever()
        self.sessions: dict[str, dict[str, Any]] = {}

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        subject = str(payload["subject"])
        chapter_ids = self._chapter_ids(payload)
        progress = self._progress_context(
            subject,
            str(payload["curriculum_version"]),
            chapter_ids,
        )
        grounding_scopes = self._grounding_scopes(progress)
        retrieval = self.knowledge_retriever.retrieve(
            subject=subject,
            scope_units=grounding_scopes,
        )
        slot_blueprint = self._slot_blueprint(grounding_scopes)
        context = {
            "subject_label": SUBJECT_LABELS[subject],
            "grade": str(payload["grade"]),
            "progress_label": progress["label"],
            "knowledge_context": progress["context"],
            "coverage_instruction": progress["coverage_instruction"],
            "slot_blueprint": json.dumps(slot_blueprint, ensure_ascii=False),
            "knowledge_sources": self.knowledge_retriever.prompt_sources(retrieval),
            "validation_feedback": "首次生成，请严格满足全部约束。",
        }
        generated = None
        fallback_reason = ""
        raw_questions: list[dict[str, Any]] = []
        generation_attempts = 0
        if retrieval["status"] != "ready":
            fallback_reason = retrieval["reason"]
        elif self.generator.available:
            for attempt in range(1, 4):
                generation_attempts = attempt
                try:
                    generated = await self.generator.generate(context)
                    if generated is None:
                        fallback_reason = "模型没有返回可校验的题组"
                        context["validation_feedback"] = fallback_reason
                        continue
                    raw_questions = [
                        item.model_dump(mode="json") for item in generated.questions
                    ]
                    for item in raw_questions:
                        self._reconcile_explicit_answer(item)
                    validation_error = self._validate_grounded_questions(
                        raw_questions,
                        progress=progress,
                        retrieval=retrieval,
                        slot_blueprint=slot_blueprint,
                    )
                    if not validation_error:
                        break
                    generated = None
                    raw_questions = []
                    fallback_reason = validation_error
                    context["validation_feedback"] = (
                        f"第 {attempt} 次结果未通过：{validation_error}。"
                        "请完整重做十题，不要沿用错误字段。"
                    )
                    LOGGER.warning(
                        "Quick diagnostic grounding validation failed on attempt %s: %s",
                        attempt,
                        validation_error,
                    )
                except Exception as exc:
                    generated = None
                    raw_questions = []
                    fallback_reason = self._model_validation_reason(exc)
                    context["validation_feedback"] = (
                        f"第 {attempt} 次结果未通过：{fallback_reason}。"
                        "请完整重做十题并严格按命题槽位输出。"
                    )
                    LOGGER.exception(
                        "Quick diagnostic model generation failed on attempt %s",
                        attempt,
                    )
        else:
            fallback_reason = "快速诊断模型暂时不可用"

        generation_mode = "llm"
        if generated is None:
            generation_mode = "fixed_bank_fallback"
            try:
                raw_questions = self.fixed_bank.questions(
                    subject=subject,
                    seed=(
                        f"{payload['student_id']}:{','.join(chapter_ids)}:{datetime.now().date()}"
                    ),
                    progress_label=progress["label"],
                    whole_book=progress["whole_book"],
                    scope_units=grounding_scopes,
                )
            except Exception as exc:
                raise PlannerModelUnavailableError(
                    "知识库约束命题未通过，且本地真题库没有足够的所选章节匹配题目",
                    details={
                        "provider": self.settings.llm_provider,
                        "model": self.settings.llm_model,
                        "stage": "diagnostic_generation",
                        "model_issue": fallback_reason,
                        "question_bank_issue": str(exc),
                    },
                ) from exc
        grounding = (
            self._llm_grounding(retrieval, raw_questions, generation_attempts)
            if generation_mode == "llm"
            else self._question_bank_grounding(raw_questions, generation_attempts)
        )
        diagnostic_id = f"diag_{uuid4().hex[:14]}"
        questions = []
        for index, question in enumerate(raw_questions, start=1):
            item = dict(question)
            item["question_id"] = f"{diagnostic_id}_q{index:02d}"
            questions.append(item)
        session = {
            "diagnostic_id": diagnostic_id,
            "student_id": str(payload["student_id"]),
            "subject": subject,
            "chapter_id": chapter_ids[0],
            "chapter_ids": chapter_ids,
            "progress_label": progress["label"],
            "scope_type": (
                "whole_book"
                if progress["whole_book"]
                else "multi_chapter"
                if progress["multi_chapter"]
                else "chapter"
            ),
            "generation_mode": generation_mode,
            "fallback_reason": fallback_reason if generation_mode != "llm" else "",
            "grounding": grounding,
            "status": "in_progress",
            "questions": questions,
            "created_at": datetime.now().astimezone().isoformat(),
            "result": None,
        }
        self.sessions[diagnostic_id] = session
        return self._public_session(session)

    def submit(
        self,
        diagnostic_id: str,
        student_id: str,
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session = self.sessions.get(diagnostic_id)
        if not session or session["student_id"] != student_id:
            raise InputValidationError("快速诊断会话不存在或不属于当前学生")
        if session["status"] == "completed":
            return session["result"]
        by_question = {item["question_id"]: item for item in session["questions"]}
        by_response = {str(item["question_id"]): item for item in responses}
        if set(by_response) != set(by_question):
            raise InputValidationError("必须完成全部 10 道诊断题后再提交")

        now = datetime.now().astimezone()
        evidence: list[dict[str, Any]] = []
        reviews = []
        dimension_scores: dict[str, list[float]] = {
            "foundation": [],
            "application": [],
        }
        calibration_scores = []
        correct_count = 0
        for question_id, question in by_question.items():
            response = by_response[question_id]
            selected = int(response["selected_option"])
            if selected < 0 or selected > 3:
                raise InputValidationError("诊断题选项下标必须在 0～3 之间")
            correct = selected == int(question["correct_option"])
            correct_count += int(correct)
            elapsed = max(1, min(int(response.get("response_time_seconds", 0)), 1800))
            expected = max(int(question["expected_seconds"]), 1)
            time_efficiency = max(0.0, 1 - abs(elapsed - expected) / expected)
            difficulty = float(question["difficulty"])
            difficulty_adjusted = min(1.0, (0.7 + 0.6 * difficulty)) if correct else 0.0
            performance = (
                min(1.0, 0.8 * difficulty_adjusted + 0.2 * time_efficiency) if correct else 0.0
            )
            group = (
                "foundation" if question["dimension"] in FOUNDATION_DIMENSIONS else "application"
            )
            dimension_scores[group].append(performance)
            confidence = min(max(float(response.get("confidence", 0.5)), 0), 1)
            calibration_scores.append(1 - abs(confidence - float(correct)))
            scope_id = str(question.get("scope_id") or session["chapter_id"])
            knowledge_id = f"{scope_id}_{group}"
            evidence.append(
                {
                    "knowledge_id": knowledge_id,
                    "score": round(performance, 3),
                    "weight": round(0.72 + 0.25 * difficulty, 3),
                    "source_type": "adaptive_diagnostic",
                    "source_id": f"{diagnostic_id}:{question_id}",
                    "description": (
                        f"{session['progress_label']}快速诊断：{question['knowledge_focus']}"
                    ),
                    "observed_at": now.isoformat(),
                    "error_tags": [] if correct else ["diagnostic_incorrect"],
                }
            )
            reviews.append(
                {
                    "question_id": question_id,
                    "selected_option": selected,
                    "correct_option": question["correct_option"],
                    "correct": correct,
                    "explanation": question["explanation"],
                    "knowledge_basis": question.get("source_excerpt"),
                    "provenance": question.get("provenance", {}),
                }
            )

        foundation_score = self._average(dimension_scores["foundation"])
        application_score = self._average(dimension_scores["application"])
        result = {
            "diagnostic_id": diagnostic_id,
            "status": "completed",
            "question_count": len(by_question),
            "correct_count": correct_count,
            "objective_score": round(correct_count / len(by_question), 3),
            "foundation_score": round(foundation_score, 3),
            "application_score": round(application_score, 3),
            "metacognitive_accuracy": round(self._average(calibration_scores), 3),
            "objective_evidence_count": len(evidence),
            "knowledge_evidence": evidence,
            "reviews": reviews,
            "completed_at": now.isoformat(),
        }
        session["status"] = "completed"
        session["result"] = result
        return result

    @staticmethod
    def _chapter_ids(payload: dict[str, Any]) -> list[str]:
        raw_ids = payload.get("chapter_ids") or [payload.get("chapter_id")]
        chapter_ids = [str(item) for item in raw_ids if item]
        if not chapter_ids:
            raise InputValidationError("必须选择至少 1 个诊断章节")
        if len(chapter_ids) > 5:
            raise InputValidationError("每次最多选择 5 个诊断章节")
        if len(set(chapter_ids)) != len(chapter_ids):
            raise InputValidationError("诊断章节不能重复选择")
        if ALL_CHAPTERS_ID in chapter_ids and len(chapter_ids) > 1:
            raise InputValidationError("整本书范围不能与具体章节同时选择")
        return chapter_ids

    def _progress_context(
        self,
        subject: str,
        edition_id: str,
        progress_ids: list[str],
    ) -> dict[str, Any]:
        catalog = self.catalog.subject_catalog(subject)
        edition = next(
            (item for item in catalog["editions"] if item["id"] == edition_id),
            None,
        )
        if progress_ids == [ALL_CHAPTERS_ID]:
            scope_units: list[dict[str, str]] = []
            context_parts: list[str] = []
            if edition:
                for volume in edition.get("volumes", []):
                    chapter_labels = []
                    for chapter in volume.get("chapters", []):
                        scope_units.append(
                            {
                                "id": str(chapter["id"]),
                                "label": str(chapter.get("title", chapter["id"])),
                            }
                        )
                        chapter_labels.append(
                            f"{chapter['id']}={chapter.get('title', chapter['id'])}"
                        )
                    if chapter_labels:
                        context_parts.append(
                            f"{volume.get('label', '教材分册')}：" + "；".join(chapter_labels)
                        )
            if not scope_units:
                for module in catalog["standard_modules"]:
                    scope_units.append({"id": str(module["id"]), "label": str(module["label"])})
                    context_parts.append(
                        f"{module['id']}={module['label']}（"
                        + "、".join(module.get("topics", []))
                        + "）"
                    )
            if not scope_units:
                raise InputValidationError("当前教材没有可用于整本书诊断的章节或模块")
            edition_label = str(edition.get("label", "当前教材")) if edition else "当前教材"
            return {
                "label": f"{edition_label} · 整本书（全部章节）",
                "context": "教材全范围目录：" + "\n".join(context_parts),
                "whole_book": True,
                "multi_chapter": False,
                "scope_units": scope_units,
                "coverage_instruction": (
                    "这是整本书诊断。10 道题须尽量分散到不同章节与知识点，至少覆盖 "
                    f"{min(6, len(scope_units), 10)} 个不同范围。每题 scope_id 必须填写上述目录中"
                    "对应的内部 ID，scope_label 填写对应章节或知识点名称。"
                ),
            }

        selected = [
            self._single_progress_context(catalog, edition, progress_id)
            for progress_id in progress_ids
        ]
        if len(selected) == 1:
            return selected[0]

        scope_units = [item["scope_units"][0] for item in selected]
        scope_catalog = "；".join(f"{item['id']}={item['label']}" for item in scope_units)
        return {
            "label": f"已选 {len(selected)} 个章节："
            + "；".join(item["label"] for item in selected),
            "context": "本次选定范围：\n"
            + "\n".join(
                f"{unit['id']}={unit['label']}；{item['context']}"
                for unit, item in zip(scope_units, selected, strict=True)
            ),
            "whole_book": False,
            "multi_chapter": True,
            "scope_units": scope_units,
            "coverage_instruction": (
                f"这是多章节诊断，只能覆盖以下 {len(scope_units)} 个范围：{scope_catalog}。"
                "10 道题须覆盖全部所选范围，每个范围至少 1 题，并在范围之间合理分配题量。"
                "每题 scope_id 必须使用上述对应内部 ID，scope_label 使用对应章节名称。"
            ),
        }

    @staticmethod
    def _single_progress_context(
        catalog: dict[str, Any],
        edition: dict[str, Any] | None,
        progress_id: str,
    ) -> dict[str, Any]:
        if edition:
            for volume in edition.get("volumes", []):
                for chapter in volume.get("chapters", []):
                    if chapter["id"] == progress_id:
                        label = (
                            f"{volume.get('label', '')} {chapter.get('title', progress_id)}"
                        ).strip()
                        evidence = chapter.get("evidence", {})
                        return {
                            "label": label,
                            "context": (
                                f"教材章节：{label}；目录证据页："
                                f"{evidence.get('pdf_page', '待核验')}"
                            ),
                            "whole_book": False,
                            "multi_chapter": False,
                            "scope_units": [{"id": progress_id, "label": label}],
                            "coverage_instruction": "10 道题围绕当前章节的不同知识点分散命题。",
                        }
        module = next(
            (item for item in catalog["standard_modules"] if item["id"] == progress_id),
            None,
        )
        if module:
            topics = "、".join(module.get("topics", []))
            return {
                "label": module["label"],
                "context": f"课程标准模块：{module['label']}；主题：{topics}",
                "whole_book": False,
                "multi_chapter": False,
                "scope_units": [{"id": progress_id, "label": module["label"]}],
                "coverage_instruction": "10 道题围绕当前模块的不同知识点分散命题。",
            }
        raise InputValidationError("当前诊断范围不在已核验教材或课程标准目录中")

    def _prepare_generated_scope(
        self,
        questions: list[dict[str, Any]],
        progress: dict[str, Any],
    ) -> str:
        scope_units = progress["scope_units"]
        if not progress["whole_book"] and not progress["multi_chapter"]:
            self._assign_scope_units(questions, scope_units)
            return ""

        allowed_scope_ids = {item["id"] for item in scope_units}
        provided_scope_ids = [str(item.get("scope_id") or "") for item in questions]
        if progress["multi_chapter"] and not any(provided_scope_ids):
            self._assign_scope_units(questions, scope_units)
            return ""
        if any(item not in allowed_scope_ids for item in provided_scope_ids):
            return "模型题目包含所选章节以外的范围"

        generated_scope_ids = set(provided_scope_ids)
        required_coverage = (
            len(allowed_scope_ids)
            if progress["multi_chapter"]
            else min(6, len(allowed_scope_ids), 10)
        )
        if len(generated_scope_ids) < required_coverage:
            return (
                "模型题目未覆盖全部所选章节"
                if progress["multi_chapter"]
                else "模型题目未达到整本书多章节覆盖要求"
            )
        labels = {item["id"]: item["label"] for item in scope_units}
        for item in questions:
            item["scope_label"] = labels[str(item["scope_id"])]
        return ""

    @staticmethod
    def _grounding_scopes(progress: dict[str, Any]) -> list[dict[str, str]]:
        scope_units = list(progress["scope_units"])
        if not progress["whole_book"] or len(scope_units) <= 6:
            return scope_units
        last = len(scope_units) - 1
        indexes = [round(index * last / 5) for index in range(6)]
        return [scope_units[index] for index in dict.fromkeys(indexes)]

    @staticmethod
    def _slot_blueprint(scope_units: list[dict[str, str]]) -> list[dict[str, str]]:
        return [
            {
                "slot_id": f"slot_{index + 1:02d}",
                "dimension": dimension,
                "scope_id": scope_units[index % len(scope_units)]["id"],
                "scope_label": scope_units[index % len(scope_units)]["label"],
            }
            for index, dimension in enumerate(DIAGNOSTIC_DIMENSIONS)
        ]

    def _validate_grounded_questions(
        self,
        questions: list[dict[str, Any]],
        *,
        progress: dict[str, Any],
        retrieval: dict[str, Any],
        slot_blueprint: list[dict[str, str]],
    ) -> str:
        if len(questions) != 10:
            return "模型没有生成恰好 10 道题"
        expected_slots = {item["slot_id"]: item for item in slot_blueprint}
        if {str(item.get("slot_id")) for item in questions} != set(expected_slots):
            return "模型没有完整使用十个知识库命题槽位"
        sources = {
            (str(item["scope_id"]), str(item["source_id"])): item
            for item in retrieval["sources"]
        }
        for question in questions:
            slot = expected_slots[str(question["slot_id"])]
            if question.get("dimension") != slot["dimension"]:
                return f"{slot['slot_id']} 的诊断维度与命题槽位不一致"
            if str(question.get("scope_id")) != slot["scope_id"]:
                return f"{slot['slot_id']} 引用了命题槽位以外的章节"
            source_key = (slot["scope_id"], str(question.get("source_chunk_id") or ""))
            source = sources.get(source_key)
            if source is None:
                return f"{slot['slot_id']} 没有引用该章节的有效知识库片段"
            excerpt = self._normalize_grounding_text(str(question.get("source_excerpt") or ""))
            content = self._normalize_grounding_text(str(source["content"]))
            if len(excerpt) < 8 or excerpt not in content:
                return f"{slot['slot_id']} 的知识依据不是知识库原文摘录"
            question["scope_label"] = slot["scope_label"]
            question["provenance"] = {
                "mode": "knowledge_grounded_ai",
                "source_id": source["source_id"],
                "title": source["title"],
                "document_type": source["document_type"],
                "authority_level": source["authority_level"],
                "page_start": source["page_start"],
                "page_end": source["page_end"],
                "source_url": source["source_url"],
                "scope_match_verified": True,
                "excerpt_verified": True,
            }
        return self._prepare_generated_scope(questions, progress)

    @staticmethod
    def _normalize_grounding_text(value: str) -> str:
        return re.sub(r"\s+", "", value).replace("　", "")

    @staticmethod
    def _model_validation_reason(exc: Exception) -> str:
        message = str(exc)
        if "五个诊断维度必须各包含两题" in message:
            return "五个诊断维度没有各生成两题"
        if "十个诊断题必须分别对应十个唯一命题槽位" in message:
            return "模型重复或遗漏了知识库命题槽位"
        if "validation error" in message.lower():
            return "模型输出未通过十题字段与结构校验"
        return "快速诊断模型调用异常"

    def _llm_grounding(
        self,
        retrieval: dict[str, Any],
        questions: list[dict[str, Any]],
        generation_attempts: int,
    ) -> dict[str, Any]:
        used = {str(item.get("source_chunk_id") or "") for item in questions}
        sources = [
            item
            for item in self.knowledge_retriever.public_sources(retrieval)
            if item["source_id"] in used
        ]
        return {
            "mode": "knowledge_grounded_ai",
            "status": "verified",
            "source_count": len(sources),
            "sources": sources,
            "generation_attempts": generation_attempts,
            "scope_match_verified": True,
            "excerpt_verified": True,
        }

    @staticmethod
    def _question_bank_grounding(
        questions: list[dict[str, Any]], generation_attempts: int
    ) -> dict[str, Any]:
        sources_by_id: dict[str, dict[str, Any]] = {}
        for question in questions:
            provenance = dict(question.get("provenance") or {})
            source_id = str(provenance.get("source_id") or "")
            if source_id:
                sources_by_id[source_id] = provenance
        return {
            "mode": "verified_question_bank",
            "status": "verified",
            "source_count": len(sources_by_id),
            "sources": list(sources_by_id.values()),
            "generation_attempts": generation_attempts,
            "scope_match_verified": True,
            "excerpt_verified": False,
        }

    @staticmethod
    def _assign_scope_units(
        questions: list[dict[str, Any]],
        scope_units: list[dict[str, str]],
    ) -> None:
        for index, question in enumerate(questions):
            unit = scope_units[index % len(scope_units)]
            question["scope_id"] = unit["id"]
            question["scope_label"] = unit["label"]

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _reconcile_explicit_answer(question: dict[str, Any]) -> None:
        """Repair a model index only when its explanation names one unique option."""
        explanation = str(question.get("explanation", ""))
        clauses = re.findall(r"(?:正确(?:答案|选项|项)|应选|故选)[^。；\n]{0,80}", explanation)
        if not clauses:
            return
        explicit_text = " ".join(clauses).replace(" ", "")
        matches = []
        for index, option in enumerate(question.get("options", [])):
            normalized = re.sub(r"\s+", "", str(option))
            if len(normalized) >= 2 and normalized in explicit_text:
                matches.append(index)
        if len(matches) == 1:
            question["correct_option"] = matches[0]

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        questions = [
            {
                key: value
                for key, value in question.items()
                if key
                not in {
                    "correct_option",
                    "explanation",
                    "slot_id",
                    "source_chunk_id",
                    "source_excerpt",
                }
            }
            for question in session["questions"]
        ]
        return {
            "diagnostic_id": session["diagnostic_id"],
            "student_id": session["student_id"],
            "subject": session["subject"],
            "chapter_id": session["chapter_id"],
            "chapter_ids": session["chapter_ids"],
            "progress_label": session["progress_label"],
            "scope_type": session["scope_type"],
            "generation_mode": session["generation_mode"],
            "fallback_reason": session["fallback_reason"],
            "grounding": session["grounding"],
            "status": session["status"],
            "question_count": len(questions),
            "questions": questions,
            "created_at": session["created_at"],
        }
