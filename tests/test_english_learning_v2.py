from __future__ import annotations

import unittest

from ai_education.core.errors import InputValidationError
from ai_education.english_learning_repository import EnglishLearningRepository
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.services.english_learning_v2 import (
    EnglishLearningV2Service,
    StructuredEnglishStudyCoach,
)


class StubTranscriber:
    async def transcribe(self, content: bytes, filename: str, content_type: str) -> str:
        del content, filename, content_type
        return "I enjoy learning English because it helps me understand the world."


class EnglishLearningV2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = EnglishLearningRepository()
        self.service = EnglishLearningV2Service(
            self.repository,
            StructuredEnglishStudyCoach(None),
            transcriber=StubTranscriber(),
        )
        self.student_id = "student_english_v2"

    def test_catalog_uses_large_real_bank_without_exposing_answers(self) -> None:
        catalog = self.service.catalog(self.student_id)
        self.assertEqual(catalog["reading_count"], 117)
        self.assertEqual(catalog["simulation_count"], 48)
        self.assertGreaterEqual(len(catalog["items"]), 100)
        self.assertNotIn("article", catalog["items"][0])
        self.assertNotIn("questions", catalog["items"][0])
        self.assertNotIn("answers", catalog["items"][0])

    def test_reading_timer_progress_and_answers_are_released_only_after_submit(self) -> None:
        reading_id = self.service.items[0]["reading_id"]
        started = self.service.start(self.student_id, reading_id)
        self.assertEqual(started["progress"]["status"], "in_progress")
        self.assertEqual(started["progress"]["elapsed_seconds"], 0)
        self.assertNotIn("correct_option", started["reading"]["questions"][0])

        first_question = started["reading"]["questions"][0]["question_id"]
        progress = self.service.checkpoint(self.student_id, reading_id, {first_question: 1}, 37)
        self.assertEqual(progress["elapsed_seconds"], 37)
        row = next(
            item
            for item in self.service.catalog(self.student_id)["items"]
            if item["reading_id"] == reading_id
        )
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(row["answered_count"], 1)
        self.assertEqual(row["elapsed_seconds"], 37)

        with self.assertRaises(InputValidationError):
            self.service.submit(self.student_id, reading_id, {first_question: 1}, 40)

        answers = {
            item["question_id"]: answer["correct_option"]
            for item, answer in zip(
                started["reading"]["questions"],
                self.service.answers[reading_id]["answers"],
                strict=True,
            )
        }
        submitted = self.service.submit(self.student_id, reading_id, answers, 95)
        self.assertEqual(submitted["progress"]["status"], "completed")
        self.assertEqual(submitted["progress"]["score"], 1.0)
        self.assertTrue(all(item["is_correct"] for item in submitted["results"]))
        self.assertTrue(all("correct_option" in item for item in submitted["results"]))

    async def test_vocabulary_grammar_and_selected_notebook(self) -> None:
        result = await self.service.analyze_language(
            self.student_id,
            "Students learn English and students build confidence.",
            "vocabulary",
            "B1",
        )
        words = result["vocabulary"]["words"]
        self.assertEqual(
            [item["word"] for item in words],
            ["students", "learn", "english", "and", "build", "confidence"],
        )
        long_words = [
            chr(97 + first) + chr(97 + second) for first in range(4) for second in range(26)
        ]
        long_result = await self.service.analyze_language(
            self.student_id, " ".join(long_words), "vocabulary", "B1"
        )
        self.assertEqual(len(long_result["vocabulary"]["words"]), len(long_words))

        saved = self.service.save_vocabulary(
            self.student_id,
            "Students learn English and students build confidence.",
            [words[1], words[-1]],
        )
        self.assertEqual(saved["saved_count"], 2)
        records = self.repository.learning_records(self.student_id)
        self.assertEqual({item["word"] for item in records["vocabulary"]}, {"learn", "confidence"})

        grammar = await self.service.analyze_language(
            self.student_id, "Because the weather", "grammar", "B1"
        )
        self.assertFalse(grammar["grammar"]["is_complete_sentence"])
        self.assertGreaterEqual(len(grammar["grammar"]["correction_steps"]), 1)

    async def test_speaking_uses_audio_transcript_and_returns_five_scores(self) -> None:
        result = await self.service.assess_speaking(
            self.student_id,
            "My future study",
            b"test-audio",
            "answer.webm",
            "audio/webm",
            28,
            "",
        )
        self.assertEqual(result["transcription_source"], "audio_model")
        self.assertFalse(result["audio_persisted"])
        self.assertEqual(
            set(result["assessment"]["scores"]),
            {"fluency", "accuracy", "coherence", "vocabulary", "speech_clarity"},
        )

    def test_mysql_schema_contains_reading_progress_table(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        self.assertIn("CREATE TABLE IF NOT EXISTS english_reading_progress", schema)
        self.assertIn("elapsed_seconds", schema)


if __name__ == "__main__":
    unittest.main()
