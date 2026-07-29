from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from ai_education.api.app import AppContainer, create_app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(AppContainer()))

    def test_health_and_manifest(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["planner_graph"], "ready")
        manifest = self.client.get("/api/v1/tools/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertGreaterEqual(len(manifest.json()), 60)

    def test_onboarding_resumes_with_only_two_questions(self) -> None:
        created = self.client.post(
            "/api/v1/onboarding/sessions", json={"student_id": "student_api"}
        )
        self.assertEqual(created.status_code, 201)
        onboarding_id = created.json()["onboarding_id"]
        questions = self.client.get(
            f"/api/v1/onboarding/sessions/{onboarding_id}/next-questions"
        ).json()["questions"]
        self.assertLessEqual(len(questions), 2)


if __name__ == "__main__":
    unittest.main()
