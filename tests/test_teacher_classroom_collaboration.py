from __future__ import annotations

import unittest
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.teacher_platform import (
    AnnouncementCreateInput,
    ClassroomJoinInput,
    ClassroomLeaveDecisionInput,
    ClassroomOwnerTransferInput,
    ExamAssignmentInput,
    TeacherPlatformService,
)


class CollaborationStore:
    def __init__(self) -> None:
        self.joined = False

    def join_teacher_classroom(self, teacher_id: str, class_code: str) -> dict[str, Any] | None:
        if teacher_id != "teacher_02" or class_code != "ABCD2345":
            return None
        self.joined = True
        return {
            "id": 7,
            "class_code": class_code,
            "class_name": "高三联合教学班",
            "teacher_access_role": "collaborator",
            "owner_teacher_name": "张老师",
        }

    def create_announcement(
        self, teacher_id: str, classroom_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not self.joined or teacher_id != "teacher_02" or classroom_id != 7:
            return None
        return {"classroom_id": classroom_id, **payload}

    def save_exam_assignment(
        self, teacher_id: str, classroom_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not self.joined or teacher_id != "teacher_02" or classroom_id != 7:
            return None
        return {"classroom_id": classroom_id, **payload}

    def list_teacher_classrooms(self, teacher_id: str) -> list[dict[str, Any]]:
        if teacher_id == "teacher_01":
            return [{"id": 7, "teacher_access_role": "owner"}]
        if teacher_id == "teacher_02" and self.joined:
            return [{"id": 7, "teacher_access_role": "collaborator"}]
        return []

    def list_classroom_announcements(self, classroom_ids: list[int]) -> list[dict[str, Any]]:
        return (
            [
                {
                    "classroom_id": 7,
                    "title": "班级共同通知",
                    "publisher_teacher_id": "teacher_01",
                }
            ]
            if 7 in classroom_ids
            else []
        )

    def list_classroom_exam_assignments(self, classroom_ids: list[int]) -> list[dict[str, Any]]:
        return (
            [
                {
                    "classroom_id": 7,
                    "title": "共同诊断卷",
                    "publisher_teacher_id": "teacher_02",
                }
            ]
            if 7 in classroom_ids
            else []
        )

    def teacher_exam_assignment_results(
        self, teacher_id: str, assignment_id: str
    ) -> dict[str, Any] | None:
        if teacher_id not in {"teacher_01", "teacher_02"} or assignment_id != "assignment_01":
            return None
        return {
            "assignment": {"assignment_id": assignment_id, "title": "共同诊断卷"},
            "summary": {"student_count": 1, "completed": 1},
            "students": [
                {
                    "student_id": "student_01",
                    "progress_status": "completed",
                    "learning_diagnosis": {"result": {"learning_state": {}}},
                }
            ],
        }

    def list_teacher_classroom_join_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        if teacher_id != "teacher_01" or classroom_id not in {None, 7}:
            return []
        return [{"request_id": "join_01", "classroom_id": 7, "status": "pending"}]

    def list_teacher_classroom_leave_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        if teacher_id != "teacher_01" or classroom_id not in {None, 7}:
            return []
        return [{"request_id": "leave_01", "classroom_id": 7, "status": "pending"}]

    def list_teacher_leave_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        return []
    def list_classroom_teachers(
        self, teacher_id: str, classroom_id: int
    ) -> list[dict[str, Any]] | None:
        if classroom_id != 7 or teacher_id not in {"teacher_01", "teacher_02"}:
            return None
        if teacher_id == "teacher_02" and not self.joined:
            return None
        return [
            {"teacher_id": "teacher_01", "role": "owner", "status": "active"},
            {
                "teacher_id": "teacher_02",
                "role": "collaborator",
                "status": "active",
            },
        ]


    def create_teacher_classroom_leave_request(
        self, teacher_id: str, classroom_id: int, request_id: str
    ) -> dict[str, Any] | None:
        if teacher_id != "teacher_02" or classroom_id != 7 or not self.joined:
            return None
        return {
            "request_id": request_id,
            "request_source": "collaborator",
            "classroom_id": 7,
            "applicant_id": "teacher_02",
            "applicant_name": "协作老师",
            "status": "pending",
        }

    def review_teacher_leave_request(
        self,
        teacher_id: str,
        request_id: str,
        decision: str,
        reviewer_note: str | None,
    ) -> dict[str, Any] | None:
        if teacher_id != "teacher_01" or not request_id.startswith("teacher_leave_"):
            return None
        if decision == "approved":
            self.joined = False
        return {
            "request_id": request_id,
            "request_source": "collaborator",
            "classroom_id": 7,
            "status": decision,
        }

    def transfer_classroom_owner(
        self, teacher_id: str, classroom_id: int, member_teacher_id: str
    ) -> dict[str, Any] | None:
        if (
            teacher_id != "teacher_01"
            or classroom_id != 7
            or member_teacher_id != "teacher_02"
            or not self.joined
        ):
            return None
        return {
            "id": 7,
            "teacher_access_role": "collaborator",
            "transferred_owner_teacher_id": "teacher_02",
        }


class TeacherClassroomCollaborationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CollaborationStore()
        self.service = TeacherPlatformService(self.store)  # type: ignore[arg-type]

    def test_teacher_joins_then_publishes_announcement_and_diagnostic(self) -> None:
        classroom = self.service.join_teacher_classroom(
            "teacher_02", ClassroomJoinInput(class_code="abcd2345")
        )
        self.assertEqual(classroom["teacher_access_role"], "collaborator")

        notice = self.service.publish_announcement(
            "teacher_02",
            7,
            AnnouncementCreateInput(
                announcement_type="notice",
                title="联合教研通知",
                content="请完成本周诊断。",
            ),
        )
        self.assertEqual(notice["classroom_id"], 7)

        assignment = self.service.save_exam_assignment(
            "teacher_02",
            7,
            ExamAssignmentInput(paper_id="paper_math_01", title="函数专项诊断"),
        )
        self.assertEqual(assignment["classroom_id"], 7)

    def test_collaborator_can_receive_student_diagnostic_results(self) -> None:
        self.service.join_teacher_classroom("teacher_02", ClassroomJoinInput(class_code="ABCD2345"))

        result = self.service.exam_assignment_results("teacher_02", "assignment_01")

        self.assertEqual(result["summary"]["completed"], 1)
        self.assertEqual(result["students"][0]["progress_status"], "completed")
        with self.assertRaises(InputValidationError):
            self.service.exam_assignment_results("teacher_outside", "assignment_01")

    def test_collaborator_sees_shared_content_but_not_leave_approvals(self) -> None:
        self.service.join_teacher_classroom("teacher_02", ClassroomJoinInput(class_code="ABCD2345"))

        collaborator_dashboard = self.service.teacher_dashboard("teacher_02")
        self.assertEqual(len(collaborator_dashboard["announcements"]), 1)
        self.assertEqual(len(collaborator_dashboard["exam_assignments"]), 1)
        self.assertEqual(collaborator_dashboard["leave_requests"], [])

        owner_dashboard = self.service.teacher_dashboard("teacher_01")
        self.assertEqual(len(owner_dashboard["leave_requests"]), 1)
        self.assertEqual(owner_dashboard["leave_requests"][0]["classroom_id"], 7)

    def test_collaborator_can_see_the_class_teacher_roster(self) -> None:
        self.service.join_teacher_classroom("teacher_02", ClassroomJoinInput(class_code="ABCD2345"))
        members = self.service.list_classroom_teachers("teacher_02", 7)
        self.assertEqual(
            [member["role"] for member in members],
            ["owner", "collaborator"],
        )

    def test_collaborator_leave_requires_owner_approval(self) -> None:
        self.service.join_teacher_classroom(
            "teacher_02", ClassroomJoinInput(class_code="ABCD2345")
        )

        request = self.service.request_teacher_classroom_leave("teacher_02", 7)
        self.assertEqual(request["request_source"], "collaborator")
        self.assertTrue(self.store.joined)

        reviewed = self.service.review_teacher_classroom_leave(
            "teacher_01",
            request["request_id"],
            ClassroomLeaveDecisionInput(decision="approved"),
        )
        self.assertEqual(reviewed["status"], "approved")
        self.assertFalse(self.store.joined)

    def test_owner_can_transfer_classroom_to_active_collaborator(self) -> None:
        self.service.join_teacher_classroom(
            "teacher_02", ClassroomJoinInput(class_code="ABCD2345")
        )

        classroom = self.service.transfer_classroom_owner(
            "teacher_01",
            7,
            ClassroomOwnerTransferInput(teacher_id="teacher_02"),
        )

        self.assertEqual(classroom["transferred_owner_teacher_id"], "teacher_02")

    def test_invalid_class_code_is_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            self.service.join_teacher_classroom(
                "teacher_03", ClassroomJoinInput(class_code="ZZZZ9999")
            )

    def test_schema_contains_teacher_membership_and_role(self) -> None:
        schema = "\n".join(SCHEMA_STATEMENTS)
        self.assertIn("CREATE TABLE IF NOT EXISTS classroom_teachers", schema)
        self.assertIn("idx_classroom_teachers_teacher", schema)
        self.assertIn("role VARCHAR(24)", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS classroom_teacher_leave_requests", schema)
        self.assertIn("uk_teacher_leave_member", schema)


if __name__ == "__main__":
    unittest.main()
