"""Evidence-weighted cold-start and ongoing knowledge profiling."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_education.domain.enums import Subject
from ai_education.domain.models import KnowledgeProfile, KnowledgeState
from ai_education.domain.protocols import Evidence


def mastery_level(value: float) -> str:
    if value < 0.30:
        return "emerging"
    if value < 0.50:
        return "developing"
    if value < 0.70:
        return "developing"
    if value < 0.85:
        return "proficient"
    return "mastered"


class KnowledgeService:
    def build_profile(
        self,
        student_id: str,
        subject: Subject,
        evidence_items: list[dict[str, Any]],
        *,
        prerequisite_edges: list[dict[str, Any]] | None = None,
    ) -> KnowledgeProfile:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in evidence_items:
            grouped.setdefault(str(item["knowledge_id"]), []).append(item)
        states: list[KnowledgeState] = []
        for knowledge_id, items in grouped.items():
            weighted_sum = 0.0
            total_weight = 0.0
            evidence: list[Evidence] = []
            for item in items:
                weight = float(item.get("weight", 0.5))
                score = float(item.get("score", item.get("correct", 0.5)))
                weighted_sum += min(max(score, 0), 1) * weight
                total_weight += weight
                evidence.append(
                    Evidence(
                        source_type=str(item.get("source_type", "self_assessment")),
                        source_id=str(item.get("source_id", knowledge_id)),
                        description=str(item.get("description", "初始学习证据")),
                        confidence=min(max(weight, 0), 1),
                    )
                )
            smoothed = (weighted_sum + 0.5) / (total_weight + 1.0)
            confidence = min(0.95, 0.35 + len(items) * 0.07 + min(total_weight, 4) * 0.08)
            states.append(
                KnowledgeState(
                    student_id=student_id,
                    subject=subject,
                    knowledge_id=knowledge_id,
                    mastery_probability=round(smoothed, 3),
                    mastery_level=mastery_level(smoothed),
                    confidence=round(confidence, 3),
                    evidence_count=len(items),
                    last_practiced_at=self._latest_time(items),
                    forgetting_risk=0.3 if len(items) >= 3 else 0.55,
                    prerequisite_status="unknown",
                    error_tags=sorted(
                        {str(tag) for item in items for tag in item.get("error_tags", [])}
                    ),
                    evidence=evidence,
                )
            )
        prerequisite_gaps = self.prerequisite_gaps(states, prerequisite_edges or [])
        gap_ids = [
            state.knowledge_id
            for state in sorted(states, key=lambda state: state.mastery_probability)
            if state.mastery_probability < 0.7
        ]
        count = sum(state.evidence_count for state in states)
        coverage = min(1.0, len(states) / max(len(states), 3))
        avg_confidence = sum(state.confidence for state in states) / len(states) if states else 0
        mode = (
            "quick"
            if count >= 24 and avg_confidence >= 0.8
            else "standard"
            if count >= 8
            else "full"
        )
        return KnowledgeProfile(
            student_id=student_id,
            knowledge_states=states,
            priority_gaps=gap_ids,
            prerequisite_gaps=prerequisite_gaps,
            assessment_quality={
                "coverage": round(coverage, 3),
                "confidence": round(avg_confidence, 3),
            },
            assessment_mode=mode,
            exam_skill_states=[
                {"metric": "time_allocation_stability", "value": 0.5, "confidence": 0.3},
                {"metric": "avoidable_error_rate", "value": 0.0, "confidence": 0.2},
            ],
        )

    def evidence_sufficient(self, state: KnowledgeState) -> bool:
        return (
            state.evidence_count >= 8
            and state.confidence >= 0.8
            and state.forgetting_risk < 0.5
            and state.last_practiced_at is not None
            and (datetime.now().astimezone() - state.last_practiced_at).days <= 30
        )

    def prerequisite_gaps(
        self,
        states: list[KnowledgeState],
        edges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_id = {state.knowledge_id: state for state in states}
        gaps = []
        for edge in edges:
            prerequisite = by_id.get(str(edge.get("prerequisite")))
            target = by_id.get(str(edge.get("target")))
            strength = float(edge.get("strength", 1.0))
            if prerequisite and target and prerequisite.mastery_probability < 0.6:
                risk = (
                    strength
                    * (1 - prerequisite.mastery_probability)
                    * (1 + target.mastery_probability)
                    / 2
                )
                gaps.append(
                    {
                        "knowledge_id": prerequisite.knowledge_id,
                        "target_knowledge_id": target.knowledge_id,
                        "relationship": "direct_prerequisite",
                        "current_mastery": prerequisite.mastery_probability,
                        "gap_risk": round(min(risk, 1), 3),
                    }
                )
        return sorted(gaps, key=lambda item: item["gap_risk"], reverse=True)

    @staticmethod
    def _latest_time(items: list[dict[str, Any]]) -> datetime | None:
        times = [item.get("observed_at") for item in items if item.get("observed_at")]
        if not times:
            return None
        parsed = [
            value if isinstance(value, datetime) else datetime.fromisoformat(value)
            for value in times
        ]
        return max(parsed)
