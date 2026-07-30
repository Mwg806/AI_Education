from __future__ import annotations

import unittest

from httpx import ASGITransport, AsyncClient

from ai_education.api.app import AppContainer, create_app


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncClient(
            transport=ASGITransport(app=create_app(AppContainer())),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_and_manifest(self) -> None:
        health = await self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["planner_graph"], "ready")
        self.assertEqual(health.json()["homework_tutor_graph"], "ready")
        self.assertEqual(len(health.json()["registered_agents"]), 2)
        manifest = await self.client.get("/api/v1/tools/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertGreaterEqual(len(manifest.json()), 60)

    async def test_homework_tutor_session_turn_and_question_bank(self) -> None:
        created = await self.client.post(
            "/api/v1/homework/sessions",
            json={
                "student_id": "student_api_homework",
                "grade": "grade_11",
                "province_code": "43",
                "target_exam_year": 2027,
                "subject_hint": "mathematics",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["agent_role"], "homework_tutor")
        session_id = created.json()["result"]["session"]["session_id"]
        turn = await self.client.post(
            f"/api/v1/homework/sessions/{session_id}/turns",
            data={
                "student_id": "student_api_homework",
                "question_text": "已知函数 f(x)=x²-2x，求单调区间。",
                "message": "我还没有思路",
                "intent": "request_hint",
                "subject": "mathematics",
                "client_turn_id": "api_homework_turn_1",
            },
        )
        self.assertEqual(turn.status_code, 200)
        self.assertEqual(turn.json()["result"]["tutoring"]["action"], "release_hint")
        self.assertGreater(len(turn.json()["result"]["question_bank_matches"]), 0)
        summary = await self.client.get("/api/v1/homework/question-bank/summary")
        self.assertEqual(summary.json()["total_files"], 7577)

    async def test_onboarding_resumes_with_only_two_questions(self) -> None:
        created = await self.client.post(
            "/api/v1/onboarding/sessions", json={"student_id": "student_api"}
        )
        self.assertEqual(created.status_code, 201)
        onboarding_id = created.json()["onboarding_id"]
        questions = (
            await self.client.get(f"/api/v1/onboarding/sessions/{onboarding_id}/next-questions")
        ).json()["questions"]
        self.assertLessEqual(len(questions), 2)

    async def test_onboarding_catalog_is_complete_and_source_grounded(self) -> None:
        response = await self.client.get("/api/v1/catalog/onboarding")
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertEqual(catalog["scope"]["exam_system"], "全国新课标Ⅰ卷")
        self.assertEqual(len(catalog["provinces"]), 11)
        self.assertEqual(catalog["scope"]["textbook_pdf_count"], 329)
        self.assertEqual(len(catalog["mathematics"]["editions"]), 7)
        self.assertTrue(all(edition["volumes"] for edition in catalog["mathematics"]["editions"]))
        self.assertGreaterEqual(len(catalog["mathematics"]["standard_modules"]), 10)
        subjects = {item["id"]: item for item in catalog["subjects"]}
        self.assertEqual(
            set(subjects),
            {
                "chinese",
                "mathematics",
                "foreign_language",
                "physics",
                "chemistry",
                "biology",
                "ideology_politics",
                "history",
                "geography",
                "technology",
            },
        )
        self.assertTrue(all(item["standard_modules"] for item in subjects.values()))
        self.assertTrue(all(item["standard_sources"] for item in subjects.values()))
        self.assertEqual(len(subjects["technology"]["standard_sources"]), 2)


if __name__ == "__main__":
    unittest.main()
