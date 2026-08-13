from __future__ import annotations

import inspect
import unittest
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import SCHEMA_STATEMENTS, MySQLPersistence
from ai_education.teacher_platform import (
    ClassroomLeaveDecisionInput,
    TeacherPlatformService,
)


class InMemoryClassroomStore:
    """Stateful test double for the approval boundary in TeacherPlatformService."""

    def __init__(self) -> None:
        self.membership_status = "active"
        self.request: dict[str, Any] | None = None

    def create_classroom_leave_request(
        self, student_id: str, classroom_id: int, request_id: str
    ) -> dict[str, Any] | None:
        if student_id != "student_01" or classroom_id != 7:
            return None
        if self.membership_status != "active":
            return None
        if self.request and self.request["status"] == "pending":
            return self.request.copy()
        self.request = {
            "request_id": request_id,
            "classroom_id": 7,
            "class_name": "高二一班",
            "student_id": "student_01",
            "student_name": "测试学生",
            "teacher_name": "测试教师",
            "status": "pending",
            "requested_at": "2026-08-03T12:00:00",
            "reviewed_at": None,
            "reviewer_note": None,
        }
        return self.request.copy()

    def review_classroom_leave_request(
        self,
        teacher_id: str,
        request_id: str,
        decision: str,
        reviewer_note: str | None,
    ) -> dict[str, Any] | None:
        if teacher_id != "teacher_01" or not self.request:
            return None
        if self.request["request_id"] != request_id or self.request["status"] != "pending":
            return None
        self.request["status"] = decision
        self.request["reviewed_at"] = "2026-08-03T12:05:00"
        self.request["reviewer_note"] = reviewer_note
        if decision == "approved":
            self.membership_status = "left"
        return self.request.copy()


class ClassroomLeaveWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryClassroomStore()
        self.service = TeacherPlatformService(self.store)  # type: ignore[arg-type]

    def test_student_stays_in_class_until_teacher_approves(self) -> None:
        requested = self.service.request_classroom_leave("student_01", 7)
        self.assertEqual(requested["status"], "pending")
        self.assertEqual(self.store.membership_status, "active")

        rejected = self.service.review_classroom_leave(
            "teacher_01",
            requested["request_id"],
            ClassroomLeaveDecisionInput(decision="rejected", reviewer_note="继续沟通"),
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.store.membership_status, "active")

        second = self.service.request_classroom_leave("student_01", 7)
        approved = self.service.review_classroom_leave(
            "teacher_01",
            second["request_id"],
            ClassroomLeaveDecisionInput(decision="approved"),
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.store.membership_status, "left")

    def test_pending_request_is_idempotent_and_other_teacher_cannot_review(self) -> None:
        first = self.service.request_classroom_leave("student_01", 7)
        second = self.service.request_classroom_leave("student_01", 7)
        self.assertEqual(first["request_id"], second["request_id"])
        with self.assertRaises(InputValidationError):
            self.service.review_classroom_leave(
                "teacher_02",
                first["request_id"],
                ClassroomLeaveDecisionInput(decision="approved"),
            )
        self.assertEqual(self.store.membership_status, "active")

    def test_mysql_permissions_bind_leave_visibility_and_review_to_class_owner(self) -> None:
        list_source = inspect.getsource(MySQLPersistence.list_teacher_classroom_leave_requests)
        review_source = inspect.getsource(MySQLPersistence.review_classroom_leave_request)

        self.assertIn("JOIN teachers t ON t.id=c.teacher_pk", list_source)
        self.assertIn('"t.teacher_id=%s"', list_source)
        self.assertIn("JOIN teachers t ON t.id=c.teacher_pk", review_source)
        self.assertIn("t.teacher_id=%s", review_source)

    def test_mysql_schema_contains_transactional_leave_request_table(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        self.assertIn("CREATE TABLE IF NOT EXISTS classroom_leave_requests", schema)
        self.assertIn("UNIQUE KEY uk_classroom_leave_member", schema)
        self.assertIn("fk_classroom_leave_classroom", schema)
        self.assertIn("fk_classroom_leave_student", schema)


if __name__ == "__main__":
    unittest.main()
