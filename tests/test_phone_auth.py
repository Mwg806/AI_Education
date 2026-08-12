from unittest import TestCase

from ai_education.auth import StudentLoginInput, TeacherLoginInput
from ai_education.core.errors import InputValidationError
from ai_education.phone_verification import normalize_phone


class PhoneAuthTest(TestCase):
    def test_normalizes_mainland_mobile_number(self) -> None:
        self.assertEqual(normalize_phone("138 0013 8000"), ("13800138000", "+8613800138000"))
        self.assertEqual(normalize_phone("+8613800138000"), ("13800138000", "+8613800138000"))

    def test_rejects_invalid_mobile_number(self) -> None:
        with self.assertRaises(InputValidationError):
            normalize_phone("123456")

    def test_student_login_has_no_password_field(self) -> None:
        body = StudentLoginInput(
            student_id="student_01",
            phone="13800138000",
            verification_code="123456",
        )
        self.assertNotIn("password", body.model_dump())

    def test_teacher_login_has_no_password_field(self) -> None:
        body = TeacherLoginInput(
            teacher_id="teacher_01",
            phone="13800138000",
            verification_code="123456",
        )
        self.assertNotIn("password", body.model_dump())
