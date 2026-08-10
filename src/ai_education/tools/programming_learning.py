"""Implemented capability manifest for the student programming growth Agent."""

PROGRAMMING_LEARNING_TOOL_MANIFEST: tuple[str, ...] = (
    "student.profile.initialize",
    "direction.intent.resolve",
    "direction.major.map",
    "direction.baseline.assess",
    "direction.roadmap.plan",
    "project.topic.recommend",
    "project.milestone.decompose",
    "project.task.decompose",
    "project.acceptance.generate",
    "project.hint.next",
    "code.context.detect",
    "code.syntax.parse",
    "code.static.scan",
    "code.error.localize",
    "code.hint.next",
    "code.test.generate",
    "interview.question.generate",
    "interview.answer.score",
    "interview.followup.generate",
    "assessment.evidence.normalize",
    "assessment.mastery.update",
    "assessment.review.generate",
    "adaptation.pace.adjust",
)


class ProgrammingLearningToolbox:
    def capability_manifest(self) -> dict[str, str]:
        return {name: "implemented" for name in PROGRAMMING_LEARNING_TOOL_MANIFEST}
