from __future__ import annotations

import unittest
from typing import Any

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import SCHEMA_STATEMENTS
from ai_education.teacher_platform import (
    AnnouncementCreateInput,
    ClassroomJoinInput,
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


if __name__ == "__main__":
    unittest.main()
