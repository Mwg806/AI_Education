"""Evidence-weighted cold-start and ongoing knowledge profiling."""

from __future__ import annotations

from datetime import datetime
from math import sqrt
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
                source_type = str(item.get("source_type", "self_assessment"))
                requested_weight = float(item.get("weight", 0.5))
                weight = (
                    min(requested_weight, 0.15)
                    if source_type in {"self_assessment", "student_self_assessment"}
                    else requested_weight
                )
                score = float(item.get("score", item.get("correct", 0.5)))
                weighted_sum += min(max(score, 0), 1) * weight
                total_weight += weight
                evidence.append(
                    Evidence(
                        source_type=source_type,
                        source_id=str(item.get("source_id", knowledge_id)),
                        description=str(item.get("description", "初始学习证据")),
                        confidence=min(max(weight, 0), 1),
                    )
                )
            smoothed = (weighted_sum + 0.5) / (total_weight + 1.0)
            self_types = {"self_assessment", "student_self_assessment"}
            objective_items = [
                item for item in items if str(item.get("source_type", "")) not in self_types
            ]
            self_items = [item for item in items if str(item.get("source_type", "")) in self_types]
            objective_count = len(objective_items)
            self_count = len(self_items)
            objective_weight = sum(float(item.get("weight", 0.5)) for item in objective_items)
            source_diversity = len(
                {str(item.get("source_type", "unknown")) for item in objective_items}
            )
            if objective_count:
                confidence = min(
                    0.95,
                    0.18
                    + min(objective_count, 8) * 0.06
                    + min(objective_weight, 4) * 0.05
                    + min(source_diversity, 3) * 0.03,
                )
            else:
                confidence = min(0.4, 0.18 + self_count * 0.04)
            radius = max(0.07, 0.32 / sqrt(1 + objective_count + total_weight))
            objective_average = (
                sum(float(item.get("score", 0.5)) for item in objective_items) / objective_count
                if objective_count
                else None
            )
            self_average = (
                sum(float(item.get("score", 0.5)) for item in self_items) / self_count
                if self_count
                else None
            )
            calibration_bias = (
                self_average - objective_average
                if self_average is not None and objective_average is not None
                else None
            )
            states.append(
                KnowledgeState(
                    student_id=student_id,
                    subject=subject,
                    knowledge_id=knowledge_id,
                    mastery_probability=round(smoothed, 3),
                    mastery_level=mastery_level(smoothed),
                    confidence=round(confidence, 3),
                    evidence_count=len(items),
                    objective_evidence_count=objective_count,
                    self_report_evidence_count=self_count,
                    credible_interval_low=round(max(0, smoothed - radius), 3),
                    credible_interval_high=round(min(1, smoothed + radius), 3),
                    calibration_bias=round(calibration_bias, 3)
                    if calibration_bias is not None
                    else None,
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
        objective_count = sum(state.objective_evidence_count for state in states)
        self_report_count = sum(state.self_report_evidence_count for state in states)
        coverage = min(1.0, len(states) / 2)
        avg_confidence = sum(state.confidence for state in states) / len(states) if states else 0
        biases = [state.calibration_bias for state in states if state.calibration_bias is not None]
        calibration_gap = sum(abs(value) for value in biases) / len(biases) if biases else 0
        objective_ratio = objective_count / count if count else 0
        breadth_aware_objective_evidence = objective_count >= 8 and objective_ratio >= 0.8
        sufficient = (
            objective_count >= 8
            and coverage >= 0.8
            and (avg_confidence >= 0.6 or breadth_aware_objective_evidence)
        )
        mode = "quick" if sufficient else "standard" if objective_count >= 4 else "full"
        return KnowledgeProfile(
            student_id=student_id,
            knowledge_states=states,
            priority_gaps=gap_ids,
            prerequisite_gaps=prerequisite_gaps,
            assessment_quality={
                "coverage": round(coverage, 3),
                "confidence": round(avg_confidence, 3),
                "objective_evidence_count": float(objective_count),
                "self_report_evidence_count": float(self_report_count),
                "objective_evidence_ratio": round(objective_ratio, 3),
                "calibration_gap": round(calibration_gap, 3),
                "evidence_sufficient": 1.0 if sufficient else 0.0,
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
