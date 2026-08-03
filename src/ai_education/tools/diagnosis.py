"""Capability declaration for learning-state diagnosis."""

DIAGNOSIS_TOOL_MANIFEST: tuple[str, ...] = (
    "diagnosis_context_validate",
    "subject_blueprint_resolve",
    "assessment_adapter_resolve",
    "learning_evidence_ingest",
    "learning_evidence_normalize",
    "learning_evidence_deduplicate",
    "evidence_quality_score",
    "evidence_independence_check",
    "evidence_sufficiency_gate",
    "knowledge_state_infer",
    "question_type_state_infer",
    "ability_state_infer",
    "stable_error_pattern_detect",
    "cause_hypothesis_generate",
    "counterevidence_check",
    "state_hysteresis_apply",
    "state_version_publish",
    "student_report_generate",
    "teacher_report_generate",
    "reassessment_spec_generate",
    "teacher_review_record",
    "diagnosis_event_publish",
)


class DiagnosisToolbox:
    def capability_manifest(self) -> dict[str, str]:
        return {name: "implemented" for name in DIAGNOSIS_TOOL_MANIFEST}
