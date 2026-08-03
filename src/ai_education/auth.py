"""Student registration, password verification and opaque MySQL sessions."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pymysql
from pydantic import Field, field_validator, model_validator

from ai_education.core.errors import InputValidationError
from ai_education.domain.enums import Grade
from ai_education.domain.protocols import StrictModel
from ai_education.mysql_persistence import MySQLPersistence


class StudentRegistrationInput(StrictModel):
    student_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    student_name: str = Field(min_length=2, max_length=64)
    grade: Grade
    province_code: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9_-]+$")
    target_exam_year: int = Field(ge=2026, le=2040)

    @field_validator("student_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("student_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def passwords_match(self) -> StudentRegistrationInput:
        if self.password != self.password_confirmation:
            raise ValueError("两次输入的密码不一致")
        return self


class StudentLoginInput(StrictModel):
    student_id: str = Field(min_length=4, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True

    @field_validator("student_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()


class TeacherRegistrationInput(StrictModel):
    teacher_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    teacher_name: str = Field(min_length=2, max_length=64)
    school_name: str = Field(min_length=2, max_length=128)
    subject: str | None = Field(default=None, max_length=32)

    @field_validator("teacher_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("teacher_name", "school_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def passwords_match(self) -> TeacherRegistrationInput:
        if self.password != self.password_confirmation:
            raise ValueError("两次输入的密码不一致")
        return self


class TeacherLoginInput(StrictModel):
    teacher_id: str = Field(min_length=4, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True

    @field_validator("teacher_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + "$".join(
        base64.urlsafe_b64encode(value).decode("ascii").rstrip("=") for value in (salt, derived)
    )


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"), salt=_decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return secrets.compare_digest(derived, _decode(expected))
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, persistence: MySQLPersistence | None, *, session_hours: int = 168) -> None:
        self.persistence = persistence
        self.session_hours = session_hours

    def _store(self) -> MySQLPersistence:
        if self.persistence is None:
            raise InputValidationError("账号服务尚未配置 MySQL，暂时无法注册或登录")
        return self.persistence

    @staticmethod
    def profile(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "student",
            "studentName": row["student_name"],
            "studentId": row["student_id"],
            "grade": row["grade"],
            "provinceCode": row["province_code"],
            "targetExamYear": int(row["target_exam_year"]),
        }

    @staticmethod
    def teacher_profile(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "teacher",
            "teacherName": row["teacher_name"],
            "teacherId": row["teacher_id"],
            "schoolName": row["school_name"],
            "subject": row.get("subject"),
        }

    def register(self, body: StudentRegistrationInput) -> dict[str, Any]:
        store = self._store()
        try:
            student = store.create_student(
                {
                    "student_id": body.student_id,
                    "student_name": body.student_name,
                    "grade": body.grade.value,
                    "province_code": body.province_code,
                    "target_exam_year": body.target_exam_year,
                },
                _password_hash(body.password),
            )
        except pymysql.err.IntegrityError as exc:
            if exc.args and exc.args[0] == 1062:
                raise InputValidationError("该学习账号已经注册，请直接登录") from exc
            raise
        return self._issue_session(student, remember=True)

    def login(self, body: StudentLoginInput) -> dict[str, Any]:
        store = self._store()
        student = store.student_by_account(body.student_id)
        if (
            not student
            or not student["is_active"]
            or not _verify_password(body.password, student["password_hash"])
        ):
            raise InputValidationError("学习账号或密码不正确")
        return self._issue_session(student, remember=body.remember)

    def register_teacher(self, body: TeacherRegistrationInput) -> dict[str, Any]:
        store = self._store()
        try:
            teacher = store.create_teacher(
                {
                    "teacher_id": body.teacher_id,
                    "teacher_name": body.teacher_name,
                    "school_name": body.school_name,
                    "subject": body.subject,
                },
                _password_hash(body.password),
            )
        except pymysql.err.IntegrityError as exc:
            if exc.args and exc.args[0] == 1062:
                raise InputValidationError("该教师账号已经注册，请直接登录") from exc
            raise
        return self._issue_teacher_session(teacher, remember=True)

    def login_teacher(self, body: TeacherLoginInput) -> dict[str, Any]:
        teacher = self._store().teacher_by_account(body.teacher_id)
        if (
            not teacher
            or not teacher["is_active"]
            or not _verify_password(body.password, teacher["password_hash"])
        ):
            raise InputValidationError("教师账号或密码不正确")
        return self._issue_teacher_session(teacher, remember=body.remember)

    def _issue_session(self, student: dict[str, Any], *, remember: bool) -> dict[str, Any]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        hours = self.session_hours if remember else min(self.session_hours, 12)
        expires_at = datetime.now(UTC) + timedelta(hours=hours)
        self._store().create_auth_session(token_hash, int(student["id"]), expires_at)
        return {
            "access_token": raw_token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "profile": self.profile(student),
        }

    def _issue_teacher_session(self, teacher: dict[str, Any], *, remember: bool) -> dict[str, Any]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        hours = self.session_hours if remember else min(self.session_hours, 12)
        expires_at = datetime.now(UTC) + timedelta(hours=hours)
        self._store().create_teacher_auth_session(token_hash, int(teacher["id"]), expires_at)
        return {
            "access_token": raw_token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "profile": self.teacher_profile(teacher),
        }

    def authenticate(self, raw_token: str) -> dict[str, Any]:
        if not raw_token:
            raise InputValidationError("登录状态无效，请重新登录")
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
        student = self._store().resolve_auth_session(token_hash)
        if student:
            return self.profile(student)
        teacher = self._store().resolve_teacher_auth_session(token_hash)
        if teacher:
            return self.teacher_profile(teacher)
        raise InputValidationError("登录已过期，请重新登录")

    def logout(self, raw_token: str) -> None:
        if raw_token and self.persistence is not None:
            token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
            self.persistence.delete_auth_session(token_hash)
            self.persistence.delete_teacher_auth_session(token_hash)


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""
