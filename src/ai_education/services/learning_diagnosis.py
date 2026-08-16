"""Deterministic, evidence-gated learning-state inference service."""

from __future__ import annotations

from collections import defaultdict
from statistics import pstdev
from typing import Callable, Iterable

from ai_education.domain.diagnosis import (
    CauseHypothesis,
    DimensionState,
    ErrorPattern,
    EvidenceGate,
    LearningEvidenceRecord,
    LearningStateDiagnosis,
)


SOURCE_RELIABILITY = {
    "formal_exam": 0.96,
    "mock_exam": 0.92,
    "diagnostic": 0.86,
    "homework": 0.72,
    "practice": 0.64,
    "teacher_evaluation": 0.82,
    "agent_feedback": 0.66,
}

ERROR_LABELS = {
    "concept_confusion": "概念边界混淆",
    "formula_misuse": "公式适用条件使用不稳",
    "calculation_error": "运算过程失误",
    "condition_omission": "条件遗漏",
    "representation_error": "表征转换受阻",
    "reasoning_gap": "推理链缺口",
    "time_pressure": "限时状态下完成不稳",
    "reading_error": "题意或关键信息提取偏差",
    "incorrect_option": "选择题未得分",
    "constructed_response_gap": "主观题作答存在得分缺口",
    "diagnostic_incorrect": "诊断题未得分",
    "grammar_structure": "语法结构运用不稳",
    "learning_error": "学习任务作答失误",
}

CAUSE_MAP = {
    "concept_confusion": ("相关概念的边界辨析可能尚不稳定", "补充 2 道同概念、不同表述的解释型题，并记录理由"),
    "formula_misuse": ("可能没有稳定检查公式适用条件", "补充含反例的公式条件辨析题并保留步骤"),
    "calculation_error": ("运算检查流程可能尚未形成稳定证据", "补充同知识点限时与不限时各 2 题，比较过程记录"),
    "condition_omission": ("条件提取与回检环节可能存在缺口", "补充需要显式列出条件的题目并记录审题标注"),
    "representation_error": ("文字、图形与符号之间的转换可能不稳定", "补充两种不同表征的等价任务并记录转换步骤"),
    "reasoning_gap": ("关键推理依据的表达可能不完整", "补充要求逐步说明依据的题目，由教师复核过程"),
    "time_pressure": ("当前错误可能与限时负荷有关", "对同类题进行一次不限时和一次限时复测"),
    "reading_error": ("题干信息提取可能不稳定", "补充题干改写与关键信息标注任务"),
}


