from __future__ import annotations

from typing import Any
from unittest import TestCase

from pydantic import ValidationError

from ai_education.admin import (
    AdminAccountDeletionInput,
    AdminService,
    AdminStudentPhoneRebindInput,
    hash_admin_password,
    mask_phone,
    verify_admin_password,
)
from ai_education.core.errors import InputValidationError


class FakeAdminStore:
    def __init__(self) -> None:
        self.deleted: dict[str, Any] | None = None
        self.rebound: dict[str, Any] | None = None
        self.failures = 0
        self.consumed = 0

    def student_by_account(self, student_id: str) -> dict[str, Any] | None:
        if student_id.lower() != "student_01":
            return None
        return {
            "id": 1,
            "student_id": "student_01",
            "phone_e164": None,
            "is_active": 1,
        }

    def guard_sms_verify(self, phone_e164: str, purpose: str, role: str) -> None:
        if (purpose, role) != ("admin_rebind", "student"):
            raise AssertionError("补绑挑战必须与学生管理员补绑用途隔离")

    def record_sms_failure(self, phone_e164: str, purpose: str, role: str) -> None:
        self.failures += 1

    def consume_sms_challenge(self, phone_e164: str, purpose: str, role: str) -> None:
        self.consumed += 1

    def admin_rebind_student_phone(self, **payload: Any) -> dict[str, Any]:
        self.rebound = payload
        return {
            "account_id": payload["student_id"],
            "display_name": "测试学生",
            "phone_e164": payload["phone_e164"],
            "is_active": 1,
        }

    def admin_delete_account(self, **payload: Any) -> dict[str, Any]:
        self.deleted = payload
        return {
            "deleted": True,
            "role": payload["role"],
            "account_id": payload["account_id"],
            "related_records": 12,
        }


class FakePhoneProvider:
    def __init__(self, passes: bool = True) -> None:
        self.passes = passes

    def check_code(self, phone: str, code: str) -> bool:
        return self.passes


class AdminSecurityTests(TestCase):
    def test_password_hash_uses_random_salt_and_verifies(self) -> None:
        first = hash_admin_password("LongAdminPassword!2026")
        second = hash_admin_password("LongAdminPassword!2026")

        self.assertNotEqual(first, second)
        self.assertTrue(verify_admin_password("LongAdminPassword!2026", first))
        self.assertFalse(verify_admin_password("wrong-password", first))
        self.assertFalse(verify_admin_password("LongAdminPassword!2026", "invalid"))

    def test_phone_is_masked_and_never_returned_in_full(self) -> None:
        self.assertEqual(mask_phone("+8613800138000"), "138****8000")
        self.assertEqual(mask_phone(None), "未绑定")

    def test_deletion_requires_literal_acknowledgement(self) -> None:
        with self.assertRaises(ValidationError):
            AdminAccountDeletionInput(
                confirm_account_id="student_01",
                reason="学生离校申请注销",
                acknowledge_permanent_deletion=False,
            )

    def test_whitespace_only_operation_reason_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AdminAccountDeletionInput(
                confirm_account_id="student_01",
                reason="     ",
                acknowledge_permanent_deletion=True,
            )

    def test_deletion_rejects_mismatched_confirmation(self) -> None:
        store = FakeAdminStore()
        service = AdminService(
            store,  # type: ignore[arg-type]
            FakePhoneProvider(),
            username="root",
            password_hash="hash",
        )
        body = AdminAccountDeletionInput(
            confirm_account_id="student_02",
            reason="学生离校申请注销",
            acknowledge_permanent_deletion=True,
        )

        with self.assertRaisesRegex(InputValidationError, "确认账号"):
            service.delete_account(
                "student",
                "student_01",
                body,
                admin_username="root",
                client_ip="192.0.2.1",
            )
        self.assertIsNone(store.deleted)

    def test_student_rebind_consumes_challenge_and_masks_result(self) -> None:
        store = FakeAdminStore()
        service = AdminService(
            store,  # type: ignore[arg-type]
            FakePhoneProvider(),
            username="root",
            password_hash="hash",
        )
        body = AdminStudentPhoneRebindInput(
            phone="13800138000",
            verification_code="123456",
            reason="已通过学校名册核验身份",
        )

        result = service.rebind_student_phone(
            "student_01",
            body,
            admin_username="root",
            client_ip="192.0.2.1",
        )

        self.assertEqual(result["phone_masked"], "138****8000")
        self.assertNotIn("phone_e164", result)
        self.assertEqual(store.consumed, 1)
        self.assertEqual(store.rebound["phone_e164"], "+8613800138000")  # type: ignore[index]

    def test_failed_rebind_records_attempt_without_consuming(self) -> None:
        store = FakeAdminStore()
        service = AdminService(
            store,  # type: ignore[arg-type]
            FakePhoneProvider(passes=False),
            username="root",
            password_hash="hash",
        )
        body = AdminStudentPhoneRebindInput(
            phone="13800138000",
            verification_code="000000",
            reason="已通过学校名册核验身份",
        )

        with self.assertRaisesRegex(InputValidationError, "不正确或已过期"):
            service.rebind_student_phone(
                "student_01",
                body,
                admin_username="root",
                client_ip="192.0.2.1",
            )
        self.assertEqual(store.failures, 1)
        self.assertEqual(store.consumed, 0)
        self.assertIsNone(store.rebound)
