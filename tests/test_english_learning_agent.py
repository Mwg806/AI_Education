from __future__ import annotations

import unittest

from ai_education.agents.english_learning import EnglishReadingLanguageAgent
from ai_education.domain.english_learning import (
    EnglishAnswerInput,
    EnglishLearnerProfileInput,
    EnglishTaskInput,
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
        self.assertEqual(response.result["target_user"], "新高考全国Ⅰ卷考生")
        self.assertTrue(response.result["exam_profile"]["audience_eligible"])

    async def test_new_mvp_routes_create_records_and_respect_learning_safety(self) -> None:
        profile = self.service.update_learner_profile(
            "student_english",
            EnglishLearnerProfileInput(
                self_reported_level="B1",
                preferred_mode="teaching",
                learning_goals=["2027 新高考全国Ⅰ卷英语"],
            ),
            PROFILE,
        )
        self.assertEqual(profile["target_language"], "en")
        vocabulary = await self.service.execute_task(
            "student_english",
            EnglishTaskInput(
                task_type="vocabulary_explanation",
                source_text="address",
                user_message="解释这个词在 address the problem 中的含义",
            ),
            PROFILE,
        )
        self.assertEqual(vocabulary["task"]["primary_intent"], "vocabulary_explanation")
        self.assertTrue(vocabulary["learning_record"]["new_vocabulary"])
        speaking = await self.service.execute_task(
            "student_english",
            EnglishTaskInput(
                task_type="speaking_practice",
                source_text="I want go to the museum tomorrow.",
                scenario="高考英语口语表达",
                feedback_mode="delayed",
            ),
            PROFILE,
        )
        self.assertIsNone(speaking["answer"]["scores"]["pronunciation"])
        self.assertTrue(speaking["learning_record"]["saved"])

    async def test_national_i_blueprint_and_exam_practice_are_explicit(self) -> None:
        blueprint = self.service.exam_blueprint()
        self.assertEqual(blueprint["paper_variant"], "新高考全国Ⅰ卷")
        self.assertEqual(blueprint["target_users"], "参加新高考全国Ⅰ卷的高中英语考生")
        self.assertEqual(blueprint["score"], 150)
        result = await self.service.execute_task(
            "student_english",
            EnglishTaskInput(
                task_type="exam_practice",
                source_text=ARTICLE,
                exam_section="reading",
                response_mode="exam",
            ),
            PROFILE,
        )
        self.assertTrue(result["task"]["national_i_candidate"])
        self.assertTrue(result["answer"]["reading_evidence"])
        self.assertEqual(result["national_i_blueprint"]["paper_variant"], "新高考全国Ⅰ卷")

    async def test_repeated_grammar_error_becomes_stable_only_after_three_events(self) -> None:
        last = None
        for _ in range(3):
            last = await self.service.execute_task(
                "student_english",
                EnglishTaskInput(
                    task_type="grammar_correction",
                    source_text="I have went to Beijing last year.",
                    response_mode="correction",
                ),
                PROFILE,
            )
        assert last is not None
        update = last["learning_record"]["grammar_updates"][0]
        self.assertEqual(update["error_count"], 3)
        self.assertTrue(update["stable_weakness"])
        dashboard = self.service.dashboard("student_english", PROFILE)
        self.assertEqual(dashboard["weekly_report"]["completed_tasks"], 3)

    async def test_learning_event_and_vocabulary_are_user_deletable(self) -> None:
        result = await self.service.execute_task(
            "student_english",
            EnglishTaskInput(task_type="vocabulary_explanation", source_text="issue"),
            PROFILE,
        )
        event_id = result["learning_record"]["event_id"]
        self.assertTrue(
            self.service.delete_learning_record("student_english", "event", event_id)["deleted"]
        )
        self.assertTrue(
            self.service.delete_learning_record("student_english", "vocabulary", "issue")["deleted"]
        )

    def test_mysql_schema_contains_all_private_english_learning_tables(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        for table in (
            "english_text_analyses",
            "english_learning_sessions",
            "english_learning_attempts",
            "english_mastery_states",
            "english_review_items",
            "english_learner_profiles",
            "english_learning_events",
            "english_vocabulary_items",
            "english_grammar_items",
            "english_writing_submissions",
            "english_speaking_sessions",
            "english_national_exam_attempts",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)


if __name__ == "__main__":
    unittest.main()
