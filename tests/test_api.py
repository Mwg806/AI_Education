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
        manifest = await self.client.get("/api/v1/tools/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertGreaterEqual(len(manifest.json()), 60)

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
        editions = {item["id"]: item for item in catalog["mathematics"]["editions"]}
        a_chapters = sum(
            len(volume["chapters"]) for volume in editions["people_education_a"]["volumes"]
        )
        b_chapters = sum(
            len(volume["chapters"]) for volume in editions["people_education_b"]["volumes"]
        )
        self.assertEqual(a_chapters, 18)
        self.assertEqual(b_chapters, 17)
        self.assertGreaterEqual(len(catalog["mathematics"]["standard_modules"]), 10)


if __name__ == "__main__":
    unittest.main()
