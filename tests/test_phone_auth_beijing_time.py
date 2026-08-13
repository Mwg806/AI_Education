from contextlib import contextmanager
from unittest import TestCase

from ai_education.core.errors import InputValidationError
from ai_education.mysql_persistence import BEIJING_NOW_SQL, MySQLPersistence


class FakeCursor:
    def __init__(self, responses: list[dict[str, int] | None] | None = None) -> None:
        self.responses = list(responses or [])
        self.queries: list[str] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execute(self, query: str, params: tuple[str, ...]) -> None:
        self.queries.append(" ".join(query.split()))

    def fetchone(self) -> dict[str, int] | None:
        return self.responses.pop(0) if self.responses else None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def persistence_with(cursor: FakeCursor, resend_seconds: int = 60) -> MySQLPersistence:
    persistence = object.__new__(MySQLPersistence)
    persistence.phone_auth_resend_seconds = resend_seconds

    @contextmanager
    def connection():
        yield FakeConnection(cursor)

    persistence.connection = connection  # type: ignore[method-assign]
    return persistence


class PhoneAuthBeijingTimeTest(TestCase):
    def test_send_guard_uses_beijing_time_for_both_hourly_windows(self) -> None:
        cursor = FakeCursor([{"elapsed": 60, "hourly": 0}, {"hourly": 0}])
        persistence = persistence_with(cursor)

        persistence.guard_sms_send("+8613800138000", "127.0.0.1", "login", "student")

        self.assertEqual(len(cursor.queries), 2)
        self.assertIn(BEIJING_NOW_SQL, cursor.queries[0])
        self.assertIn(BEIJING_NOW_SQL, cursor.queries[1])

    def test_send_guard_reports_the_actual_remaining_cooldown(self) -> None:
        cursor = FakeCursor([{"elapsed": 45, "hourly": 1}])
        persistence = persistence_with(cursor)

        with self.assertRaisesRegex(InputValidationError, "15 秒后再试"):
            persistence.guard_sms_send(
                "+8613800138000", "127.0.0.1", "login", "student"
            )

    def test_send_time_is_written_explicitly_as_beijing_time(self) -> None:
        cursor = FakeCursor()
        persistence = persistence_with(cursor)

        persistence.record_sms_send(
            "+8613800138000", "127.0.0.1", "register", "teacher"
        )

        self.assertIn("role, sent_at", cursor.queries[0])
        self.assertIn(BEIJING_NOW_SQL, cursor.queries[0])

    def test_verification_window_uses_beijing_time(self) -> None:
        cursor = FakeCursor([{"attempts": 0}])
        persistence = persistence_with(cursor)

        persistence.guard_sms_verify("+8613800138000", "login", "student")

        self.assertIn(BEIJING_NOW_SQL, cursor.queries[0])
        self.assertIn("INTERVAL 15 MINUTE", cursor.queries[0])

    def test_consumed_time_is_written_as_beijing_time(self) -> None:
        cursor = FakeCursor()
        persistence = persistence_with(cursor)

        persistence.consume_sms_challenge("+8613800138000", "login", "student")

        self.assertIn(f"consumed_at={BEIJING_NOW_SQL}", cursor.queries[0])
