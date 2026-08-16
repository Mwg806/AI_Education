"""Unified learning-event ingestion and legacy AgentResponse adaptation."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from ai_education.domain.enums import AgentRole, MessageType
from ai_education.domain.multi_agent import LearningEvent, LearningEventType
from ai_education.domain.protocols import AgentMessage, AgentRequest, AgentResponse
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository


class LearningEventService:
    def __init__(
        self,
        repository: SharedLearningRepository,
        profile_service: StudentProfileService,
    ) -> None:
        self.repository = repository
        self.profile_service = profile_service

    async def emit(self, event: LearningEvent) -> LearningEvent:
        inserted = self.repository.save_event(event.model_dump(mode="json"))
        if inserted:
            try:
                await self.profile_service.apply_event(event)
            except Exception as exc:
                self.repository.mark_event_failed(event.event_id, f"{type(exc).__name__}: {exc}")
                raise
            else:
                self.repository.mark_event_processed(event.event_id)
        return event

    async def replay_pending_outbox(self, limit: int = 100) -> dict[str, Any]:
        summary: dict[str, Any] = {"examined": 0, "processed": 0, "failed": []}
        for record in self.repository.list_pending_event_outbox(limit):
            summary["examined"] += 1
            event_id = str(record["event_id"])
            try:
                event = LearningEvent.model_validate(record["payload"])
                await self.profile_service.apply_event(event)
                self.repository.mark_event_processed(event_id)
                summary["processed"] += 1
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                self.repository.mark_event_failed(event_id, error)
                summary["failed"].append({"event_id": event_id, "error": error})
        return summary

    async def get_recent_events(self, user_id: str, limit: int = 100) -> list[LearningEvent]:
        return [
            LearningEvent.model_validate(item)
            for item in self.repository.list_events(user_id, limit=limit)
        ]

    async def get_events_by_knowledge(
        self, user_id: str, knowledge_point: str
    ) -> list[LearningEvent]:
        return [
            LearningEvent.model_validate(item)
            for item in self.repository.list_events(
                user_id, limit=200, knowledge_point=knowledge_point
            )
        ]

    async def summarize_recent_learning(self, user_id: str) -> dict[str, Any]:
        events = await self.get_recent_events(user_id, 100)
        type_counts = Counter(item.event_type.value for item in events)
        knowledge_counts = Counter(item.knowledge_point for item in events if item.knowledge_point)
        errors = [
            item
            for item in events
            if item.event_type
            in {
                LearningEventType.QUESTION_WRONG,
                LearningEventType.KNOWLEDGE_WEAK,
                LearningEventType.READING_ERROR,
                LearningEventType.GRAMMAR_ERROR,
                LearningEventType.WRITING_ERROR,
                LearningEventType.SPEAKING_ERROR,
            }
        ]
        summary = {
            "event_count": len(events),
            "event_types": dict(type_counts),
            "frequent_knowledge_points": [
                {"knowledge_point": key, "count": count}
                for key, count in knowledge_counts.most_common(8)
            ],
            "recent_error_count": len(errors),
            "diagnosis_signals": [
                {"knowledge_point": key, "error_count": count}
                for key, count in Counter(
                    item.knowledge_point for item in errors if item.knowledge_point
                ).items()
                if count >= 3
            ],
        }
        await self.profile_service.update_profile(user_id, {"recent_learning_summary": summary})
        return summary

    async def capture_agent_response(
        self, request: AgentRequest, response: AgentResponse
    ) -> list[LearningEvent]:
        candidates: list[LearningEvent] = []
        for message in response.messages:
            if message.message_type == MessageType.EVENT:
                candidates.extend(self._from_message(request, response, message))
        candidates.extend(self._from_result(request, response))
        emitted: list[LearningEvent] = []
        seen: set[str] = set()
        for event in candidates:
            key = (
                f"{event.event_type}:{event.knowledge_point}:"
                f"{event.metadata.get('source_item_id', '')}"
            )
            if key in seen:
                continue
            seen.add(key)
            emitted.append(await self.emit(event))
        return emitted

    async def capture_english_reading_bank_submission(
        self, user_id: str, result: dict[str, Any], *, trace_id: str | None = None
    ) -> list[LearningEvent]:
        reading = result.get("reading", {})
        progress = result.get("progress", {})
        reading_id = str(reading.get("reading_id") or progress.get("reading_id") or "")
        session_id = str(progress.get("session_id") or "") or None
        events: list[LearningEvent] = []
        for item in result.get("results", []):
            question_id = str(item.get("question_id") or "")
            correct = bool(item.get("is_correct"))
            stable = f"english_bank|{user_id}|{reading_id}|{session_id}|{question_id}"
            event = LearningEvent(
                event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
                event_type=(
                    LearningEventType.QUESTION_CORRECT
                    if correct
                    else LearningEventType.READING_ERROR
                ),
                user_id=user_id,
                agent=AgentRole.ENGLISH_READING_LANGUAGE,
                subject="foreign_language",
                knowledge_point="reading.comprehension",
                difficulty=0.55,
                score=1.0 if correct else 0.0,
                confidence=0.9,
                session_id=session_id,
                trace_id=trace_id,
                metadata={
                    "source_item_id": question_id,
                    "reading_id": reading_id,
                    "reading_title": reading.get("title"),
                    "question_type": "reading_comprehension",
                    "error_type": None if correct else "reading_error",
                },
            )
            await self.emit(event)
            events.append(event)
        return events

    async def capture_english_language_analysis(
        self,
        user_id: str,
        text: str,
        mode: str,
        result: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> list[LearningEvent]:
        if mode != "grammar":
            return []
        grammar = result.get("grammar", {})
        issues = list(grammar.get("issues") or [])
        if not grammar.get("is_complete_sentence") and not issues:
            issues = [
                {
                    "issue_type": "sentence_fragment",
                    "explanation": grammar.get("overall_feedback"),
                }
            ]
        emitted: list[LearningEvent] = []
        text_key = hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]
        for index, issue in enumerate(issues):
            issue_type = str(issue.get("issue_type") or "grammar_general")
            stable = f"english_grammar|{user_id}|{text_key}|{index}|{issue_type}"
            event = LearningEvent(
                event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
                event_type=LearningEventType.GRAMMAR_ERROR,
                user_id=user_id,
                agent=AgentRole.ENGLISH_READING_LANGUAGE,
                subject="foreign_language",
                knowledge_point=f"grammar.{issue_type}",
                score=0.0,
                confidence=0.75,
                trace_id=trace_id,
                metadata={
                    "source_item_id": text_key,
                    "error_type": issue_type,
                    "question_type": "grammar_correction",
                    "source_reliability": 0.75,
                    "assessment_independence_key": text_key,
                },
            )
            await self.emit(event)
            emitted.append(event)
        return emitted

    async def capture_english_grammar_training(
        self,
        user_id: str,
        result: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> list[LearningEvent]:
        session_id = str(result.get("session_id") or "") or None
        questions = {str(item.get("question_id")): item for item in result.get("questions", [])}
        emitted: list[LearningEvent] = []
        assessment = result.get("assessment") or {}
        for item in assessment.get("feedback") or []:
            question_id = str(item.get("question_id") or "")
            correct = bool(item.get("is_correct"))
            raw_score = max(0.0, min(100.0, float(item.get("score") or 0)))
            focus = str(questions.get(question_id, {}).get("grammar_focus") or "general")
            defect = str(item.get("defect_tag") or "").strip()
            knowledge = defect if not correct and defect else focus
            stable = f"english_grammar_training|{user_id}|{session_id}|{question_id}"
            event = LearningEvent(
                event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
                event_type=(
                    LearningEventType.QUESTION_CORRECT
                    if correct
                    else LearningEventType.GRAMMAR_ERROR
                ),
                user_id=user_id,
                agent=AgentRole.ENGLISH_READING_LANGUAGE,
                subject="foreign_language",
                knowledge_point=f"grammar.{knowledge}",
                difficulty=0.62,
                score=raw_score / 100,
                confidence=0.85,
                session_id=session_id,
                trace_id=trace_id,
                metadata={
                    "source_item_id": question_id,
                    "error_type": None if correct else knowledge,
                    "question_type": "ai_grammar_training",
                    "source_reliability": 0.85,
                    "assessment_independence_key": stable,
                },
            )
            await self.emit(event)
            emitted.append(event)
        return emitted

    async def capture_english_speaking_assessment(
        self,
        user_id: str,
        result: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> list[LearningEvent]:
        assessment = result.get("assessment", {})
        scores = assessment.get("scores") or {}
        transcript = str(result.get("transcript") or "")
        source = f"{result.get('topic')}|{transcript}"
        source_key = hashlib.sha256(source.encode()).hexdigest()[:16]
        emitted: list[LearningEvent] = []
        for dimension, raw_score in scores.items():
            score = max(0.0, min(1.0, float(raw_score) / 100.0))
            stable = f"english_speaking|{user_id}|{source_key}|{dimension}"
            event = LearningEvent(
                event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
                event_type=(
                    LearningEventType.SKILL_SCORE
                    if score >= 0.8
                    else LearningEventType.SPEAKING_ERROR
                ),
                user_id=user_id,
                agent=AgentRole.ENGLISH_READING_LANGUAGE,
                subject="foreign_language",
                knowledge_point=f"speaking.{dimension}",
                score=score,
                difficulty=0.55,
                confidence=0.7,
                trace_id=trace_id,
                metadata={
                    "source_item_id": source_key,
                    "error_type": dimension if score < 0.8 else None,
                    "question_type": "speaking_assessment",
                    "source_reliability": 0.7,
                    "assessment_independence_key": source_key,
                },
            )
            await self.emit(event)
            emitted.append(event)
        return emitted

    async def capture_career_profile_snapshot(
        self,
        user_id: str,
        profile: dict[str, Any] | None,
        *,
        trace_id: str | None = None,
    ) -> LearningEvent | None:
        if not profile or profile.get("career_spec_version") != "1.0":
            return None
        event = self._career_profile_event(user_id, profile, trace_id=trace_id)
        await self.emit(event)
        return event

    def _from_message(
        self, request: AgentRequest, response: AgentResponse, message: AgentMessage
    ) -> list[LearningEvent]:
        payload = message.payload
        if payload.get("event_name") == "homework.knowledge_evidence.created":
            verification = str(payload.get("verification_result", "uncertain")).lower()
            if verification in {"uncertain", "model_review_without_unique_rubric"}:
                return []
            correct = verification in {"correct", "verified_correct", "passed"}
            return [
                self._event(
                    request,
                    response.agent_role,
                    LearningEventType.QUESTION_CORRECT
                    if correct
                    else LearningEventType.QUESTION_WRONG,
                    subject=self._value(payload.get("subject")),
                    knowledge_point=str(knowledge_id),
                    score=1.0 if correct else 0.0,
                    difficulty=self._number(payload.get("difficulty")),
                    confidence=self._number(payload.get("evidence_quality"), 0.7),
                    source_item_id=str(payload.get("question_id", "")),
                    metadata={"verification_result": verification, "legacy_event": payload},
                )
                for knowledge_id in payload.get("knowledge_ids", [])
            ]
        if payload.get("event_type") == "learning_state.updated":
            return [
                self._event(
                    request,
                    response.agent_role,
                    LearningEventType.KNOWLEDGE_WEAK,
                    subject=str(payload.get("subject") or "general"),
                    knowledge_point=str(item),
                    score=0.4,
                    confidence=0.8,
                    source_item_id=str(payload.get("diagnosis_id", "")),
                    metadata={"legacy_event": payload},
                )
                for item in payload.get("weak_dimensions", [])
            ]
        return []

    def _from_result(self, request: AgentRequest, response: AgentResponse) -> list[LearningEvent]:
        result = response.result
        events: list[LearningEvent] = []
        if response.agent_role == AgentRole.ENGLISH_READING_LANGUAGE:
            attempt = result.get("attempt", {})
            for item in attempt.get("results", []):
                correct = bool(item.get("is_correct"))
                events.append(
                    self._event(
                        request,
                        response.agent_role,
                        LearningEventType.QUESTION_CORRECT
                        if correct
                        else LearningEventType.READING_ERROR,
                        subject="foreign_language",
                        knowledge_point=f"reading.{item.get('skill', 'general')}",
                        score=1.0 if correct else 0.0,
                        confidence=self._number(item.get("evidence_weight"), 0.7),
                        source_item_id=str(item.get("question_id", "")),
                        metadata={"error_type": item.get("error_type")},
                    )
                )
            learning_record = result.get("learning_record", {})
            for item in learning_record.get("grammar_updates", []):
                events.append(
                    self._event(
                        request,
                        response.agent_role,
                        LearningEventType.GRAMMAR_ERROR,
                        subject="foreign_language",
                        knowledge_point=f"grammar.{item.get('grammar_key', 'general')}",
                        score=self._number(item.get("mastery_score"), 0.0),
                        confidence=self._number(item.get("confidence"), 0.6),
                        source_item_id=str(learning_record.get("event_id", "")),
                        metadata={
                            "error_type": item.get("grammar_key"),
                            "stable_weakness": item.get("stable_weakness", False),
                            "example_error": item.get("example_error"),
                        },
                    )
                )
            if result.get("task", {}).get("primary_intent") == "writing_revision":
                source_id = str(learning_record.get("event_id") or request.request_id)
                for dimension, raw_score in (result.get("answer", {}).get("scores") or {}).items():
                    if raw_score is None:
                        continue
                    score = max(0.0, min(100.0, float(raw_score))) / 100
                    events.append(
                        self._event(
                            request,
                            response.agent_role,
                            LearningEventType.SKILL_SCORE
                            if score >= 0.75
                            else LearningEventType.WRITING_ERROR,
                            subject="foreign_language",
                            knowledge_point=f"writing.{dimension}",
                            score=score,
                            difficulty=0.65,
                            confidence=0.8,
                            source_item_id=source_id,
                            metadata={
                                "error_type": None if score >= 0.75 else f"writing_{dimension}",
                                "question_type": "ai_writing_assessment",
                                "source_reliability": 0.8,
                            },
                        )
                    )
        if response.agent_role == AgentRole.PROGRAMMING_LEARNING:
            source_id = str(
                result.get("evaluation_id")
                or result.get("submission_id")
                or result.get("question_id")
                or ""
            )
            if result.get("total_score") is not None:
                score = self._number(result.get("total_score"), 0.0) or 0.0
                score = score / 100.0 if score > 1 else score
                skill_updates = result.get("skill_updates") or [{"skill_id": "project.general"}]
                for item in skill_updates:
                    skill_id = str(item.get("skill_id") or "project.general")
                    events.append(
                        self._event(
                            request,
                            response.agent_role,
                            LearningEventType.PROJECT_SCORE,
                            subject="technology",
                            knowledge_point=f"programming.{skill_id}",
                            score=score,
                            difficulty=0.75,
                            confidence=0.8,
                            source_item_id=source_id,
                            metadata={
                                "error_type": None if score >= 0.6 else "project_skill_gap",
                                "question_type": "project_evaluation",
                                "source_reliability": 0.8,
                            },
                        )
                    )
            elif result.get("judge_result") and result.get("action") == "submit":
                judge = result.get("judge_result") or {}
                score = float(judge.get("passed") or 0) / max(1, int(judge.get("total") or 1))
                skills = (result.get("feedback") or {}).get("related_skills") or ["coding.general"]
                for skill_id in skills:
                    events.append(
                        self._event(
                            request,
                            response.agent_role,
                            LearningEventType.SKILL_SCORE,
                            subject="technology",
                            knowledge_point=f"programming.{skill_id}",
                            score=score,
                            difficulty=0.65,
                            confidence=0.95,
                            source_item_id=source_id,
                            metadata={
                                "error_type": (result.get("feedback") or {}).get("error_type"),
                                "question_type": "coding_judge",
                                "hint_level": result.get("hint_level", 0),
                                "source_reliability": 0.95,
                            },
                        )
                    )
            elif result.get("score_percent") is not None:
                score = float(result.get("score_percent") or 0) / 100.0
                events.append(
                    self._event(
                        request,
                        response.agent_role,
                        LearningEventType.SKILL_SCORE,
                        subject="technology",
                        knowledge_point="programming.gaokao_programming",
                        score=score,
                        difficulty=0.8,
                        confidence=0.85,
                        source_item_id=source_id,
                        metadata={
                            "error_type": "gaokao_programming_error" if score < 0.6 else None,
                            "question_type": "gaokao_programming",
                            "source_reliability": 0.85,
                        },
                    )
                )
            career_profile = (
                (result.get("profile") or result) if result.get("configured") else result
            )
            if career_profile.get("career_spec_version") == "1.0":
                events.append(
                    self._career_profile_event(
                        request.student_id,
                        career_profile,
                        trace_id=request.trace_id,
                        session_id=str(request.context.get("session_id") or "") or None,
                    )
                )
        if response.agent_role == AgentRole.LEARNING_DIAGNOSIS:
            diagnosis_event = result.get("diagnosis_event", {})
            if diagnosis_event:
                events.append(
                    self._event(
                        request,
                        response.agent_role,
                        LearningEventType.DIAGNOSIS_UPDATED,
                        subject=str(diagnosis_event.get("subject") or "general"),
                        confidence=0.85,
                        source_item_id=str(diagnosis_event.get("diagnosis_id", "")),
                        metadata=diagnosis_event,
                    )
                )
        if response.agent_role == AgentRole.PERSONALIZED_LEARNING_PLANNER:
            plan = result.get("plan")
            if plan:
                events.append(
                    self._event(
                        request,
                        response.agent_role,
                        LearningEventType.PLAN_UPDATED,
                        subject=None,
                        confidence=1.0,
                        source_item_id=str(plan.get("plan_id", "")),
                        metadata={
                            "plan_id": plan.get("plan_id"),
                            "version": plan.get("version"),
                            "status": plan.get("status"),
                        },
                    )
                )
        return events

    def _event(
        self,
        request: AgentRequest,
        agent: AgentRole,
        event_type: LearningEventType,
        *,
        subject: str | None,
        knowledge_point: str | None = None,
        score: float | None = None,
        difficulty: float | None = None,
        confidence: float = 1.0,
        source_item_id: str,
        metadata: dict[str, Any],
    ) -> LearningEvent:
        stable = "|".join(
            (
                request.idempotency_key or request.request_id,
                event_type.value,
                knowledge_point or "",
                source_item_id,
            )
        )
        return LearningEvent(
            event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
            event_type=event_type,
            user_id=request.student_id,
            agent=agent,
            subject=subject,
            knowledge_point=knowledge_point,
            difficulty=difficulty,
            score=score,
            confidence=max(0.0, min(1.0, confidence)),
            session_id=str(request.context.get("session_id") or "") or None,
            trace_id=request.trace_id,
            metadata={**metadata, "source_item_id": source_item_id},
        )

    @staticmethod
    def _career_profile_event(
        user_id: str,
        profile: dict[str, Any],
        *,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> LearningEvent:
        version = max(1, int(profile.get("profile_version") or 1))
        stable = f"career_profile|{user_id}|{version}"
        source_item_id = f"career_profile_v{version}"
        return LearningEvent(
            event_id=f"learn_evt_{hashlib.sha256(stable.encode()).hexdigest()[:20]}",
            event_type=LearningEventType.CAREER_PROFILE_UPDATED,
            user_id=user_id,
            agent=AgentRole.PROGRAMMING_LEARNING,
            subject="technology",
            confidence=1.0,
            session_id=session_id,
            trace_id=trace_id,
            metadata={
                "source_item_id": source_item_id,
                "question_type": "career_profile",
                "target_job_id": profile.get("target_job_id"),
                "programming_level": profile.get("programming_level"),
                "known_languages": profile.get("known_languages") or [],
                "weekly_hours": profile.get("weekly_hours"),
                "learning_goal": profile.get("learning_goal"),
                "target_period_weeks": profile.get("target_period_weeks"),
                "source_reliability": 1.0,
            },
        )

    @staticmethod
    def _number(value: Any, default: float | None = None) -> float | None:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _value(value: Any) -> str:
        return str(getattr(value, "value", value) or "general")
