"""Teacher classrooms, student membership, notices and diagnostic assignments."""

from __future__ import annotations

import hashlib
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


class ClassroomJoinPolicyInput(StrictModel):
    join_policy: Literal["open", "approval"]


class StudentClassroomJoinPolicyInput(StrictModel):
    student_join_policy: Literal["open", "approval"]


class ClassroomLeaveDecisionInput(StrictModel):
    decision: Literal["approved", "rejected"]
    reviewer_note: str | None = Field(default=None, max_length=500)

    @field_validator("reviewer_note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ClassroomOwnerTransferInput(StrictModel):
    teacher_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


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


class BatchAnnouncementInput(AnnouncementCreateInput):
    classroom_ids: list[int] = Field(min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


class BatchExamAssignmentInput(ExamAssignmentInput):
    classroom_ids: list[int] = Field(min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


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

    def join_teacher_classroom(self, teacher_id: str, body: ClassroomJoinInput) -> dict:
        classroom = self._store().join_teacher_classroom(teacher_id, body.class_code)
        if not classroom:
            raise InputValidationError("班级码不存在、班级已停用或教师账号无效")
        return classroom

    def list_classroom_teachers(self, teacher_id: str, classroom_id: int) -> list[dict]:
        members = self._store().list_classroom_teachers(teacher_id, classroom_id)
        if members is None:
            raise InputValidationError("班级不存在或当前教师未加入该班级")
        return members

    def remove_classroom_teacher(
        self, teacher_id: str, classroom_id: int, member_teacher_id: str
    ) -> dict:
        member = self._store().remove_classroom_teacher(teacher_id, classroom_id, member_teacher_id)
        if not member:
            raise InputValidationError("教师成员不存在，或当前账号没有移除权限")
        return member

    def request_teacher_classroom_leave(self, teacher_id: str, classroom_id: int) -> dict:
        request = self._store().create_teacher_classroom_leave_request(
            teacher_id, classroom_id, f"teacher_leave_{uuid4().hex[:20]}"
        )
        if not request:
            raise InputValidationError("你不是该班级的协作教师，无法提交退班申请")
        return request

    def review_teacher_classroom_leave(
        self, teacher_id: str, request_id: str, body: ClassroomLeaveDecisionInput
    ) -> dict:
        request = self._store().review_teacher_leave_request(
            teacher_id, request_id, body.decision, body.reviewer_note
        )
        if not request:
            raise InputValidationError("协作教师退班申请不存在、已处理或不属于当前班主任")
        return request

    def transfer_classroom_owner(
        self, teacher_id: str, classroom_id: int, body: ClassroomOwnerTransferInput
    ) -> dict:
        classroom = self._store().transfer_classroom_owner(
            teacher_id, classroom_id, body.teacher_id
        )
        if not classroom:
            raise InputValidationError(
                "仅班主任可将职权转给在班且没有待处理退班申请的协作教师"
            )
        return classroom

    def review_teacher_join(
        self,
        teacher_id: str,
        classroom_id: int,
        member_teacher_id: str,
        decision: Literal["approved", "rejected"],
    ) -> dict:
        member = self._store().review_teacher_join(
            teacher_id, classroom_id, member_teacher_id, decision
        )
        if not member:
            raise InputValidationError("加入申请不存在，或当前账号没有审批权限")
        return member

    def update_classroom_join_policy(
        self, teacher_id: str, classroom_id: int, body: ClassroomJoinPolicyInput
    ) -> dict:
        classroom = self._store().update_classroom_join_policy(
            teacher_id, classroom_id, body.join_policy
        )
        if not classroom:
            raise InputValidationError("仅班级创建者可以修改加入方式")
        return classroom

    def update_student_classroom_join_policy(
        self, teacher_id: str, classroom_id: int, body: StudentClassroomJoinPolicyInput
    ) -> dict:
        classroom = self._store().update_student_classroom_join_policy(
            teacher_id, classroom_id, body.student_join_policy
        )
        if not classroom:
            raise InputValidationError("仅班主任可以修改学生入班方式")
        return classroom

    def review_student_classroom_join(
        self, teacher_id: str, request_id: str, body: ClassroomLeaveDecisionInput
    ) -> dict:
        request = self._store().review_student_classroom_join_request(
            teacher_id, request_id, body.decision, body.reviewer_note
        )
        if not request:
            raise InputValidationError("入班申请不存在、已处理或不属于当前班主任")
        return request

    def teacher_dashboard(self, teacher_id: str) -> dict:
        classrooms = self._store().list_teacher_classrooms(teacher_id)
        classroom_ids = [int(item["id"]) for item in classrooms]
        join_requests = self._store().list_teacher_classroom_join_requests(teacher_id)
        leave_requests = self._store().list_teacher_classroom_leave_requests(teacher_id)
        leave_requests.extend(self._store().list_teacher_leave_requests(teacher_id))
        leave_requests.sort(key=lambda item: item.get("requested_at") or datetime.min)
        return {
            "classrooms": classrooms,
            "announcements": self._store().list_classroom_announcements(classroom_ids),
            "exam_assignments": self._store().list_classroom_exam_assignments(classroom_ids),
            "join_requests": join_requests,
            "leave_requests": leave_requests,
        }

    def classroom_detail(self, teacher_id: str, classroom_id: int) -> dict:
        classroom = self._store().teacher_classroom(teacher_id, classroom_id)
        members = self._store().classroom_members_for_teacher(teacher_id, classroom_id)
        if not classroom or members is None:
            raise InputValidationError("班级不存在或当前教师未加入该班级")
        join_requests = self._store().list_teacher_classroom_join_requests(
            teacher_id, classroom_id=classroom_id
        )
        leave_requests = self._store().list_teacher_classroom_leave_requests(
            teacher_id, classroom_id=classroom_id
        )
        leave_requests.extend(
            self._store().list_teacher_leave_requests(teacher_id, classroom_id=classroom_id)
        )
        leave_requests.sort(key=lambda item: item.get("requested_at") or datetime.min)
        return {
            "classroom": classroom,
            "students": members,
            "announcements": self._store().list_classroom_announcements([classroom_id]),
            "exam_assignments": self._store().list_classroom_exam_assignments([classroom_id]),
            "join_requests": join_requests,
            "leave_requests": leave_requests,
        }

    def join_classroom(self, student_id: str, body: ClassroomJoinInput) -> dict:
        classroom = self._store().join_classroom(
            student_id, body.class_code, f"join_{uuid4().hex[:20]}"
        )
        if not classroom:
            raise InputValidationError("班级码不存在、已停用或学生账号无效")
        return classroom

    def student_portal(self, student_id: str) -> dict:
        classrooms = self._store().list_student_classrooms(student_id)
        classroom_ids = [int(item["id"]) for item in classrooms]
        return {
            "classrooms": classrooms,
            "announcements": self._store().list_classroom_announcements(classroom_ids),
            "exam_assignments": self._store().list_student_classroom_exam_assignments(
                student_id, classroom_ids
            ),
            "join_requests": self._store().list_student_classroom_join_requests(student_id),
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
            raise InputValidationError("班级不存在或当前教师无发布权限")
        return saved

    def publish_announcements_batch(self, teacher_id: str, body: BatchAnnouncementInput) -> dict:
        key = body.idempotency_key or uuid4().hex
        results: list[dict] = []
        failed: list[dict] = []
        for classroom_id in dict.fromkeys(body.classroom_ids):
            digest = hashlib.sha256(f"{key}:{classroom_id}".encode()).hexdigest()[:28]
            try:
                saved = self._store().create_announcement(
                    teacher_id,
                    classroom_id,
                    {"announcement_id": f"batch_notice_{digest}", **body.model_dump(mode="json")},
                )
                if saved:
                    results.append(saved)
                else:
                    failed.append(
                        {"classroom_id": classroom_id, "reason": "无发布权限或班级不存在"}
                    )
            except pymysql.err.IntegrityError as exc:
                if exc.args and exc.args[0] == 1062:
                    existing = self._store().classroom_announcement(f"batch_notice_{digest}")
                    if existing:
                        results.append(existing)
                        continue
                failed.append({"classroom_id": classroom_id, "reason": str(exc)})
            except Exception as exc:
                failed.append({"classroom_id": classroom_id, "reason": str(exc)})
        return {"succeeded": results, "failed": failed, "requested": len(set(body.classroom_ids))}

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
            raise InputValidationError("班级不存在或当前教师无发布权限")
        return saved

    def exam_assignment_results(self, teacher_id: str, assignment_id: str) -> dict:
        results = self._store().teacher_exam_assignment_results(teacher_id, assignment_id)
        if not results:
            raise InputValidationError("诊断任务不存在或当前教师无权查看")
        return results

    def save_exam_assignments_batch(
        self, teacher_id: str, body: BatchExamAssignmentInput
    ) -> dict:
        key = body.idempotency_key or uuid4().hex
        results: list[dict] = []
        failed: list[dict] = []
        for classroom_id in dict.fromkeys(body.classroom_ids):
            digest = hashlib.sha256(f"{key}:{classroom_id}".encode()).hexdigest()[:28]
            try:
                saved = self._store().save_exam_assignment(
                    teacher_id,
                    classroom_id,
                    {**body.model_dump(mode="json"), "assignment_id": f"batch_assignment_{digest}"},
                )
                if saved:
                    results.append(saved)
                else:
                    failed.append(
                        {"classroom_id": classroom_id, "reason": "无发布权限或班级不存在"}
                    )
            except pymysql.err.IntegrityError as exc:
                if exc.args and exc.args[0] == 1062:
                    existing = self._store().classroom_exam_assignment(f"batch_assignment_{digest}")
                    if existing:
                        results.append(existing)
                        continue
                failed.append({"classroom_id": classroom_id, "reason": str(exc)})
            except Exception as exc:
                failed.append({"classroom_id": classroom_id, "reason": str(exc)})
        return {"succeeded": results, "failed": failed, "requested": len(set(body.classroom_ids))}
