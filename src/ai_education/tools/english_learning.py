"""Implemented capability manifest for the English reading and language Agent."""

ENGLISH_LEARNING_TOOL_MANIFEST: tuple[str, ...] = (
    "exam.resolve_paper_profile",
    "language.detect_and_normalize",
    "language.score_text_difficulty",
    "gaokao.analyze_vocabulary_requirements",
    "language.extract_core_vocabulary",
    "language.extract_grammar_points",
    "gaokao.analyze_long_complex_sentences",
    "gaokao.map_text_to_exam_skills",
    "reading.build_question_blueprint",
    "gaokao.generate_reading_multiple_choice",
    "gaokao.generate_seven_of_five",
    "reading.validate_question_quality",
    "reading.evaluate_answer",
    "gaokao.diagnose_reading_distractor",
    "gaokao.diagnose_seven_of_five_gap",
    "reading.locate_comprehension_gap",
    "tracking.normalize_learning_evidence",
    "tracking.update_mastery",
    "tracking.estimate_forgetting_risk",
    "tracking.schedule_gaokao_review",
    "tracking.build_language_profile",
)


class EnglishLearningToolbox:
    def capability_manifest(self) -> dict[str, str]:
        return {name: "implemented" for name in ENGLISH_LEARNING_TOOL_MANIFEST}
