"""MySQL 5.7 persistence for accounts and durable student learning records."""

# SQL column lists remain on one line so migrations can be compared with SHOW CREATE TABLE.
# ruff: noqa: E501

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from ai_education.config import Settings

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS students (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        student_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_name VARCHAR(64) NOT NULL,
        grade VARCHAR(24) CHARACTER SET ascii NOT NULL,
        province_code VARCHAR(12) CHARACTER SET ascii NOT NULL,
        target_exam_year SMALLINT UNSIGNED NOT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uk_students_student_id (student_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (token_hash),
        KEY idx_auth_sessions_student (student_pk),
        KEY idx_auth_sessions_expiry (expires_at),
        CONSTRAINT fk_auth_sessions_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS teachers (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        teacher_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        teacher_name VARCHAR(64) NOT NULL,
        school_name VARCHAR(128) NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uk_teachers_teacher_id (teacher_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS teacher_auth_sessions (
        token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (token_hash),
        KEY idx_teacher_sessions_teacher (teacher_pk),
        KEY idx_teacher_sessions_expiry (expires_at),
        CONSTRAINT fk_teacher_sessions_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classrooms (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        class_code CHAR(8) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        class_name VARCHAR(96) NOT NULL,
        grade VARCHAR(24) CHARACTER SET ascii NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uk_classrooms_code (class_code),
        KEY idx_classrooms_teacher (teacher_pk, status, updated_at),
        CONSTRAINT fk_classrooms_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classroom_members (
        classroom_pk BIGINT UNSIGNED NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
        joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (classroom_pk, student_pk),
        KEY idx_classroom_members_student (student_pk, status, joined_at),
        CONSTRAINT fk_classroom_members_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_classroom_members_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classroom_announcements (
        announcement_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        announcement_type VARCHAR(32) CHARACTER SET ascii NOT NULL,
        title VARCHAR(160) NOT NULL,
        content TEXT NOT NULL,
        due_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (announcement_id),
        KEY idx_announcements_classroom (classroom_pk, created_at),
        CONSTRAINT fk_announcements_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_announcements_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classroom_exam_assignments (
        assignment_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        paper_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        title VARCHAR(160) NOT NULL,
        due_at DATETIME NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'published',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (assignment_id),
        KEY idx_exam_assignments_classroom (classroom_pk, status, created_at),
        CONSTRAINT fk_exam_assignments_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_exam_assignments_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS student_state_records (
        student_pk BIGINT UNSIGNED NOT NULL,
        state_type VARCHAR(48) CHARACTER SET ascii NOT NULL,
        external_id VARCHAR(128) CHARACTER SET ascii NULL,
        state_version INT UNSIGNED NOT NULL DEFAULT 1,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk, state_type),
        KEY idx_student_state_external (state_type, external_id),
        CONSTRAINT fk_student_state_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_plans (
        plan_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        version INT UNSIGNED NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (plan_id, version),
        KEY idx_learning_plans_student (student_pk, status, updated_at),
        CONSTRAINT fk_learning_plans_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS homework_sessions (
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        active_question_id VARCHAR(96) CHARACTER SET ascii NULL,
        state_version INT UNSIGNED NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (session_id),
        KEY idx_homework_student (student_pk, updated_at),
        KEY idx_homework_question (active_question_id),
        CONSTRAINT fk_homework_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS homework_turns (
        turn_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        user_intent VARCHAR(80) CHARACTER SET ascii NOT NULL,
        assistant_action VARCHAR(80) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (turn_id),
        KEY idx_homework_turn_session (session_id, created_at),
        CONSTRAINT fk_homework_turn_session FOREIGN KEY (session_id)
            REFERENCES homework_sessions(session_id) ON DELETE CASCADE,
        CONSTRAINT fk_homework_turn_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS homework_variant_sessions (
        variant_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        PRIMARY KEY (variant_id),
        KEY idx_homework_variant_session (session_id),
        CONSTRAINT fk_homework_variant_session FOREIGN KEY (session_id)
            REFERENCES homework_sessions(session_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS answer_vault_records (
        vault_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        question_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        variant_id VARCHAR(96) CHARACTER SET ascii NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (vault_id),
        KEY idx_answer_vault_student (student_pk, created_at),
        CONSTRAINT fk_answer_vault_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_evidence_records (
        evidence_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NOT NULL,
        assessment_id VARCHAR(128) NOT NULL,
        question_id VARCHAR(128) NOT NULL,
        source_id VARCHAR(256) NULL,
        score DECIMAL(10,3) NOT NULL,
        max_score DECIMAL(10,3) NOT NULL,
        duration_seconds INT UNSIGNED NULL,
        knowledge_tags JSON NOT NULL,
        payload_json JSON NOT NULL,
        occurred_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (evidence_id),
        KEY idx_evidence_student_subject (student_pk, subject, occurred_at),
        KEY idx_evidence_assessment (student_pk, assessment_id, question_id),
        CONSTRAINT fk_evidence_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_diagnosis_reports (
        diagnosis_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NOT NULL,
        state_version INT UNSIGNED NOT NULL,
        diagnosis_status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (diagnosis_id),
        UNIQUE KEY uk_diagnosis_student_version (student_pk, subject, state_version),
        KEY idx_diagnosis_latest (student_pk, subject, created_at),
        CONSTRAINT fk_diagnosis_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS teacher_reviews (
        review_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        diagnosis_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        reviewer_id VARCHAR(128) NOT NULL,
        decision VARCHAR(40) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (review_id),
        KEY idx_review_diagnosis (diagnosis_id, created_at),
        CONSTRAINT fk_review_diagnosis FOREIGN KEY (diagnosis_id)
            REFERENCES learning_diagnosis_reports(diagnosis_id) ON DELETE CASCADE,
        CONSTRAINT fk_review_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_diagnostic_sessions (
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        paper_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NOT NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        score DECIMAL(10,3) NULL,
        paper_max DECIMAL(10,3) NULL,
        payload_json JSON NOT NULL,
        result_json JSON NULL,
        started_at DATETIME NOT NULL,
        completed_at DATETIME NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (session_id),
        KEY idx_exam_student (student_pk, started_at),
        KEY idx_exam_paper (paper_id, status),
        CONSTRAINT fk_exam_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_question_records (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        question_id VARCHAR(160) CHARACTER SET ascii NOT NULL,
        question_type VARCHAR(40) CHARACTER SET ascii NOT NULL,
        selected_option CHAR(1) CHARACTER SET ascii NULL,
        duration_seconds INT UNSIGNED NOT NULL,
        score DECIMAL(10,3) NULL,
        max_score DECIMAL(10,3) NOT NULL,
        is_correct TINYINT(1) NULL,
        knowledge_tags JSON NOT NULL,
        response_json JSON NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uk_exam_question (session_id, question_id),
        KEY idx_exam_question_session (session_id),
        CONSTRAINT fk_exam_question_session FOREIGN KEY (session_id)
            REFERENCES exam_diagnostic_sessions(session_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _decoded(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _mysql_datetime(value: Any) -> Any:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


class MySQLPersistence:
    """Small DB-API adapter; each operation owns a short-lived connection."""

    def __init__(self, settings: Settings) -> None:
        if not IDENTIFIER.fullmatch(settings.mysql_database):
            raise ValueError("AI_EDUCATION_MYSQL_DATABASE 不是安全的数据库标识符")
        self.host = settings.mysql_host
        self.port = settings.mysql_port
        self.user = settings.mysql_user
        self.password = settings.mysql_password
        self.database = settings.mysql_database
        self.timeout = settings.mysql_connect_timeout_seconds

    def _connect(self, *, include_database: bool = True) -> Connection:
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "charset": "utf8mb4",
            "connect_timeout": self.timeout,
            "read_timeout": 15,
            "write_timeout": 15,
            "cursorclass": DictCursor,
            "autocommit": False,
        }
        if include_database:
            kwargs["database"] = self.database
        return pymysql.connect(**kwargs)

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        connection = self._connect(include_database=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.commit()
        finally:
            connection.close()
        with self.connection() as connection, connection.cursor() as cursor:
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)

    def health(self) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            return bool(cursor.fetchone()["ok"])

    @staticmethod
    def _student_pk(cursor: DictCursor, student_id: str) -> int | None:
        cursor.execute(
            "SELECT id FROM students WHERE student_id=%s AND is_active=1",
            (student_id.lower(),),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None

    def create_student(self, profile: dict[str, Any], password_hash: str) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO students
                    (student_id, password_hash, student_name, grade, province_code, target_exam_year)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    profile["student_id"].lower(),
                    password_hash,
                    profile["student_name"],
                    profile["grade"],
                    profile["province_code"],
                    profile["target_exam_year"],
                ),
            )
        return self.student_by_account(profile["student_id"]) or {}

    def student_by_account(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, student_id, password_hash, student_name, grade, province_code,
                       target_exam_year, is_active, created_at, updated_at
                FROM students WHERE student_id=%s
                """,
                (student_id.lower(),),
            )
            return cursor.fetchone()

    def create_auth_session(self, token_hash: str, student_pk: int, expires_at: datetime) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO auth_sessions (token_hash, student_pk, expires_at) VALUES (%s,%s,%s)",
                (token_hash, student_pk, _mysql_datetime(expires_at)),
            )

    def resolve_auth_session(self, token_hash: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.student_id, s.student_name, s.grade, s.province_code,
                       s.target_exam_year, a.expires_at
                FROM auth_sessions a JOIN students s ON s.id=a.student_pk
                WHERE a.token_hash=%s AND a.expires_at>UTC_TIMESTAMP() AND s.is_active=1
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE auth_sessions SET last_seen_at=UTC_TIMESTAMP() WHERE token_hash=%s",
                    (token_hash,),
                )
            return row

    def delete_auth_session(self, token_hash: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM auth_sessions WHERE token_hash=%s", (token_hash,))

    def create_teacher(self, profile: dict[str, Any], password_hash: str) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO teachers
                    (teacher_id, password_hash, teacher_name, school_name, subject)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    profile["teacher_id"].lower(),
                    password_hash,
                    profile["teacher_name"],
                    profile["school_name"],
                    profile.get("subject"),
                ),
            )
        return self.teacher_by_account(profile["teacher_id"]) or {}

    def teacher_by_account(self, teacher_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, teacher_id, password_hash, teacher_name, school_name, subject,
                       is_active, created_at, updated_at
                FROM teachers WHERE teacher_id=%s
                """,
                (teacher_id.lower(),),
            )
            return cursor.fetchone()

    def create_teacher_auth_session(
        self, token_hash: str, teacher_pk: int, expires_at: datetime
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO teacher_auth_sessions (token_hash, teacher_pk, expires_at)
                VALUES (%s,%s,%s)
                """,
                (token_hash, teacher_pk, _mysql_datetime(expires_at)),
            )

    def resolve_teacher_auth_session(self, token_hash: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.teacher_id, t.teacher_name, t.school_name, t.subject,
                       a.expires_at
                FROM teacher_auth_sessions a JOIN teachers t ON t.id=a.teacher_pk
                WHERE a.token_hash=%s AND a.expires_at>UTC_TIMESTAMP() AND t.is_active=1
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    """
                    UPDATE teacher_auth_sessions SET last_seen_at=UTC_TIMESTAMP()
                    WHERE token_hash=%s
                    """,
                    (token_hash,),
                )
            return row

    def delete_teacher_auth_session(self, token_hash: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM teacher_auth_sessions WHERE token_hash=%s", (token_hash,)
            )

    def save_state(
        self,
        student_id: str,
        state_type: str,
        external_id: str,
        version: int,
        payload: dict[str, Any],
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO student_state_records
                    (student_pk, state_type, external_id, state_version, payload_json)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE external_id=VALUES(external_id),
                    state_version=VALUES(state_version), payload_json=VALUES(payload_json)
                """,
                (student_pk, state_type, external_id, version, _json(payload)),
            )

    def load_state(self, student_id: str, state_type: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.payload_json FROM student_state_records r
                JOIN students s ON s.id=r.student_pk
                WHERE s.student_id=%s AND r.state_type=%s
                """,
                (student_id.lower(), state_type),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_plan(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO learning_plans (plan_id, version, student_pk, status, payload_json)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), payload_json=VALUES(payload_json)
                """,
                (
                    payload["plan_id"],
                    payload["version"],
                    student_pk,
                    payload["status"],
                    _json(payload),
                ),
            )

    def load_plan(self, plan_id: str, version: int | None = None) -> dict[str, Any] | None:
        clause = "AND p.version=%s" if version is not None else "ORDER BY p.version DESC LIMIT 1"
        params: tuple[Any, ...] = (plan_id, version) if version is not None else (plan_id,)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT p.payload_json FROM learning_plans p WHERE p.plan_id=%s {clause}", params
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def load_active_plan(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM learning_plans p
                JOIN students s ON s.id=p.student_pk
                JOIN (SELECT plan_id, MAX(version) version FROM learning_plans GROUP BY plan_id) latest
                  ON latest.plan_id=p.plan_id AND latest.version=p.version
                WHERE s.student_id=%s AND p.status IN ('active','waiting_for_confirmation')
                ORDER BY p.updated_at DESC LIMIT 1
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def load_latest_plan(self, student_id: str) -> dict[str, Any] | None:
        """Load the most recently updated plan that a student can continue viewing."""
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM learning_plans p
                JOIN students s ON s.id=p.student_pk
                JOIN (SELECT plan_id, MAX(version) version FROM learning_plans GROUP BY plan_id) latest
                  ON latest.plan_id=p.plan_id AND latest.version=p.version
                WHERE s.student_id=%s
                  AND p.status IN ('active','waiting_for_confirmation','provisional','paused')
                ORDER BY p.updated_at DESC, p.created_at DESC LIMIT 1
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_homework_session(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                return
            active_question = payload.get("active_question") or {}
            cursor.execute(
                """
                INSERT INTO homework_sessions
                    (session_id, student_pk, subject, status, active_question_id, state_version,
                     payload_json, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE subject=VALUES(subject), status=VALUES(status),
                    active_question_id=VALUES(active_question_id), state_version=VALUES(state_version),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    payload["session_id"],
                    student_pk,
                    payload.get("subject_hint"),
                    payload["status"],
                    active_question.get("question_id"),
                    payload["state_version"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["updated_at"]),
                ),
            )
            for turn in payload.get("turns", []):
                cursor.execute(
                    """
                    INSERT IGNORE INTO homework_turns
                        (turn_id, session_id, student_pk, user_intent, assistant_action,
                         payload_json, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        turn["turn_id"],
                        payload["session_id"],
                        student_pk,
                        turn["user_intent"],
                        turn["assistant_action"],
                        _json(turn),
                        _mysql_datetime(turn["created_at"]),
                    ),
                )

    def load_homework_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload_json FROM homework_sessions WHERE session_id=%s", (session_id,)
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def load_homework_by_question(self, question_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload_json FROM homework_sessions WHERE active_question_id=%s ORDER BY updated_at DESC LIMIT 1",
                (question_id,),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_homework_variant(self, variant_id: str, session_id: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO homework_variant_sessions (variant_id, session_id) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE session_id=VALUES(session_id)",
                (variant_id, session_id),
            )

    def load_homework_by_variant(self, variant_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT h.payload_json FROM homework_variant_sessions v
                JOIN homework_sessions h ON h.session_id=v.session_id WHERE v.variant_id=%s
                """,
                (variant_id,),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_answer_vault(self, student_id: str, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO answer_vault_records
                    (vault_id, student_pk, question_id, variant_id, payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json)
                """,
                (
                    payload["vault_id"],
                    student_pk,
                    payload["question_id"],
                    payload.get("variant_id"),
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def load_answer_vault(self, vault_id: str, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.payload_json FROM answer_vault_records v
                JOIN students s ON s.id=v.student_pk
                WHERE v.vault_id=%s AND s.student_id=%s
                """,
                (vault_id, student_id.lower()),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_learning_evidence(self, student_id: str, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return
            for payload in payloads:
                cursor.execute(
                    """
                    INSERT INTO learning_evidence_records
                        (evidence_id, student_pk, subject, assessment_id, question_id, source_id,
                         score, max_score, duration_seconds, knowledge_tags, payload_json, occurred_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json),
                        score=VALUES(score), max_score=VALUES(max_score),
                        duration_seconds=VALUES(duration_seconds), knowledge_tags=VALUES(knowledge_tags)
                    """,
                    (
                        payload["evidence_id"],
                        student_pk,
                        payload["subject"],
                        payload["assessment_id"],
                        payload["question_id"],
                        payload.get("source_id"),
                        payload["score"],
                        payload["max_score"],
                        payload.get("duration_seconds"),
                        _json(payload["knowledge_tags"]),
                        _json(payload),
                        _mysql_datetime(payload["occurred_at"]),
                    ),
                )

    def load_learning_evidence(self, student_id: str, subject: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.payload_json FROM learning_evidence_records e
                JOIN students s ON s.id=e.student_pk
                WHERE s.student_id=%s AND e.subject=%s ORDER BY e.occurred_at
                """,
                (student_id.lower(), subject),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_diagnosis(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO learning_diagnosis_reports
                    (diagnosis_id, student_pk, subject, state_version, diagnosis_status,
                     payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE diagnosis_status=VALUES(diagnosis_status),
                    payload_json=VALUES(payload_json)
                """,
                (
                    payload["diagnosis_id"],
                    student_pk,
                    payload["subject"],
                    payload["state_version"],
                    payload["diagnosis_status"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def load_diagnosis(self, diagnosis_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload_json FROM learning_diagnosis_reports WHERE diagnosis_id=%s",
                (diagnosis_id,),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def load_latest_diagnosis(self, student_id: str, subject: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.payload_json FROM learning_diagnosis_reports d
                JOIN students s ON s.id=d.student_pk
                WHERE s.student_id=%s AND d.subject=%s
                ORDER BY d.state_version DESC LIMIT 1
                """,
                (student_id.lower(), subject),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_teacher_review(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO teacher_reviews
                    (review_id, diagnosis_id, student_pk, reviewer_id, decision, payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json)
                """,
                (
                    payload["review_id"],
                    payload["diagnosis_id"],
                    student_pk,
                    payload["reviewer_id"],
                    payload["decision"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def save_exam_session(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                return
            result = payload.get("result")
            completed_at = result.get("completed_at") if result else None
            cursor.execute(
                """
                INSERT INTO exam_diagnostic_sessions
                    (session_id, student_pk, paper_id, subject, status, score, paper_max,
                     payload_json, result_json, started_at, completed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), score=VALUES(score),
                    paper_max=VALUES(paper_max), payload_json=VALUES(payload_json),
                    result_json=VALUES(result_json), completed_at=VALUES(completed_at)
                """,
                (
                    payload["session_id"],
                    student_pk,
                    payload["paper_id"],
                    payload["subject"],
                    payload["status"],
                    result.get("score") if result else None,
                    result.get("paper_max") if result else None,
                    _json(payload),
                    _json(result) if result else None,
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(completed_at) if completed_at else None,
                ),
            )
            if result:
                objective = {
                    item["question_id"]: item for item in result.get("objective_results", [])
                }
                constructed = {
                    item["question_id"]: item for item in result.get("constructed_results", [])
                }
                selected = payload.get("objective_answers", {})
                for record in result.get("learning_record", {}).get("question_records", []):
                    question_id = record["question_id"]
                    response = objective.get(question_id) or constructed.get(question_id) or {}
                    cursor.execute(
                        """
                        INSERT INTO exam_question_records
                            (session_id, question_id, question_type, selected_option, duration_seconds,
                             score, max_score, is_correct, knowledge_tags, response_json)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE selected_option=VALUES(selected_option),
                            duration_seconds=VALUES(duration_seconds), score=VALUES(score),
                            max_score=VALUES(max_score), is_correct=VALUES(is_correct),
                            knowledge_tags=VALUES(knowledge_tags), response_json=VALUES(response_json)
                        """,
                        (
                            payload["session_id"],
                            question_id,
                            record["question_type"],
                            (selected.get(question_id) or {}).get("selected_option"),
                            record["duration_seconds"],
                            record.get("score"),
                            record["max_score"],
                            record.get("is_correct"),
                            _json(record["knowledge_tags"]),
                            _json(response),
                        ),
                    )

    def load_exam_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload_json FROM exam_diagnostic_sessions WHERE session_id=%s",
                (session_id,),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    @staticmethod
    def _teacher_pk(cursor: DictCursor, teacher_id: str) -> int | None:
        cursor.execute(
            "SELECT id FROM teachers WHERE teacher_id=%s AND is_active=1",
            (teacher_id.lower(),),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None

    def create_classroom(self, teacher_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            if teacher_pk is None:
                raise ValueError("教师账号不存在")
            cursor.execute(
                """
                INSERT INTO classrooms (class_code, teacher_pk, class_name, grade, subject)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    payload["class_code"], teacher_pk, payload["class_name"],
                    payload["grade"], payload.get("subject"),
                ),
            )
            classroom_id = int(cursor.lastrowid)
        return self.teacher_classroom(teacher_id, classroom_id) or {}

    def teacher_classroom(self, teacher_id: str, classroom_id: int) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.status,
                       c.created_at, c.updated_at,
                       COUNT(CASE WHEN m.status='active' THEN 1 END) AS student_count
                FROM classrooms c JOIN teachers t ON t.id=c.teacher_pk
                LEFT JOIN classroom_members m ON m.classroom_pk=c.id
                WHERE c.id=%s AND t.teacher_id=%s
                GROUP BY c.id
                """,
                (classroom_id, teacher_id.lower()),
            )
            return cursor.fetchone()

    def list_teacher_classrooms(self, teacher_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.status,
                       c.created_at, c.updated_at,
                       COUNT(CASE WHEN m.status='active' THEN 1 END) AS student_count
                FROM classrooms c JOIN teachers t ON t.id=c.teacher_pk
                LEFT JOIN classroom_members m ON m.classroom_pk=c.id
                WHERE t.teacher_id=%s AND c.status='active'
                GROUP BY c.id ORDER BY c.updated_at DESC
                """,
                (teacher_id.lower(),),
            )
            return list(cursor.fetchall())

    def join_classroom(self, student_id: str, class_code: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            cursor.execute(
                """
                SELECT c.id FROM classrooms c
                WHERE c.class_code=%s AND c.status='active'
                """,
                (class_code.upper(),),
            )
            classroom = cursor.fetchone()
            if student_pk is None or not classroom:
                return None
            cursor.execute(
                """
                INSERT INTO classroom_members (classroom_pk, student_pk, status)
                VALUES (%s,%s,'active')
                ON DUPLICATE KEY UPDATE status='active', updated_at=UTC_TIMESTAMP()
                """,
                (classroom["id"], student_pk),
            )
        return self.student_classroom(student_id, int(classroom["id"]))

    def student_classroom(self, student_id: str, classroom_id: int) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.status,
                       t.teacher_name, t.school_name, m.joined_at
                FROM classroom_members m
                JOIN classrooms c ON c.id=m.classroom_pk
                JOIN teachers t ON t.id=c.teacher_pk
                JOIN students s ON s.id=m.student_pk
                WHERE s.student_id=%s AND c.id=%s AND m.status='active'
                """,
                (student_id.lower(), classroom_id),
            )
            return cursor.fetchone()

    def list_student_classrooms(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.status,
                       t.teacher_name, t.school_name, m.joined_at
                FROM classroom_members m
                JOIN classrooms c ON c.id=m.classroom_pk
                JOIN teachers t ON t.id=c.teacher_pk
                JOIN students s ON s.id=m.student_pk
                WHERE s.student_id=%s AND m.status='active' AND c.status='active'
                ORDER BY m.joined_at DESC
                """,
                (student_id.lower(),),
            )
            return list(cursor.fetchall())

    def create_announcement(
        self, teacher_id: str, classroom_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        classroom = self.teacher_classroom(teacher_id, classroom_id)
        if not classroom:
            return None
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                INSERT INTO classroom_announcements
                    (announcement_id, classroom_pk, teacher_pk, announcement_type,
                     title, content, due_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    payload["announcement_id"], classroom_id, teacher_pk,
                    payload["announcement_type"], payload["title"], payload["content"],
                    _mysql_datetime(payload.get("due_at")) if payload.get("due_at") else None,
                ),
            )
            cursor.execute(
                """
                SELECT announcement_id, classroom_pk AS classroom_id, announcement_type,
                       title, content, due_at, created_at, updated_at
                FROM classroom_announcements WHERE announcement_id=%s
                """,
                (payload["announcement_id"],),
            )
            return cursor.fetchone()

    def list_classroom_announcements(
        self, classroom_ids: list[int]
    ) -> list[dict[str, Any]]:
        if not classroom_ids:
            return []
        placeholders = ",".join(["%s"] * len(classroom_ids))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT a.announcement_id, a.classroom_pk AS classroom_id, c.class_name,
                       a.announcement_type, a.title, a.content, a.due_at,
                       a.created_at, a.updated_at
                FROM classroom_announcements a JOIN classrooms c ON c.id=a.classroom_pk
                WHERE a.classroom_pk IN ({placeholders})
                ORDER BY a.created_at DESC LIMIT 200
                """,
                tuple(classroom_ids),
            )
            return list(cursor.fetchall())

    def save_exam_assignment(
        self, teacher_id: str, classroom_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        classroom = self.teacher_classroom(teacher_id, classroom_id)
        if not classroom:
            return None
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                INSERT INTO classroom_exam_assignments
                    (assignment_id, classroom_pk, teacher_pk, paper_id, title, due_at, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE paper_id=VALUES(paper_id), title=VALUES(title),
                    due_at=VALUES(due_at), status=VALUES(status), updated_at=UTC_TIMESTAMP()
                """,
                (
                    payload["assignment_id"], classroom_id, teacher_pk, payload["paper_id"],
                    payload["title"],
                    _mysql_datetime(payload.get("due_at")) if payload.get("due_at") else None,
                    payload.get("status", "published"),
                ),
            )
            cursor.execute(
                """
                SELECT assignment_id, classroom_pk AS classroom_id, paper_id, title,
                       due_at, status, created_at, updated_at
                FROM classroom_exam_assignments WHERE assignment_id=%s
                """,
                (payload["assignment_id"],),
            )
            return cursor.fetchone()

    def list_classroom_exam_assignments(
        self, classroom_ids: list[int]
    ) -> list[dict[str, Any]]:
        if not classroom_ids:
            return []
        placeholders = ",".join(["%s"] * len(classroom_ids))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT a.assignment_id, a.classroom_pk AS classroom_id, c.class_name,
                       a.paper_id, a.title, a.due_at, a.status, a.created_at, a.updated_at
                FROM classroom_exam_assignments a JOIN classrooms c ON c.id=a.classroom_pk
                WHERE a.classroom_pk IN ({placeholders}) AND a.status!='archived'
                ORDER BY a.created_at DESC LIMIT 200
                """,
                tuple(classroom_ids),
            )
            return list(cursor.fetchall())

    def classroom_members_for_teacher(
        self, teacher_id: str, classroom_id: int
    ) -> list[dict[str, Any]] | None:
        if not self.teacher_classroom(teacher_id, classroom_id):
            return None
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.student_id, s.student_name, s.grade, s.province_code,
                       s.target_exam_year, m.joined_at
                FROM classroom_members m JOIN students s ON s.id=m.student_pk
                WHERE m.classroom_pk=%s AND m.status='active'
                ORDER BY s.student_name, s.student_id
                """,
                (classroom_id,),
            )
            members = list(cursor.fetchall())
        for member in members:
            student_id = member["student_id"]
            member["latest_plan"] = self.load_latest_plan(student_id)
            with self.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT d.payload_json FROM learning_diagnosis_reports d
                    JOIN students s ON s.id=d.student_pk
                    WHERE s.student_id=%s ORDER BY d.created_at DESC LIMIT 1
                    """,
                    (student_id.lower(),),
                )
                diagnosis = cursor.fetchone()
                member["latest_diagnosis"] = (
                    _decoded(diagnosis["payload_json"]) if diagnosis else None
                )
                cursor.execute(
                    """
                    SELECT e.paper_id, e.subject, e.status, e.score, e.paper_max,
                           e.started_at, e.completed_at
                    FROM exam_diagnostic_sessions e JOIN students s ON s.id=e.student_pk
                    WHERE s.student_id=%s ORDER BY e.updated_at DESC LIMIT 1
                    """,
                    (student_id.lower(),),
                )
                member["latest_exam"] = cursor.fetchone()
        return members
