from __future__ import annotations

import inspect
import unittest
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import SCHEMA_STATEMENTS, MySQLPersistence
from ai_education.teacher_platform import (
    ClassroomJoinInput,
    ClassroomLeaveDecisionInput,
    StudentClassroomJoinPolicyInput,
    TeacherPlatformService,
)


class InMemoryStudentJoinStore:
    def __init__(self) -> None:
        self.policy = "open"
        self.membership_status: str | None = None
        self.request: dict[str, Any] | None = None

    def update_student_classroom_join_policy(
        self, teacher_id: str, classroom_id: int, policy: str
    ) -> dict[str, Any] | None:
        if teacher_id != "teacher_01" or classroom_id != 7:
            return None
        self.policy = policy
        return {"id": 7, "student_join_policy": policy}

    def join_classroom(
        self, student_id: str, class_code: str, request_id: str
    ) -> dict[str, Any] | None:
        if student_id != "student_01" or class_code != "ABCD2345":
            return None
        if self.policy == "open":
            self.membership_status = "active"
            return {
                "id": 7,
                "class_name": "高二一班",
                "membership_status": "active",
            }
        self.request = {
            "request_id": request_id,
            "classroom_id": 7,
            "class_name": "高二一班",
            "student_id": student_id,
            "student_name": "测试学生",
            "status": "pending",
        }
        return {
            "id": 7,
            "class_name": "高二一班",
            "membership_status": "pending",
            "join_request_id": request_id,
        }

    def review_student_classroom_join_request(
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
        self.request["reviewer_note"] = reviewer_note
        if decision == "approved":
            self.membership_status = "active"
        return self.request.copy()


class StudentClassroomJoinApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryStudentJoinStore()
        self.service = TeacherPlatformService(self.store)  # type: ignore[arg-type]

    def test_student_waits_for_owner_approval_before_becoming_member(self) -> None:
        policy = self.service.update_student_classroom_join_policy(
            "teacher_01",
            7,
            StudentClassroomJoinPolicyInput(student_join_policy="approval"),
        )
        self.assertEqual(policy["student_join_policy"], "approval")

        requested = self.service.join_classroom(
            "student_01", ClassroomJoinInput(class_code="abcd2345")
        )
        self.assertEqual(requested["membership_status"], "pending")
        self.assertIsNone(self.store.membership_status)

        approved = self.service.review_student_classroom_join(
            "teacher_01",
            requested["join_request_id"],
            ClassroomLeaveDecisionInput(decision="approved"),
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.store.membership_status, "active")

    def test_non_owner_cannot_change_policy_or_review_request(self) -> None:
        with self.assertRaises(InputValidationError):
            self.service.update_student_classroom_join_policy(
                "teacher_02",
                7,
                StudentClassroomJoinPolicyInput(student_join_policy="approval"),
            )

        self.service.update_student_classroom_join_policy(
            "teacher_01",
            7,
            StudentClassroomJoinPolicyInput(student_join_policy="approval"),
        )
        requested = self.service.join_classroom(
            "student_01", ClassroomJoinInput(class_code="ABCD2345")
        )
        with self.assertRaises(InputValidationError):
            self.service.review_student_classroom_join(
                "teacher_02",
                requested["join_request_id"],
                ClassroomLeaveDecisionInput(decision="rejected"),
            )

    def test_mysql_owner_boundary_and_schema_are_explicit(self) -> None:
        listing = inspect.getsource(MySQLPersistence.list_teacher_classroom_join_requests)
        review = inspect.getsource(MySQLPersistence.review_student_classroom_join_request)
        schema = "\n".join(SCHEMA_STATEMENTS)

        self.assertIn("owner.teacher_id=%s", listing)
        self.assertIn("c.teacher_pk=%s", review)
        self.assertIn("student_join_policy", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS classroom_join_requests", schema)
        self.assertIn("UNIQUE KEY uk_classroom_join_member", schema)


if __name__ == "__main__":
    unittest.main()
