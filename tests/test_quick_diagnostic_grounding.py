from __future__ import annotations

import unittest

from ai_education.services.diagnostic_knowledge import DiagnosticKnowledgeRetriever
from ai_education.services.diagnostic_scope import DiagnosticScopeResolver
from ai_education.services.quick_diagnostic_bank import QuickDiagnosticBank


class QuickDiagnosticGroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.label = "必修 第一册 集合与常用逻辑用语"
        self.scope = {
            "id": "TB-MATH-V-A82DECE0E2F8-C01",
            "label": self.label,
        }

    def test_scope_resolver_removes_book_noise_and_maps_taxonomy(self) -> None:
        profile = DiagnosticScopeResolver().resolve("mathematics", self.label)

        self.assertEqual(profile.cleaned_label, "集合与常用逻辑用语")
        self.assertEqual(profile.module_ids, ("MATH-SETS-LOGIC",))
        self.assertIn("集合", profile.direct_terms)
        self.assertIn("充分条件", profile.taxonomy_terms)

    def test_chapter_fallback_selects_ten_verified_questions(self) -> None:
        bank = QuickDiagnosticBank()

        questions = bank.questions(
            subject="mathematics",
            seed="scope-mapping-regression",
            progress_label=self.label,
            whole_book=False,
            scope_units=[self.scope],
        )

        self.assertEqual(len(questions), 10)
        self.assertTrue(
            all(
                item["scope_id"] == self.scope["id"]
                and item["provenance"]["scope_match_verified"]
                and item["provenance"]["scope_match_terms"]
                and item["provenance"]["scope_module_ids"] == ["MATH-SETS-LOGIC"]
                for item in questions
            )
        )

    def test_unrelated_scope_is_not_filled_with_random_subject_questions(self) -> None:
        bank = QuickDiagnosticBank()

        with self.assertRaisesRegex(RuntimeError, "可核验匹配的题目不足 10 题"):
            bank.questions(
                subject="mathematics",
                seed="unrelated-scope-regression",
                progress_label="火星土壤培养与星际航行",
                whole_book=False,
                scope_units=[
                    {
                        "id": "not-a-real-math-scope",
                        "label": "火星土壤培养与星际航行",
                    }
                ],
            )

    def test_grounding_sources_are_relevant_to_resolved_scope(self) -> None:
        retrieval = DiagnosticKnowledgeRetriever().retrieve(
            subject="mathematics",
            scope_units=[self.scope],
        )

        self.assertEqual(retrieval["status"], "ready")
        self.assertTrue(retrieval["sources"])
        self.assertTrue(
            all(
                any(
                    term in source["content"]
                    for term in ("集合", "逻辑用语", "充分条件", "全称量词")
                )
                for source in retrieval["sources"]
            )
        )


if __name__ == "__main__":
    unittest.main()
