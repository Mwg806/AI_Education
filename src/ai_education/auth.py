"""Passwordless phone verification and opaque MySQL sessions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pymysql
from pydantic import Field, field_validator

from ai_education.core.errors import InputValidationError
from ai_education.domain.enums import Grade
from ai_education.domain.protocols import StrictModel
from ai_education.mysql_persistence import MySQLPersistence
from ai_education.phone_verification import normalize_phone


class VerificationCodeInput(StrictModel):
    phone: str = Field(min_length=11, max_length=20)
    purpose: str = Field(pattern=r"^(register|login)$")
    role: str = Field(pattern=r"^(student|teacher)$")


class StudentRegistrationInput(StrictModel):
    student_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    phone: str = Field(min_length=11, max_length=20)
    verification_code: str = Field(pattern=r"^\d{4,8}$")
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


class StudentLoginInput(StrictModel):
    student_id: str = Field(min_length=4, max_length=64)
    phone: str = Field(min_length=11, max_length=20)
    verification_code: str = Field(pattern=r"^\d{4,8}$")
    remember: bool = True

    @field_validator("student_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()


class TeacherRegistrationInput(StrictModel):
    teacher_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    phone: str = Field(min_length=11, max_length=20)
    verification_code: str = Field(pattern=r"^\d{4,8}$")
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


class TeacherLoginInput(StrictModel):
    teacher_id: str = Field(min_length=4, max_length=64)
    phone: str = Field(min_length=11, max_length=20)
    verification_code: str = Field(pattern=r"^\d{4,8}$")
    remember: bool = True

    @field_validator("teacher_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()


class AuthService:
    def __init__(
        self,
        persistence: MySQLPersistence | None,
        phone_auth: Any | None = None,
        *,
        session_hours: int = 168,
    ) -> None:
        self.persistence = persistence
        self.phone_auth = phone_auth
        self.session_hours = session_hours

    def _store(self) -> MySQLPersistence:
        if self.persistence is None:
            raise InputValidationError("账号服务尚未配置 MySQL，暂时无法注册或登录")
        return self.persistence

    def send_verification_code(self, body: VerificationCodeInput, client_ip: str) -> dict[str, Any]:
        if self.phone_auth is None:
            raise InputValidationError("手机号认证服务尚未启用")
        phone, phone_e164 = normalize_phone(body.phone)
        store = self._store()
        store.guard_sms_send(phone_e164, client_ip, body.purpose, body.role)
        self.phone_auth.send_code(phone)
        store.record_sms_send(phone_e164, client_ip, body.purpose, body.role)
        return {"sent": True, "retry_after": 60}

    def _verify_code(self, phone: str, code: str, purpose: str, role: str) -> str:
        if self.phone_auth is None:
            raise InputValidationError("手机号认证服务尚未启用")
        local_phone, phone_e164 = normalize_phone(phone)
        self._store().guard_sms_verify(phone_e164, purpose, role)
        if not self.phone_auth.check_code(local_phone, code):
            self._store().record_sms_failure(phone_e164, purpose, role)
            raise InputValidationError("手机号验证码不正确或已过期")
        self._store().consume_sms_challenge(phone_e164, purpose, role)
        return phone_e164

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
        phone_e164 = self._verify_code(body.phone, body.verification_code, "register", "student")
        try:
            student = self._store().create_student(
                {
                    "student_id": body.student_id,
                    "student_name": body.student_name,
                    "grade": body.grade.value,
                    "province_code": body.province_code,
                    "target_exam_year": body.target_exam_year,
                },
                None,
                phone_e164=phone_e164,
            )
        except pymysql.err.IntegrityError as exc:
            if exc.args and exc.args[0] == 1062:
                raise InputValidationError("该学号已经注册，请直接登录") from exc
            raise
        return self._issue_session(student, remember=True)

    def login(self, body: StudentLoginInput) -> dict[str, Any]:
        student = self._store().student_by_account(body.student_id)
        _, phone_e164 = normalize_phone(body.phone)
        if not student or not student["is_active"] or student.get("phone_e164") != phone_e164:
            raise InputValidationError("学号或手机号不正确")
        self._verify_code(body.phone, body.verification_code, "login", "student")
        return self._issue_session(student, remember=body.remember)

    def register_teacher(self, body: TeacherRegistrationInput) -> dict[str, Any]:
        phone_e164 = self._verify_code(body.phone, body.verification_code, "register", "teacher")
        try:
            teacher = self._store().create_teacher(
                {
                    "teacher_id": body.teacher_id,
                    "teacher_name": body.teacher_name,
                    "school_name": body.school_name,
                    "subject": body.subject,
                },
                None,
                phone_e164=phone_e164,
            )
        except pymysql.err.IntegrityError as exc:
            if exc.args and exc.args[0] == 1062:
                raise InputValidationError("该教师账号已经注册，请直接登录") from exc
            raise
        return self._issue_teacher_session(teacher, remember=True)

    def login_teacher(self, body: TeacherLoginInput) -> dict[str, Any]:
        teacher = self._store().teacher_by_account(body.teacher_id)
        _, phone_e164 = normalize_phone(body.phone)
        if not teacher or not teacher["is_active"] or teacher.get("phone_e164") != phone_e164:
            raise InputValidationError("教师账号或手机号不正确")
        self._verify_code(body.phone, body.verification_code, "login", "teacher")
        return self._issue_teacher_session(teacher, remember=body.remember)

    def _issue_session(self, student: dict[str, Any], *, remember: bool) -> dict[str, Any]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(
            hours=self.session_hours if remember else min(self.session_hours, 12)
        )
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
        expires_at = datetime.now(UTC) + timedelta(
            hours=self.session_hours if remember else min(self.session_hours, 12)
        )
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
