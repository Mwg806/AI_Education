"""Single-super-admin authentication and account lifecycle operations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import Field, field_validator

from ai_education.core.errors import InputValidationError
from ai_education.domain.protocols import StrictModel
from ai_education.mysql_persistence import MySQLPersistence
from ai_education.phone_verification import normalize_phone

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


def hash_admin_password(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("超级管理员密码至少需要 12 个字符")
    actual_salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        (
            "scrypt_v1",
            base64.b64encode(actual_salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        )
    )


def verify_admin_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_value, digest_value = encoded.split("$", 2)
        if scheme != "scrypt_v1":
            return False
        salt = base64.b64decode(salt_value, validate=True)
        expected = base64.b64decode(digest_value, validate=True)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def mask_phone(phone_e164: str | None) -> str:
    if not phone_e164:
        return "未绑定"
    local = phone_e164[3:] if phone_e164.startswith("+86") else phone_e164
    if len(local) < 7:
        return "已绑定"
    return f"{local[:3]}****{local[-4:]}"


class AdminLoginInput(StrictModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class AdminRebindCodeInput(StrictModel):
    phone: str = Field(min_length=11, max_length=20)


class AdminStudentPhoneRebindInput(AdminRebindCodeInput):
    verification_code: str = Field(pattern=r"^\d{4,8}$")
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 5:
            raise ValueError("操作原因至少需要 5 个字符")
        return normalized


class AdminAccountDeletionInput(StrictModel):
    confirm_account_id: str = Field(min_length=4, max_length=64)
    reason: str = Field(min_length=5, max_length=500)
    acknowledge_permanent_deletion: Literal[True]

    @field_validator("confirm_account_id")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 5:
            raise ValueError("操作原因至少需要 5 个字符")
        return normalized


class AdminService:
    def __init__(
        self,
        persistence: MySQLPersistence | None,
        phone_auth: Any | None,
        *,
        username: str,
        password_hash: str,
        session_hours: int = 8,
    ) -> None:
        self.persistence = persistence
        self.phone_auth = phone_auth
        self.username = username.strip().lower()
        self.password_hash = password_hash.strip()
        self.session_hours = session_hours

    @property
    def configured(self) -> bool:
        return bool(self.persistence and self.username and self.password_hash)

    def _store(self) -> MySQLPersistence:
        if self.persistence is None:
            raise InputValidationError("管理员服务需要启用 MySQL 持久化")
        return self.persistence

    def _require_configured(self) -> None:
        if not self.configured:
            raise InputValidationError("超级管理员账号尚未完成服务端配置")

    def login(
        self,
        body: AdminLoginInput,
        *,
        client_ip: str,
        user_agent: str,
    ) -> dict[str, Any]:
        self._require_configured()
        store = self._store()
        store.guard_admin_login(client_ip, body.username)
        username_matches = hmac.compare_digest(body.username, self.username)
        password_matches = verify_admin_password(body.password, self.password_hash)
        if not username_matches or not password_matches:
            store.record_admin_login_failure(client_ip, body.username)
            raise InputValidationError("管理员账号或密码不正确")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=self.session_hours)
        store.create_admin_session(
            token_hash,
            self.username,
            expires_at,
            client_ip[:45],
            user_agent[:255],
        )
        store.record_admin_audit(
            admin_username=self.username,
            action="admin.login",
            target_role=None,
            target_account_id=None,
            reason="超级管理员登录",
            metadata={},
            client_ip=client_ip,
        )
        return {
            "access_token": raw_token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "profile": {"role": "super_admin", "username": self.username},
        }

    def authenticate(self, raw_token: str) -> dict[str, str]:
        self._require_configured()
        if not raw_token:
            raise InputValidationError("管理员登录状态无效，请重新登录")
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
        session = self._store().resolve_admin_session(token_hash)
        if not session or session["admin_username"].lower() != self.username:
            raise InputValidationError("管理员登录已过期，请重新登录")
        return {"role": "super_admin", "username": self.username}

    def logout(self, raw_token: str) -> None:
        if not raw_token or self.persistence is None:
            return
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
        self.persistence.delete_admin_session(token_hash)

    def overview(self) -> dict[str, Any]:
        return self._store().admin_account_overview()

    def list_accounts(
        self,
        *,
        role: Literal["all", "student", "teacher"],
        query: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        rows = self._store().list_admin_accounts(
            role=role,
            query=query.strip(),
            limit=limit,
            offset=offset,
        )
        has_more = len(rows) > limit
        accounts = rows[:limit]
        for account in accounts:
            account["phone_masked"] = mask_phone(account.pop("phone_e164", None))
            account["is_active"] = bool(account["is_active"])
        return {
            "accounts": accounts,
            "has_more": has_more,
            "limit": limit,
            "offset": offset,
        }

    def account_impact(
        self, role: Literal["student", "teacher"], account_id: str
    ) -> dict[str, Any]:
        impact = self._store().admin_account_deletion_impact(role, account_id.lower())
        if not impact:
            raise InputValidationError("账号不存在")
        impact["phone_masked"] = mask_phone(impact.pop("phone_e164", None))
        impact["is_active"] = bool(impact["is_active"])
        return impact

    def send_student_rebind_code(
        self,
        student_id: str,
        body: AdminRebindCodeInput,
        *,
        admin_username: str,
        client_ip: str,
    ) -> dict[str, Any]:
        if self.phone_auth is None:
            raise InputValidationError("手机号认证服务尚未启用")
        student = self._store().student_by_account(student_id)
        if not student:
            raise InputValidationError("学生账号不存在")
        phone, phone_e164 = normalize_phone(body.phone)
        if student.get("phone_e164") == phone_e164:
            raise InputValidationError("新手机号与当前绑定手机号相同")
        self._store().guard_sms_send(phone_e164, client_ip, "admin_rebind", "student")
        self.phone_auth.send_code(phone)
        self._store().record_sms_send(phone_e164, client_ip, "admin_rebind", "student")
        self._store().record_admin_audit(
            admin_username=admin_username,
            action="student.phone_rebind_code_sent",
            target_role="student",
            target_account_id=student_id.lower(),
            reason="学生手机号补绑验证",
            metadata={"new_phone_masked": mask_phone(phone_e164)},
            client_ip=client_ip,
        )
        return {"sent": True, "retry_after": 60}

    def rebind_student_phone(
        self,
        student_id: str,
        body: AdminStudentPhoneRebindInput,
        *,
        admin_username: str,
        client_ip: str,
    ) -> dict[str, Any]:
        if self.phone_auth is None:
            raise InputValidationError("手机号认证服务尚未启用")
        student = self._store().student_by_account(student_id)
        if not student:
            raise InputValidationError("学生账号不存在")
        phone, phone_e164 = normalize_phone(body.phone)
        if student.get("phone_e164") == phone_e164:
            raise InputValidationError("新手机号与当前绑定手机号相同")
        self._store().guard_sms_verify(phone_e164, "admin_rebind", "student")
        if not self.phone_auth.check_code(phone, body.verification_code):
            self._store().record_sms_failure(phone_e164, "admin_rebind", "student")
            raise InputValidationError("手机号验证码不正确或已过期")
        self._store().consume_sms_challenge(phone_e164, "admin_rebind", "student")
        updated = self._store().admin_rebind_student_phone(
            student_id=student_id.lower(),
            phone_e164=phone_e164,
            admin_username=admin_username,
            reason=body.reason,
            client_ip=client_ip,
        )
        if not updated:
            raise InputValidationError("学生账号不存在")
        updated["phone_masked"] = mask_phone(updated.pop("phone_e164", None))
        updated["is_active"] = bool(updated["is_active"])
        return updated

    def delete_account(
        self,
        role: Literal["student", "teacher"],
        account_id: str,
        body: AdminAccountDeletionInput,
        *,
        admin_username: str,
        client_ip: str,
    ) -> dict[str, Any]:
        normalized = account_id.strip().lower()
        if body.confirm_account_id != normalized:
            raise InputValidationError("确认账号与待注销账号不一致")
        result = self._store().admin_delete_account(
            role=role,
            account_id=normalized,
            admin_username=admin_username,
            reason=body.reason,
            client_ip=client_ip,
        )
        if not result:
            raise InputValidationError("账号不存在或已经注销")
        return result

    def list_audits(self, *, limit: int, offset: int) -> dict[str, Any]:
        rows = self._store().list_admin_audits(limit=limit + 1, offset=offset)
        return {
            "audits": rows[:limit],
            "has_more": len(rows) > limit,
            "limit": limit,
            "offset": offset,
        }
