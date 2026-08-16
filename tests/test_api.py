from __future__ import annotations

import unittest
from io import BytesIO

from httpx import ASGITransport, AsyncClient

from ai_education.api.app import AppContainer, create_app
from ai_education.core.errors import InputValidationError
from tests.fixtures import (
    FakeStructuredDiagnosisReporter,
    FakeStructuredDiagnosticGenerator,
    FakeStructuredExamGrader,
    FakeStructuredHomeworkTutor,
)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        container = AppContainer(enable_persistence=False)
        self.container = container
        self.fake_tutor = FakeStructuredHomeworkTutor()
        container.homework.structured_tutor = self.fake_tutor
        self.fake_diagnostic = FakeStructuredDiagnosticGenerator()
        container.diagnostics.generator = self.fake_diagnostic
        self.fake_diagnosis_reporter = FakeStructuredDiagnosisReporter()
        container.learning_diagnosis.reporter = self.fake_diagnosis_reporter
        self.fake_exam_grader = FakeStructuredExamGrader()
        container.exam_diagnostics.grader = self.fake_exam_grader
        self.client = AsyncClient(
            transport=ASGITransport(app=create_app(container)),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_and_manifest(self) -> None:
        health = await self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["planner_graph"], "ready")
        self.assertEqual(health.json()["homework_tutor_graph"], "ready")
        self.assertEqual(health.json()["learning_diagnosis_graph"], "ready")
        self.assertEqual(health.json()["teacher_preparation_graph"], "ready")
        self.assertEqual(health.json()["english_learning_graph"], "ready")
        self.assertEqual(health.json()["teaching_resource_bank"]["resource_count"], 27)
        self.assertEqual(health.json()["diagnosis_report_generation_mode"], "llm")
        self.assertEqual(len(health.json()["registered_agents"]), 6)
        self.assertEqual(health.json()["programming_learning_graph"], "ready")
        manifest = await self.client.get("/api/v1/tools/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertGreaterEqual(len(manifest.json()), 60)
        agent_manifest = await self.client.get("/api/v1/agents/manifest")
        self.assertIn("learning_diagnosis", agent_manifest.json())
        self.assertIn("teacher_preparation", agent_manifest.json())
        self.assertIn("english_reading_language", agent_manifest.json())
        self.assertIn("programming_learning", agent_manifest.json())

    async def test_exam_diagnostic_catalog_and_paper_never_expose_answers(self) -> None:
        catalog = await self.client.get("/api/v1/exam-diagnostics/catalog")
        self.assertEqual(catalog.status_code, 200)
        payload = catalog.json()
        self.assertEqual(payload["paper_count"], 100)
        self.assertEqual(len(payload["subjects"]), 10)
        self.assertTrue(all(item["paper_count"] == 10 for item in payload["subjects"]))
        paper_id = payload["subjects"][1]["papers"][0]["paper_id"]
        paper = await self.client.get(f"/api/v1/exam-diagnostics/papers/{paper_id}")
        self.assertEqual(paper.status_code, 200)
        self.assertEqual(len(paper.json()["questions"]), 20)
        self.assertNotIn("correct_option", paper.text)
        self.assertNotIn("standard_answer", paper.text)
        multiple_choice = next(
            item for item in paper.json()["questions"] if item["type"] == "multiple_choice"
        )
        self.assertEqual([item["key"] for item in multiple_choice["options"]], list("ABCD"))

    async def test_teacher_assignment_only_accepts_each_subject_last_five_papers(self) -> None:
        catalog = self.container.exam_diagnostics.catalog()
        first_subject = catalog["subjects"][0]
        platform_paper_id = first_subject["papers"][0]["paper_id"]
        teacher_paper_id = first_subject["papers"][5]["paper_id"]

        with self.assertRaises(InputValidationError):
            self.container.exam_diagnostics.teacher_assignable_paper(platform_paper_id)
        accepted = self.container.exam_diagnostics.teacher_assignable_paper(teacher_paper_id)
        self.assertEqual(accepted["paper_id"], teacher_paper_id)

    async def test_teacher_assignment_is_bound_to_exam_session(self) -> None:
        class AssignmentStore:
            def student_exam_assignment(self, student_id: str, assignment_id: str, paper_id: str):
                if student_id != "student_exam_api" or assignment_id != "assignment_01":
                    return None
                return {"title": "老师新增诊断卷", "classroom_id": 7, "class_name": "高三一班"}

            def save_exam_session(self, payload: dict) -> None:
                self.saved = payload

        store = AssignmentStore()
        self.container.exam_diagnostics.persistence = store  # type: ignore[assignment]
        catalog = (await self.client.get("/api/v1/exam-diagnostics/catalog")).json()
        paper_id = catalog["subjects"][1]["papers"][0]["paper_id"]
        created = await self.client.post("/api/v1/exam-diagnostics/sessions", json={
            "student_id": "student_exam_api", "paper_id": paper_id, "assignment_id": "assignment_01",
            "grade": "grade_12", "province_code": "43", "target_exam_year": 2027,
        })
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["session"]["assignment_id"], "assignment_01")
        self.assertEqual(created.json()["session"]["assignment_title"], "老师新增诊断卷")
        rejected = await self.client.post("/api/v1/exam-diagnostics/sessions", json={"student_id": "other_student", "paper_id": paper_id, "assignment_id": "assignment_01", "grade": "grade_12", "province_code": "43", "target_exam_year": 2027})
        self.assertEqual(rejected.status_code, 400)

    async def test_exam_photo_grading_uses_source_answer_and_submit_creates_evidence(self) -> None:
        from PIL import Image

        catalog = (await self.client.get("/api/v1/exam-diagnostics/catalog")).json()
        paper_id = catalog["subjects"][1]["papers"][0]["paper_id"]
        created = await self.client.post("/api/v1/exam-diagnostics/sessions", json={
            "student_id": "student_exam_api", "paper_id": paper_id,
            "grade": "grade_12", "province_code": "43", "target_exam_year": 2027,
        })
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["session"]["session_id"]
        paper = created.json()["paper"]
        constructed = next(item for item in paper["questions"] if item["type"] == "constructed_response")
        buffer = BytesIO()
        Image.new("RGB", (1200, 900), "white").save(buffer, format="PNG")
        graded = await self.client.post(
            f"/api/v1/exam-diagnostics/sessions/{session_id}/questions/{constructed['question_id']}/grade",
            data={"student_id": "student_exam_api", "duration_seconds": "95"},
            files={"images": ("work.png", buffer.getvalue(), "image/png")},
        )
        self.assertEqual(graded.status_code, 200, graded.text)
        self.assertEqual(graded.json()["grading"]["graded_by"], "multimodal_llm")
        self.assertFalse(graded.json()["standard_answer_exposed"])
        self.assertTrue(self.fake_exam_grader.calls[-1]["source_answer"])

        objective = [
            {"question_id": item["question_id"], "selected_option": "A", "duration_seconds": 30}
            for item in paper["questions"] if item["type"] == "multiple_choice"
        ]
        submitted = await self.client.post(
            f"/api/v1/exam-diagnostics/sessions/{session_id}/submit",
            json={
                "student_id": "student_exam_api",
                "answers": objective,
                "question_durations": {
                    item["question_id"]: item["sequence"] * 7 for item in paper["questions"]
                },
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        result = submitted.json()
        self.assertEqual(len(result["objective_results"]), 12)
        self.assertEqual(len(result["evidence_records"]), 13)
        self.assertEqual(len(result["learning_record"]["question_records"]), 20)
        self.assertTrue(result["learning_record"]["knowledge_statistics"])
        self.assertGreater(result["learning_record"]["total_duration_seconds"], 0)
        constructed_record = next(
            item for item in result["learning_record"]["question_records"]
            if item["question_id"] == constructed["question_id"]
        )
        self.assertEqual(constructed_record["duration_seconds"], constructed["sequence"] * 7)
        self.assertFalse(result["standard_answer_exposed"])
        self.assertEqual(result["learning_diagnosis"]["agent_role"], "learning_diagnosis")

    async def test_learning_diagnosis_is_evidence_gated_and_model_explained(self) -> None:
        records = []
        for index in range(6):
            records.append({
                "assessment_id": "weekly_01" if index < 2 else "mock_01" if index < 4 else "homework_02",
                "assessment_type": "mock_exam" if 2 <= index < 4 else "homework",
                "question_id": f"q{index + 1}",
                "knowledge_tags": ["函数单调性" if index < 5 else "导数应用"],
                "question_type": ["选择题", "解答题", "填空题"][index % 3],
                "ability_tags": ["逻辑推理" if index % 2 else "数学抽象"],
                "difficulty": 0.35 + index * 0.07,
                "score": [5, 4, 6, 3, 8, 5][index],
                "max_score": 10,
                "duration_seconds": 240 + index * 30,
                "error_tags": ["concept_confusion"] if index in {0, 2} else [],
                "step_trace": "保留了可核验的关键步骤",
                "source_id": f"api_diag_{index}",
                "occurred_at": f"2026-07-{15 + index}T12:00:00+08:00",
            })
        response = await self.client.post("/api/v1/learning-diagnosis/run", json={
            "student_id": "student_diag_api", "grade": "grade_11", "province_code": "43",
            "subject": "mathematics", "target_exam_year": 2027,
            "diagnosis_request": "识别稳定薄弱点", "records": records,
        })
        self.assertEqual(response.status_code, 201, response.text)
        envelope = response.json()
        self.assertEqual(envelope["agent_role"], "learning_diagnosis")
        state = envelope["result"]["learning_state"]
        self.assertEqual(state["diagnosis_status"], "stable")
        self.assertEqual(state["evidence_gate"]["independent_assessment_count"], 3)
        self.assertEqual(state["narrative"]["generation_mode"], "llm")
        self.assertEqual(len(state["stable_error_patterns"]), 1)
        self.assertTrue(state["knowledge_states"][0]["evidence_ids"])
        self.assertEqual(len(self.fake_diagnosis_reporter.calls), 1)

    async def test_learning_record_accepts_question_and_solution_images(self) -> None:
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (1000, 800), "white").save(buffer, format="PNG")
        payload = buffer.getvalue()
        response = await self.client.post(
            "/api/v1/learning-diagnosis/record-images",
            files=[
                ("question_images", ("question.png", payload, "image/png")),
                ("solution_images", ("solution.png", payload, "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["question_image_count"], 1)
        self.assertEqual(result["solution_image_count"], 1)
        self.assertFalse(result["raw_images_persisted"])

    async def test_single_diagnosis_record_never_becomes_stable_conclusion(self) -> None:
        response = await self.client.post("/api/v1/learning-diagnosis/run", json={
            "student_id": "student_diag_sparse", "grade": "grade_11", "province_code": "43",
            "subject": "mathematics", "target_exam_year": 2027,
            "records": [{
                "assessment_id": "once", "assessment_type": "homework", "question_id": "q1",
                "knowledge_tags": ["数列"], "question_type": "选择题", "ability_tags": ["运算求解"],
                "difficulty": 0.5, "score": 0, "max_score": 5,
            }],
        })
        self.assertEqual(response.status_code, 201, response.text)
        state = response.json()["result"]["learning_state"]
        self.assertEqual(state["diagnosis_status"], "insufficient_evidence")
        self.assertEqual(state["knowledge_states"][0]["mastery_level"], "insufficient_evidence")
        self.assertFalse(state["stable_error_patterns"])

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

    async def test_homework_image_upload_reaches_multimodal_model(self) -> None:
        from PIL import Image

        created = await self.client.post(
            "/api/v1/homework/sessions",
            json={
                "student_id": "student_api_image",
                "grade": "grade_11",
                "province_code": "43",
                "target_exam_year": 2027,
                "subject_hint": "physics",
            },
        )
        session_id = created.json()["result"]["session"]["session_id"]
        buffer = BytesIO()
        Image.new("RGB", (1000, 800), "white").save(buffer, format="PNG")
        turn = await self.client.post(
            f"/api/v1/homework/sessions/{session_id}/turns",
            data={
                "student_id": "student_api_image",
                "message": "请结合原图分析这道物理题",
                "intent": "request_hint",
                "subject": "physics",
                "client_turn_id": "api_homework_image_1",
            },
            files={"images": ("question.png", buffer.getvalue(), "image/png")},
        )
        self.assertEqual(turn.status_code, 200)
        tutoring = turn.json()["result"]["tutoring"]
        self.assertEqual(tutoring["pedagogical_metadata"]["generation_mode"], "llm")
        self.assertTrue(tutoring["pedagogical_metadata"]["multimodal"])
        self.assertEqual(self.fake_tutor.calls[-1]["image_count"], 1)

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



    async def test_quick_diagnostic_hides_answers_and_emits_objective_evidence(self) -> None:
        created = await self.client.post(
            "/api/v1/planner/diagnostics",
            json={
                "student_id": "student_diagnostic",
                "grade": "grade_11",
                "subject": "mathematics",
                "curriculum_version": "people_education_a",
                "chapter_id": "MATH-DERIVATIVE",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["question_count"], 10)
        self.assertEqual(session["generation_mode"], "llm")
        self.assertEqual(session["grounding"]["mode"], "knowledge_grounded_ai")
        self.assertEqual(session["grounding"]["status"], "verified")
        self.assertGreater(session["grounding"]["source_count"], 0)
        self.assertTrue(
            all(
                item["provenance"]["scope_match_verified"]
                and item["provenance"]["excerpt_verified"]
                for item in session["questions"]
            )
        )
        self.assertNotIn("correct_option", session["questions"][0])
        self.assertNotIn("source_excerpt", session["questions"][0])
        self.assertEqual(len(self.fake_diagnostic.calls), 1)

        responses = [
            {
                "question_id": question["question_id"],
                "selected_option": index % 4,
                "response_time_seconds": 55,
                "confidence": 0.8,
            }
            for index, question in enumerate(session["questions"])
        ]
        submitted = await self.client.post(
            f"/api/v1/planner/diagnostics/{session['diagnostic_id']}/submit",
            json={"student_id": "student_diagnostic", "responses": responses},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        result = submitted.json()
        self.assertEqual(result["objective_evidence_count"], 10)
        self.assertEqual(result["correct_count"], 10)
        self.assertEqual(
            {item["source_type"] for item in result["knowledge_evidence"]},
            {"adaptive_diagnostic"},
        )

    async def test_multi_chapter_diagnostic_covers_every_selected_scope(self) -> None:
        catalog = self.container.curriculum_catalog.subject_catalog("mathematics")
        edition = next(
            item
            for item in catalog["editions"]
            if sum(len(volume["chapters"]) for volume in item["volumes"]) >= 6
        )
        chapter_ids = [
            chapter["id"]
            for volume in edition["volumes"]
            for chapter in volume["chapters"]
        ][:3]
        created = await self.client.post(
            "/api/v1/planner/diagnostics",
            json={
                "student_id": "multi_chapter_diagnostic",
                "grade": "grade_11",
                "subject": "mathematics",
                "curriculum_version": edition["id"],
                "chapter_ids": chapter_ids,
            },
        )

        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["chapter_ids"], chapter_ids)
        self.assertEqual(session["scope_type"], "multi_chapter")
        self.assertEqual(
            {question["scope_id"] for question in session["questions"]},
            set(chapter_ids),
        )
        self.assertTrue(
            all(question["scope_label"] for question in session["questions"])
        )
        model_context = self.fake_diagnostic.calls[-1]
        self.assertTrue(
            all(chapter_id in model_context["knowledge_context"] for chapter_id in chapter_ids)
        )
        self.assertIn("覆盖全部所选范围", model_context["coverage_instruction"])
        self.assertTrue(model_context["knowledge_sources"])
        self.assertTrue(model_context["slot_blueprint"])

        responses = [
            {
                "question_id": question["question_id"],
                "selected_option": index % 4,
                "response_time_seconds": 45,
                "confidence": 0.8,
            }
            for index, question in enumerate(session["questions"])
        ]
        submitted = await self.client.post(
            f"/api/v1/planner/diagnostics/{session['diagnostic_id']}/submit",
            json={"student_id": "multi_chapter_diagnostic", "responses": responses},
        )

        self.assertEqual(submitted.status_code, 200, submitted.text)
        evidence_scopes = {
            item["knowledge_id"].rsplit("_", 1)[0]
            for item in submitted.json()["knowledge_evidence"]
        }
        self.assertEqual(evidence_scopes, set(chapter_ids))

    async def test_quick_diagnostic_retries_invalid_knowledge_citation(self) -> None:
        valid_generator = self.fake_diagnostic

        class InvalidCitationThenValid:
            def __init__(self) -> None:
                self.calls = 0

            @property
            def available(self) -> bool:
                return True

            async def generate(self, context: dict):
                self.calls += 1
                result = await valid_generator.generate(context)
                if self.calls != 1:
                    return result
                questions = list(result.questions)
                questions[0] = questions[0].model_copy(
                    update={"source_chunk_id": "not_in_retrieved_knowledge"}
                )
                return result.model_copy(update={"questions": questions})

        retrying = InvalidCitationThenValid()
        self.container.diagnostics.generator = retrying
        created = await self.client.post(
            "/api/v1/planner/diagnostics",
            json={
                "student_id": "grounding_retry_student",
                "grade": "grade_11",
                "subject": "mathematics",
                "curriculum_version": "people_education_a",
                "chapter_id": "MATH-DERIVATIVE",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["generation_mode"], "llm")
        self.assertEqual(session["grounding"]["generation_attempts"], 2)
        self.assertEqual(retrying.calls, 2)

    async def test_multi_chapter_diagnostic_rejects_six_scopes(self) -> None:
        catalog = self.container.curriculum_catalog.subject_catalog("mathematics")
        edition = next(
            item
            for item in catalog["editions"]
            if sum(len(volume["chapters"]) for volume in item["volumes"]) >= 6
        )
        chapter_ids = [
            chapter["id"]
            for volume in edition["volumes"]
            for chapter in volume["chapters"]
        ][:6]

        created = await self.client.post(
            "/api/v1/planner/diagnostics",
            json={
                "student_id": "too_many_chapter_diagnostic",
                "grade": "grade_11",
                "subject": "mathematics",
                "curriculum_version": edition["id"],
                "chapter_ids": chapter_ids,
            },
        )

        self.assertEqual(created.status_code, 422, created.text)

    async def test_quick_diagnostic_model_failure_uses_fixed_bank_for_whole_book(self) -> None:
        class BrokenDiagnosticGenerator:
            @property
            def available(self) -> bool:
                return True

            async def generate(self, context: dict):
                raise RuntimeError("invalid structured model output")

        self.container.diagnostics.generator = BrokenDiagnosticGenerator()
        catalog = self.container.curriculum_catalog.subject_catalog("mathematics")
        edition = next(item for item in catalog["editions"] if item["volumes"])
        created = await self.client.post(
            "/api/v1/planner/diagnostics",
            json={
                "student_id": "whole_book_student",
                "grade": "grade_12",
                "subject": "mathematics",
                "curriculum_version": edition["id"],
                "chapter_id": "__all_chapters__",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["scope_type"], "whole_book")
        self.assertEqual(session["generation_mode"], "fixed_bank_fallback")
        self.assertEqual(session["grounding"]["mode"], "verified_question_bank")
        self.assertTrue(session["grounding"]["scope_match_verified"])
        self.assertTrue(
            all(
                item["provenance"]["mode"] == "verified_question_bank"
                for item in session["questions"]
            )
        )
        self.assertEqual(session["question_count"], 10)
        self.assertGreaterEqual(
            len({item["knowledge_focus"] for item in session["questions"]}), 4
        )
        self.assertTrue(any(item.get("prompt_html") for item in session["questions"]))
        self.assertNotIn("correct_option", created.text)
        self.assertNotIn("explanation", created.text)

    def test_quick_diagnostic_repairs_explicit_model_answer_index(self) -> None:
        question = {
            "options": ["20", "40", "80", "160"],
            "correct_option": 2,
            "explanation": "计算可得系数为 40，本题正确项为 40。",
        }
        self.container.diagnostics._reconcile_explicit_answer(question)
        self.assertEqual(question["correct_option"], 1)
if __name__ == "__main__":
    unittest.main()
