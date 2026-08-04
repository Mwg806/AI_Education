from __future__ import annotations

import unittest

from ai_education.agents.english_learning import EnglishReadingLanguageAgent
from ai_education.domain.english_learning import (
    EnglishAnswerInput,
    EnglishTextAnalysisInput,
    EnglishTrainingCreateInput,
    EnglishTrainingSubmissionInput,
)
from ai_education.domain.enums import ActorType, AgentRole, StandardStatus
from ai_education.domain.protocols import AgentRequest, Operator
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.llm.english_learning import StructuredEnglishTrainingGenerator
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.services.english_knowledge import EnglishKnowledgeService
from ai_education.services.english_learning import EnglishLearningService

ARTICLE = """Learning to read well involves more than recognizing individual words.
Students need to connect ideas across sentences and notice how writers signal contrast or cause.
When a paragraph begins with however, the writer usually changes direction and asks the reader
to reconsider an earlier point. Skilled readers also return to the text instead of relying only
on background knowledge. This habit helps them separate evidence from guesses and makes their
conclusions more reliable. Regular practice is useful because the same strategy can be applied
to science reports, stories, and news articles. Over time, careful evidence location becomes
faster and requires less conscious effort."""

PROFILE = {
    "grade": "grade_11",
    "provinceCode": "43",
    "targetExamYear": 2027,
}


class EnglishKnowledgeTests(unittest.TestCase):
    def test_curriculum_retrieval_prefers_official_english_standard(self) -> None:
        references = EnglishKnowledgeService().curriculum_basis()
        self.assertTrue(references)
        self.assertEqual(references[0]["document_id"], "DOC-CS-ENGLISH-2020")
        self.assertEqual(references[0]["authority_level"], "A")


class EnglishLearningServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = EnglishLearningRepository()
        self.service = EnglishLearningService(
            self.repository,
            StructuredEnglishTrainingGenerator(None),
        )

    async def test_analysis_and_training_are_grounded_and_answers_stay_private(self) -> None:
        analysis = self.service.analyze(
            "student_english",
            EnglishTextAnalysisInput(title="Evidence-based reading", text=ARTICLE),
            PROFILE,
        )
        self.assertGreaterEqual(analysis["statistics"]["sentence_count"], 7)
        self.assertTrue(analysis["source_references"])
        self.assertEqual(analysis["vocabulary_coverage"]["status"], "needs_learner_evidence")

        session = await self.service.create_training(
            "student_english",
            EnglishTrainingCreateInput(
                title="Evidence-based reading",
                text=ARTICLE,
                mode="reading_multiple_choice",
                question_count=4,
            ),
            PROFILE,
        )
        self.assertEqual(session["quality_status"], "passed")
        self.assertEqual(session["generation_mode"], "evidence_template")
        self.assertNotIn("correct_option", session["questions"][0])
        self.assertNotIn("evidence_quote", session["questions"][0])

        answers = [
            EnglishAnswerInput(
                question_id=item["question_id"],
                selected_option=0 if index else 1,
                response_time_ms=20_000,
            )
            for index, item in enumerate(session["questions"])
        ]
        result = self.service.submit_training(
            "student_english",
            session["session_id"],
            EnglishTrainingSubmissionInput(answers=answers),
        )
        self.assertEqual(result["attempt"]["correct_count"], 3)
        self.assertEqual(len(result["new_reviews"]), 1)
        self.assertTrue(result["attempt"]["results"][0]["evidence_quote"] in ARTICLE)
        self.assertEqual(result["session"]["status"], "completed")

    async def test_seven_of_five_has_five_gaps_and_seven_options(self) -> None:
        session = await self.service.create_training(
            "student_english",
            EnglishTrainingCreateInput(
                title="Cohesion practice",
                text=ARTICLE,
                mode="seven_of_five",
            ),
            PROFILE,
        )
        self.assertEqual(len(session["questions"]), 5)
        self.assertTrue(all(len(item["options"]) == 7 for item in session["questions"]))
        self.assertTrue(all(f"[{index}]" in session["display_text"] for index in range(1, 6)))

    async def test_agent_is_registered_role_and_returns_dashboard(self) -> None:
        agent = EnglishReadingLanguageAgent(self.service)
        self.assertEqual(agent.metadata.role, AgentRole.ENGLISH_READING_LANGUAGE)
        response = await agent.ainvoke(
            AgentRequest(
                student_id="student_english",
                actor=Operator(type=ActorType.STUDENT, id="student_english"),
                intent="get_english_dashboard",
                context={"student_profile": PROFILE},
            )
        )
        self.assertEqual(response.status, StandardStatus.SUCCESS)
        self.assertIn("exam_profile", response.result)
        self.assertFalse(response.result["data_sufficiency"]["score_prediction_available"])

    def test_mysql_schema_contains_all_private_english_learning_tables(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        for table in (
            "english_text_analyses",
            "english_learning_sessions",
            "english_learning_attempts",
            "english_mastery_states",
            "english_review_items",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)


if __name__ == "__main__":
    unittest.main()
