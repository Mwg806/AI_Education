"""Capability declaration for the teacher lesson-preparation Agent."""

TEACHER_PREPARATION_TOOL_MANIFEST: tuple[str, ...] = (
    "teaching_context_validate",
    "teacher_profile_load",
    "class_profile_load",
    "class_diagnosis_aggregate",
    "lesson_request_resolve",
    "lesson_type_template_load",
    "curriculum_version_resolve",
    "exam_blueprint_resolve",
    "subject_adapter_load",
    "teaching_resource_catalog",
    "teaching_resource_search",
    "teaching_resource_excerpt_retrieve",
    "teaching_resource_checksum_verify",
    "learning_objectives_generate",
    "objective_measurability_validate",
    "lesson_flow_generate",
    "time_budget_allocate",
    "activity_feasibility_validate",
    "contingency_path_generate",
    "board_plan_generate",
    "board_capacity_validate",
    "assessment_blueprint_generate",
    "assessment_item_generate",
    "scoring_rubric_generate",
    "differentiation_plan_generate",
    "diagnosis_tags_bind",
    "alignment_matrix_build",
    "instructional_alignment_validate",
    "resource_compliance_validate",
    "lesson_version_save",
    "lesson_component_lock",
    "lesson_component_revise",
    "teacher_approval_record",
    "lesson_publish",
    "post_lesson_feedback_record",
    "teaching_events_publish",
)


class TeacherPreparationToolbox:
    def capability_manifest(self) -> dict[str, str]:
        return {name: "implemented" for name in TEACHER_PREPARATION_TOOL_MANIFEST}
