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


if __name__ == "__main__":
    unittest.main()