class LearningDiagnosisService:
    """Build versioned state while keeping facts, patterns and hypotheses separate."""

    def blueprint_version(self, subject: str, target_exam_year: int) -> str:
        return f"{subject}_national_new_curriculum_v1_{target_exam_year}"

    def normalize(self, records: Iterable[LearningEvidenceRecord]) -> list[LearningEvidenceRecord]:
        normalized: list[LearningEvidenceRecord] = []
        for record in records:
            flags = list(record.quality_flags)
            if record.duration_seconds is not None and record.duration_seconds < 8:
                flags.append("abnormally_fast")
            if record.duration_seconds is not None and record.duration_seconds > 7_200:
                flags.append("abnormally_slow")
            if not record.ability_tags:
                flags.append("ability_tag_missing")
            reliability = record.source_reliability or SOURCE_RELIABILITY[record.assessment_type]
            penalty = 0.82 if any(flag.startswith("abnormally") for flag in flags) else 1.0
            weight = max(0.0, min(1.0, reliability * penalty))
            normalized.append(record.model_copy(update={
                "source_id": record.source_id or f"{record.assessment_id}:{record.question_id}",
                "source_reliability": reliability,
                "evidence_weight": weight,
                "quality_flags": list(dict.fromkeys(flags)),
            }))
        return normalized

    def gate(self, records: list[LearningEvidenceRecord], rejected: int = 0) -> EvidenceGate:
        valid = [item for item in records if item.evidence_weight >= 0.4]
        assessments = {item.assessment_id for item in valid}
        question_types = {item.question_type for item in valid}
        bands = {"low" if item.difficulty < 0.4 else "medium" if item.difficulty < 0.7 else "high" for item in valid}
        scores = [item.normalized_score for item in valid]
        consistency = 1.0 if len(scores) < 2 else max(0.0, min(1.0, 1 - pstdev(scores) * 1.6))
        coverage = min(1.0, (len(question_types) / 3) * 0.55 + (len(bands) / 3) * 0.45)
        if len(valid) >= 5 and len(assessments) >= 2 and len(question_types) >= 2:
            level = "stable"
            allowed = "可形成有置信区间的当前状态，并识别跨测次稳定模式"
        elif len(valid) >= 3 and len(assessments) >= 2:
            level = "preliminary"
            allowed = "只形成初步状态，不将薄弱点或原因写成稳定结论"
        else:
            level = "insufficient"
            allowed = "仅报告已观察事实与证据缺口，不形成稳定掌握度结论"
        missing: list[str] = []
        if len(valid) < 3:
            missing.append(f"至少还需 {3 - len(valid)} 条有效作答证据以形成初步判断")
        if len(assessments) < 2:
            missing.append("需要来自至少 2 个独立测次或不同日期的证据")
        if len(question_types) < 2:
            missing.append("需要至少覆盖 2 种题型，避免单一题型偏差")
        if len(bands) < 2:
            missing.append("建议补充不同难度层级的题目")
        return EvidenceGate(
            valid_evidence_count=len(valid), rejected_evidence_count=rejected,
            independent_assessment_count=len(assessments), question_type_count=len(question_types),
            difficulty_band_count=len(bands), coverage_score=round(coverage, 3),
            consistency_score=round(consistency, 3), sufficiency_level=level,
            allowed_conclusion=allowed, missing_evidence=missing,
        )

    def infer(
        self,
        *,
        student_id: str,
        subject: str,
        target_exam_year: int,
        records: list[LearningEvidenceRecord],
        previous: LearningStateDiagnosis | None = None,
        rejected: int = 0,
    ) -> LearningStateDiagnosis:
        gate = self.gate(records, rejected)
        knowledge = self._dimension_states(records, lambda item: item.knowledge_tags, previous.knowledge_states if previous else [])
        question_types = self._dimension_states(records, lambda item: [item.question_type], previous.question_type_states if previous else [])
        abilities = self._dimension_states(records, lambda item: item.ability_tags, previous.ability_states if previous else [])
        facts = self._facts(records, gate)
        patterns = self._patterns(records)
        hypotheses = self._hypotheses(records, patterns)
        review_required = gate.valid_evidence_count >= 5 and gate.consistency_score < 0.45
        status = (
            "review_required"
            if review_required
            else "insufficient_evidence"
            if gate.sufficiency_level == "insufficient"
            else gate.sufficiency_level
        )
        missing = list(gate.missing_evidence)
        weak_dimensions = [item.dimension_id for item in knowledge if item.mastery_level in {"needs_support", "developing"}]
        reassessment = {
            "purpose": "验证当前初步结论并提高证据独立性",
            "target_dimensions": weak_dimensions[:3] or [item.dimension_id for item in knowledge[:2]],
            "recommended_item_count": max(3, min(8, 8 - gate.valid_evidence_count)),
            "required_question_type_count": max(2, 3 - gate.question_type_count),
            "process_data_required": bool(patterns),
            "do_not_reuse_assessment_ids": sorted({item.assessment_id for item in records}),
        }
        return LearningStateDiagnosis(
            student_id=student_id,
            subject=subject,
            blueprint_version=self.blueprint_version(subject, target_exam_year),
            diagnosis_status=status,
            evidence_gate=gate,
            knowledge_states=knowledge,
            question_type_states=question_types,
            ability_states=abilities,
            observed_facts=facts,
            stable_error_patterns=patterns,
            cause_hypotheses=hypotheses,
            missing_evidence=missing,
            reassessment_spec=reassessment,
            review_status="pending" if review_required else "not_required",
        )

    def _dimension_states(
        self,
        records: list[LearningEvidenceRecord],
        key_fn: Callable[[LearningEvidenceRecord], list[str]],
        previous_states: list[DimensionState],
    ) -> list[DimensionState]:
        grouped: dict[str, list[LearningEvidenceRecord]] = defaultdict(list)
        for record in records:
            if record.evidence_weight < 0.4:
                continue
            for key in key_fn(record):
                if key:
                    grouped[key].append(record)
        previous_by_id = {item.dimension_id: item for item in previous_states}
        states: list[DimensionState] = []
        for key, items in grouped.items():
            weight_sum = sum(item.evidence_weight for item in items)
            adjusted = [max(0.0, min(1.0, item.normalized_score + (item.difficulty - 0.5) * 0.12)) for item in items]
            raw = (1.0 + sum(value * item.evidence_weight for value, item in zip(adjusted, items))) / (2.0 + weight_sum)
            assessments = {item.assessment_id for item in items}
            types = {item.question_type for item in items}
            old = previous_by_id.get(key)
            if old and not (len(assessments) >= 2 and sum((item.source_reliability or 0) >= 0.85 for item in items) >= 2):
                raw = max(old.mastery_probability - 0.12, min(old.mastery_probability + 0.12, raw))
            confidence = min(0.92, 0.12 + len(items) * 0.10 + len(assessments) * 0.12 + len(types) * 0.07)
            enough = len(items) >= 3 and len(assessments) >= 2
            if not enough:
                level = "insufficient_evidence"
                confidence = min(confidence, 0.39)
            elif raw < 0.45:
                level = "needs_support"
            elif raw < 0.65:
                level = "developing"
            elif raw < 0.82:
                level = "proficient"
            else:
                level = "strong"
            trend = "unknown"
            if old and enough:
                delta = raw - old.mastery_probability
                trend = "improving" if delta >= 0.06 else "declining" if delta <= -0.06 else "stable"
            interval = max(0.07, 0.34 * (1 - confidence))
            states.append(DimensionState(
                dimension_id=key, dimension_label=key,
                mastery_probability=round(raw, 3), mastery_level=level,
                confidence=round(confidence, 3),
                credible_interval_low=round(max(0.0, raw - interval), 3),
                credible_interval_high=round(min(1.0, raw + interval), 3),
                valid_evidence_count=len(items), independent_assessment_count=len(assessments),
                question_type_count=len(types), trend=trend,
                evidence_ids=[item.evidence_id for item in items],
                status_basis=f"由 {len(items)} 条有效证据、{len(assessments)} 个独立测次和 {len(types)} 种题型推断",
            ))
        return sorted(states, key=lambda item: (item.mastery_probability, item.dimension_id))

    def _facts(self, records: list[LearningEvidenceRecord], gate: EvidenceGate) -> list[str]:
        valid = [item for item in records if item.evidence_weight >= 0.4]
        if not valid:
            return ["当前没有通过质量门控的有效证据"]
        average = sum(item.normalized_score for item in valid) / len(valid)
        low = sum(item.normalized_score < 0.6 for item in valid)
        return [
            f"本次累计接收 {len(records)} 条记录，其中 {gate.valid_evidence_count} 条通过质量门控",
            f"有效记录的原始得分率均值为 {average:.0%}；这是观察统计，不等同于最终掌握度",
            f"共有 {low} 条有效记录得分率低于 60%",
            f"证据来自 {gate.independent_assessment_count} 个独立测次，覆盖 {gate.question_type_count} 种题型",
        ]

    def _patterns(self, records: list[LearningEvidenceRecord]) -> list[ErrorPattern]:
        grouped: dict[str, list[LearningEvidenceRecord]] = defaultdict(list)
        for record in records:
            for tag in record.error_tags:
                grouped[tag].append(record)
        patterns: list[ErrorPattern] = []
        for tag, items in grouped.items():
            assessments = {item.assessment_id for item in items}
            if len(items) < 2 or len(assessments) < 2:
                continue
            knowledge = sorted({tag for item in items for tag in item.knowledge_tags})
            patterns.append(ErrorPattern(
                label=ERROR_LABELS.get(tag, tag),
                description=f"该错误在 {len(assessments)} 个独立测次中重复出现，暂列为稳定错误模式",
                occurrence_count=len(items), independent_assessment_count=len(assessments),
                knowledge_tags=knowledge, evidence_ids=[item.evidence_id for item in items],
                confidence=round(min(0.9, 0.45 + len(items) * 0.08 + len(assessments) * 0.08), 3),
            ))
        return patterns

    def _hypotheses(self, records: list[LearningEvidenceRecord], patterns: list[ErrorPattern]) -> list[CauseHypothesis]:
        by_evidence = {item.evidence_id: item for item in records}
        hypotheses: list[CauseHypothesis] = []
        for pattern in patterns:
            tag = next((key for key, label in ERROR_LABELS.items() if label == pattern.label), pattern.label)
            if tag not in CAUSE_MAP:
                continue
            items = [by_evidence[eid] for eid in pattern.evidence_ids if eid in by_evidence]
            process_items = [item for item in items if item.step_trace or item.duration_seconds]
            if len(process_items) < 2:
                continue
            statement, verification = CAUSE_MAP[tag]
            counter = [
                item.evidence_id for item in records
                if item.normalized_score >= 0.8 and set(item.knowledge_tags) & set(pattern.knowledge_tags)
            ][:5]
            hypotheses.append(CauseHypothesis(
                hypothesis=statement,
                support=[item.evidence_id for item in process_items],
                counterevidence=counter,
                confidence=round(min(0.78, pattern.confidence * (0.75 if counter else 0.88)), 3),
                verification_needed=verification,
            ))
        return hypotheses
