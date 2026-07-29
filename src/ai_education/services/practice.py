"""Practice-event cleaning, feature extraction and conservative mastery updates."""

from __future__ import annotations

from ai_education.domain.models import KnowledgeProfile, PracticeEvent, PracticeUpdate
from ai_education.repositories import PlannerRepository
from ai_education.services.knowledge import mastery_level

ERROR_TYPES = {
    "knowledge_missing",
    "concept_confusion",
    "method_selection_error",
    "procedure_error",
    "calculation_error",
    "reading_error",
    "careless_error",
    "representation_error",
    "time_pressure_error",
    "answer_format_error",
    "unknown",
}


class PracticeService:
    def __init__(self, repository: PlannerRepository) -> None:
        self.repository = repository

    def ingest(self, event: PracticeEvent) -> PracticeUpdate:
        identity = event.idempotency_key or event.event_id
        if identity in self.repository.processed_event_ids:
            return PracticeUpdate(event_id=event.event_id, duplicate=True)

        behavior = event.behavior
        elapsed = max(int(behavior.get("response_time_seconds", 0)), 0)
        pause = max(int(behavior.get("pause_seconds", 0)), 0)
        unfocused = max(int(behavior.get("unfocused_seconds", 0)), 0)
        effective_seconds = max(min(elapsed - pause - unfocused, 3600), 0)
        anomalies: list[str] = []
        minimum_seconds = max(int(behavior.get("minimum_reasonable_seconds", 8)), 1)
        if effective_seconds < minimum_seconds:
            anomalies.append("rapid_guessing")
        if elapsed > 7200:
            anomalies.append("excessive_idle_time")
        if behavior.get("answer_viewed_before_submit"):
            anomalies.append("answer_dependency")

        score = float(event.response.get("score", 1 if event.response.get("correct") else 0))
        max_score = max(float(event.response.get("max_score", 1)), 1)
        accuracy = min(max(score / max_score, 0), 1)
        difficulty = min(max(float(event.response.get("difficulty", 0.5)), 0), 1)
        difficulty_adjusted = min(1.0, accuracy * (0.7 + 0.6 * difficulty))
        expected_seconds = max(float(behavior.get("expected_time_seconds", 300)), 1)
        speed = max(0.0, 1 - abs(effective_seconds - expected_seconds) / expected_seconds)
        hint_dependency = min(int(behavior.get("hint_count", 0)) / 3, 1)
        attempts = max(int(behavior.get("attempt_count", 1)), 1)
        retry_dependency = min((attempts - 1) / 3, 1)
        independent = max(0, 1 - hint_dependency * 0.6 - retry_dependency * 0.3)
        if "answer_dependency" in anomalies:
            independent *= 0.35
        process_quality = float(event.response.get("solution_process_quality", 0.5))
        quality = (
            0.25 * difficulty_adjusted
            + 0.15 * speed
            + 0.15 * independent
            + 0.15 * float(event.response.get("performance_stability", 0.5))
            + 0.10 * float(event.response.get("retention_score", 0.5))
            + 0.10 * float(event.response.get("transfer_score", 0.5))
            + 0.10 * process_quality
        )
        reliability = 0.4 if anomalies else 0.9
        evidence_weight = (
            reliability
            * float(event.response.get("item_discrimination", 0.7))
            * (0.6 + difficulty * 0.4)
            * independent
            * float(event.response.get("freshness_weight", 1.0))
            * float(event.response.get("exam_relevance", 0.7))
        )
        error_type = self._classify_error(event, accuracy)
        updates = self._update_mastery(event, quality, evidence_weight, error_type)
        self.repository.processed_event_ids.add(identity)
        # One event may request a rule check, but never directly triggers a broad replan.
        replan_check = any(abs(float(item["change"])) >= 0.10 for item in updates)
        return PracticeUpdate(
            event_id=event.event_id,
            anomaly_tags=anomalies,
            effective_seconds=effective_seconds,
            quality_score=round(min(max(quality, 0), 1), 3),
            evidence_weight=round(min(max(evidence_weight, 0), 1), 3),
            error_type=error_type,
            mastery_updates=updates,
            replan_check_required=replan_check,
        )

    def _classify_error(self, event: PracticeEvent, accuracy: float) -> str | None:
        if accuracy >= 1:
            return None
        provided = str(event.response.get("error_type", "unknown"))
        if provided in ERROR_TYPES:
            return provided
        if event.behavior.get("time_pressure"):
            return "time_pressure_error"
        if event.response.get("calculation_correct") is False:
            return "calculation_error"
        return "unknown"

    def _update_mastery(
        self,
        event: PracticeEvent,
        quality: float,
        evidence_weight: float,
        error_type: str | None,
    ) -> list[dict[str, float | str]]:
        profile: KnowledgeProfile | None = self.repository.knowledge_profiles.get(event.student_id)
        if not profile:
            return []
        by_id = {state.knowledge_id: state for state in profile.knowledge_states}
        updates: list[dict[str, float | str]] = []
        for knowledge_id in event.knowledge_ids:
            state = by_id.get(knowledge_id)
            if not state:
                continue
            old = state.mastery_probability
            # Conservative weighted update prevents one ordinary error changing the profile sharply.
            learning_rate = min(0.18 * evidence_weight, 0.12)
            new = old + learning_rate * (quality - old)
            new = min(max(new, 0), 1)
            state.mastery_probability = round(new, 3)
            state.mastery_level = mastery_level(new)
            state.evidence_count += 1
            state.last_practiced_at = event.timestamp
            state.confidence = round(min(0.98, state.confidence + 0.02 * evidence_weight), 3)
            if error_type and error_type not in state.error_tags:
                state.error_tags.append(error_type)
            updates.append(
                {
                    "knowledge_id": knowledge_id,
                    "old_mastery": old,
                    "new_mastery": state.mastery_probability,
                    "change": round(state.mastery_probability - old, 3),
                    "confidence": state.confidence,
                    "trend": "improving" if new > old else "declining" if new < old else "stable",
                }
            )
        self.repository.save_knowledge_profile(profile)
        return updates
