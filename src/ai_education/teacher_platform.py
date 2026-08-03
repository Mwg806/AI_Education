"""Teacher classrooms, student membership, notices and diagnostic assignments."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Literal
from uuid import uuid4

import pymysql
from pydantic import Field, field_validator

from ai_education.core.errors import InputValidationError
from ai_education.domain.enums import Grade, Subject
from ai_education.domain.protocols import StrictModel
from ai_education.mysql_persistence import MySQLPersistence


class ClassroomCreateInput(StrictModel):
    class_name: str = Field(min_length=2, max_length=96)
    grade: Grade
    subject: Subject | None = None

    @field_validator("class_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ClassroomJoinInput(StrictModel):
    class_code: str = Field(min_length=8, max_length=8, pattern=r"^[A-Za-z0-9]+$")

    @field_validator("class_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class ClassroomLeaveDecisionInput(StrictModel):
    decision: Literal["approved", "rejected"]
    reviewer_note: str | None = Field(default=None, max_length=500)

    @field_validator("reviewer_note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AnnouncementCreateInput(StrictModel):
    announcement_type: Literal["homework", "holiday", "notice"] = "notice"
    title: str = Field(min_length=2, max_length=160)
    content: str = Field(min_length=1, max_length=10_000)
    due_at: datetime | None = None

    @field_validator("title", "content")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class ExamAssignmentInput(StrictModel):
    assignment_id: str | None = Field(default=None, max_length=96)
    paper_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=2, max_length=160)
    due_at: datetime | None = None
    status: Literal["published", "closed", "archived"] = "published"

    @field_validator("paper_id", "title")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class TeacherPlatformService:
    def __init__(self, persistence: MySQLPersistence | None) -> None:
        self.persistence = persistence

    def _store(self) -> MySQLPersistence:
        if self.persistence is None:
            raise InputValidationError("教师平台需要启用 MySQL 持久化")
        return self.persistence

    def create_classroom(self, teacher_id: str, body: ClassroomCreateInput) -> dict:
        for _ in range(8):
            code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
            try:
                return self._store().create_classroom(
                    teacher_id,
                    {
                        "class_code": code,
                        "class_name": body.class_name,
                        "grade": body.grade.value,
                        "subject": body.subject.value if body.subject else None,
                    },
                )
            except pymysql.err.IntegrityError as exc:
                if exc.args and exc.args[0] == 1062:
                    continue
                raise
        raise InputValidationError("班级码生成冲突，请重新创建班级")

    def teacher_dashboard(self, teacher_id: str) -> dict:
        classrooms = self._store().list_teacher_classrooms(teacher_id)
        classroom_ids = [int(item["id"]) for item in classrooms]
        return {
            "classrooms": classrooms,
            "announcements": self._store().list_classroom_announcements(classroom_ids),
            "exam_assignments": self._store().list_classroom_exam_assignments(classroom_ids),
            "leave_requests": self._store().list_teacher_classroom_leave_requests(
                teacher_id
            ),
        }

    def classroom_detail(self, teacher_id: str, classroom_id: int) -> dict:
        classroom = self._store().teacher_classroom(teacher_id, classroom_id)
        members = self._store().classroom_members_for_teacher(teacher_id, classroom_id)
        if not classroom or members is None:
            raise InputValidationError("班级不存在或不属于当前教师")
        return {
            "classroom": classroom,
            "students": members,
            "announcements": self._store().list_classroom_announcements([classroom_id]),
            "exam_assignments": self._store().list_classroom_exam_assignments([classroom_id]),
            "leave_requests": self._store().list_teacher_classroom_leave_requests(
                teacher_id, classroom_id=classroom_id
            ),
        }

    def join_classroom(self, student_id: str, body: ClassroomJoinInput) -> dict:
        classroom = self._store().join_classroom(student_id, body.class_code)
        if not classroom:
            raise InputValidationError("班级码不存在、已停用或学生账号无效")
        return classroom

    def student_portal(self, student_id: str) -> dict:
        classrooms = self._store().list_student_classrooms(student_id)
        classroom_ids = [int(item["id"]) for item in classrooms]
        return {
            "classrooms": classrooms,
            "announcements": self._store().list_classroom_announcements(classroom_ids),
            "exam_assignments": self._store().list_classroom_exam_assignments(classroom_ids),
            "leave_requests": self._store().list_student_classroom_leave_requests(student_id),
        }

    def request_classroom_leave(self, student_id: str, classroom_id: int) -> dict:
        request = self._store().create_classroom_leave_request(
            student_id, classroom_id, f"leave_{uuid4().hex[:20]}"
        )
        if not request:
            raise InputValidationError("学生当前不在该班级，无法提交退出申请")
        return request

    def review_classroom_leave(
        self, teacher_id: str, request_id: str, body: ClassroomLeaveDecisionInput
    ) -> dict:
        request = self._store().review_classroom_leave_request(
            teacher_id, request_id, body.decision, body.reviewer_note
        )
        if not request:
            raise InputValidationError("退出申请不存在、已处理或不属于当前教师")
        return request

    def publish_announcement(
        self, teacher_id: str, classroom_id: int, body: AnnouncementCreateInput
    ) -> dict:
        saved = self._store().create_announcement(
            teacher_id,
            classroom_id,
            {
                "announcement_id": f"notice_{uuid4().hex[:16]}",
                **body.model_dump(mode="json"),
            },
        )
        if not saved:
            raise InputValidationError("班级不存在或不属于当前教师")
        return saved

    def save_exam_assignment(
        self, teacher_id: str, classroom_id: int, body: ExamAssignmentInput
    ) -> dict:
        saved = self._store().save_exam_assignment(
            teacher_id,
            classroom_id,
            {
                **body.model_dump(mode="json"),
                "assignment_id": body.assignment_id or f"assignment_{uuid4().hex[:16]}",
            },
        )
        if not saved:
            raise InputValidationError("班级不存在或不属于当前教师")
        return saved
