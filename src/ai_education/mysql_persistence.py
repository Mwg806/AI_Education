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
from ai_education.core.errors import InputValidationError

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

# Verification challenge timestamps are stored as naive MySQL DATETIME values.
# Derive Beijing time explicitly from UTC so their meaning does not depend on
# the MySQL server, host, or connection session time zone.
BEIJING_NOW_SQL = "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 8 HOUR)"


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS students (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        student_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL,
        phone_e164 VARCHAR(16) CHARACTER SET ascii NULL,
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
        password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL,
        phone_e164 VARCHAR(16) CHARACTER SET ascii NULL,
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
    CREATE TABLE IF NOT EXISTS phone_verification_challenges (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        phone_e164 VARCHAR(16) CHARACTER SET ascii NOT NULL,
        client_ip VARCHAR(45) CHARACTER SET ascii NOT NULL,
        purpose VARCHAR(16) CHARACTER SET ascii NOT NULL,
        role VARCHAR(16) CHARACTER SET ascii NOT NULL,
        attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
        sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        consumed_at DATETIME NULL,
        PRIMARY KEY (id),
        KEY idx_phone_challenge_phone (phone_e164, role, purpose, sent_at),
        KEY idx_phone_challenge_ip (client_ip, sent_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_sessions (
        token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        admin_username VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        expires_at DATETIME NOT NULL,
        client_ip VARCHAR(45) CHARACTER SET ascii NOT NULL,
        user_agent VARCHAR(255) NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (token_hash),
        KEY idx_admin_sessions_expiry (expires_at),
        KEY idx_admin_sessions_username (admin_username, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        admin_username VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
        action VARCHAR(80) CHARACTER SET ascii NOT NULL,
        target_role VARCHAR(16) CHARACTER SET ascii NULL,
        target_account_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NULL,
        reason VARCHAR(500) NOT NULL,
        metadata_json JSON NOT NULL,
        client_ip VARCHAR(45) CHARACTER SET ascii NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_admin_audit_time (created_at),
        KEY idx_admin_audit_target (target_role, target_account_id, created_at),
        KEY idx_admin_audit_action (action, created_at)
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
        join_policy VARCHAR(16) CHARACTER SET ascii NOT NULL DEFAULT 'open',
        student_join_policy VARCHAR(16) CHARACTER SET ascii NOT NULL DEFAULT 'open',
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
    CREATE TABLE IF NOT EXISTS classroom_teachers (
        classroom_pk BIGINT UNSIGNED NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        role VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'collaborator',
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
        joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        reviewed_at DATETIME NULL,
        last_action_at DATETIME NULL,
        PRIMARY KEY (classroom_pk, teacher_pk),
        KEY idx_classroom_teachers_teacher (teacher_pk, status, joined_at),
        CONSTRAINT fk_classroom_teachers_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_classroom_teachers_teacher FOREIGN KEY (teacher_pk)
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
    CREATE TABLE IF NOT EXISTS classroom_join_requests (
        request_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'pending',
        requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME NULL,
        reviewer_teacher_pk BIGINT UNSIGNED NULL,
        reviewer_note VARCHAR(500) NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (request_id),
        UNIQUE KEY uk_classroom_join_member (classroom_pk, student_pk),
        KEY idx_classroom_join_status (classroom_pk, status, requested_at),
        KEY idx_student_join_status (student_pk, status, requested_at),
        CONSTRAINT fk_classroom_join_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_classroom_join_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE,
        CONSTRAINT fk_classroom_join_reviewer FOREIGN KEY (reviewer_teacher_pk)
            REFERENCES teachers(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classroom_leave_requests (
        request_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'pending',
        requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME NULL,
        reviewer_note VARCHAR(500) NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (request_id),
        UNIQUE KEY uk_classroom_leave_member (classroom_pk, student_pk),
        KEY idx_classroom_leave_status (classroom_pk, status, requested_at),
        KEY idx_student_leave_status (student_pk, status, requested_at),
        CONSTRAINT fk_classroom_leave_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_classroom_leave_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS classroom_teacher_leave_requests (
        request_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'pending',
        requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME NULL,
        reviewer_note VARCHAR(500) NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (request_id),
        UNIQUE KEY uk_teacher_leave_member (classroom_pk, teacher_pk),
        KEY idx_teacher_leave_status (classroom_pk, status, requested_at),
        CONSTRAINT fk_teacher_leave_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE,
        CONSTRAINT fk_teacher_leave_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
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
    CREATE TABLE IF NOT EXISTS english_text_analyses (
        analysis_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        title VARCHAR(160) NOT NULL,
        difficulty DECIMAL(6,4) NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (analysis_id),
        KEY idx_english_analysis_student (student_pk, created_at),
        CONSTRAINT fk_english_analysis_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_learning_sessions (
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        mode VARCHAR(40) CHARACTER SET ascii NOT NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        title VARCHAR(160) NOT NULL,
        article_text MEDIUMTEXT NOT NULL,
        difficulty DECIMAL(6,4) NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (session_id),
        KEY idx_english_session_student (student_pk, updated_at),
        CONSTRAINT fk_english_session_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_learning_attempts (
        attempt_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        score DECIMAL(6,4) NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (attempt_id),
        KEY idx_english_attempt_session (session_id, created_at),
        CONSTRAINT fk_english_attempt_session FOREIGN KEY (session_id)
            REFERENCES english_learning_sessions(session_id) ON DELETE CASCADE,
        CONSTRAINT fk_english_attempt_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_reading_progress (
        student_pk BIGINT UNSIGNED NOT NULL,
        reading_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL,
        elapsed_seconds INT UNSIGNED NOT NULL DEFAULT 0,
        score DECIMAL(6,4) NULL,
        payload_json JSON NOT NULL,
        started_at DATETIME NOT NULL,
        submitted_at DATETIME NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (student_pk, reading_id),
        UNIQUE KEY uk_english_reading_session (session_id),
        KEY idx_english_reading_status (student_pk, status, updated_at),
        CONSTRAINT fk_english_reading_progress_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_mastery_states (
        student_pk BIGINT UNSIGNED NOT NULL,
        skill_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        mastery_probability DECIMAL(6,4) NOT NULL,
        stability_days DECIMAL(8,2) NOT NULL,
        evidence_count INT UNSIGNED NOT NULL,
        confidence DECIMAL(6,4) NOT NULL,
        next_review_at DATETIME NULL,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk, skill_id),
        KEY idx_english_mastery_review (student_pk, next_review_at),
        CONSTRAINT fk_english_mastery_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_review_items (
        review_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        session_id VARCHAR(96) CHARACTER SET ascii NULL,
        skill_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        due_at DATETIME NOT NULL,
        completed_at DATETIME NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (review_id),
        KEY idx_english_review_due (student_pk, status, due_at),
        CONSTRAINT fk_english_review_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE,
        CONSTRAINT fk_english_review_session FOREIGN KEY (session_id)
            REFERENCES english_learning_sessions(session_id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_learner_profiles (
        student_pk BIGINT UNSIGNED NOT NULL,
        estimated_level VARCHAR(8) CHARACTER SET ascii NOT NULL,
        self_reported_level VARCHAR(8) CHARACTER SET ascii NOT NULL,
        preferred_mode VARCHAR(24) CHARACTER SET ascii NOT NULL,
        evidence_count INT UNSIGNED NOT NULL DEFAULT 0,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk),
        CONSTRAINT fk_english_profile_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_learning_events (
        event_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        task_type VARCHAR(40) CHARACTER SET ascii NOT NULL,
        response_mode VARCHAR(24) CHARACTER SET ascii NOT NULL,
        source_excerpt TEXT NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (event_id),
        KEY idx_english_events_student (student_pk, created_at),
        CONSTRAINT fk_english_event_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_national_exam_attempts (
        attempt_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        section VARCHAR(32) CHARACTER SET ascii NOT NULL,
        score DECIMAL(8,3) NULL,
        max_score DECIMAL(8,3) NULL,
        evidence_count INT UNSIGNED NOT NULL DEFAULT 0,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (attempt_id),
        KEY idx_english_national_attempt_student (student_pk, created_at),
        CONSTRAINT fk_english_national_attempt_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_vocabulary_items (
        student_pk BIGINT UNSIGNED NOT NULL,
        word_key VARCHAR(96) CHARACTER SET ascii NOT NULL,
        word VARCHAR(96) NOT NULL,
        mastery_score DECIMAL(5,2) NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL,
        contexts_seen INT UNSIGNED NOT NULL,
        next_review_at DATETIME NULL,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (student_pk, word_key),
        KEY idx_english_vocab_review (student_pk, status, next_review_at),
        CONSTRAINT fk_english_vocab_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_grammar_items (
        student_pk BIGINT UNSIGNED NOT NULL,
        grammar_key VARCHAR(96) CHARACTER SET ascii NOT NULL,
        error_count INT UNSIGNED NOT NULL,
        mastery_score DECIMAL(5,2) NOT NULL,
        confidence DECIMAL(6,4) NOT NULL,
        next_review_at DATETIME NULL,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (student_pk, grammar_key),
        KEY idx_english_grammar_review (student_pk, next_review_at),
        CONSTRAINT fk_english_grammar_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_writing_submissions (
        submission_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        event_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        revision_level TINYINT UNSIGNED NOT NULL,
        source_text MEDIUMTEXT NOT NULL,
        revised_text MEDIUMTEXT NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (submission_id),
        KEY idx_english_writing_student (student_pk, created_at),
        CONSTRAINT fk_english_writing_event FOREIGN KEY (event_id)
            REFERENCES english_learning_events(event_id) ON DELETE CASCADE,
        CONSTRAINT fk_english_writing_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS english_speaking_sessions (
        speaking_session_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        event_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        scenario VARCHAR(160) NOT NULL,
        feedback_mode VARCHAR(24) CHARACTER SET ascii NOT NULL,
        pronunciation_scored TINYINT(1) NOT NULL DEFAULT 0,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (speaking_session_id),
        KEY idx_english_speaking_student (student_pk, created_at),
        CONSTRAINT fk_english_speaking_event FOREIGN KEY (event_id)
            REFERENCES english_learning_events(event_id) ON DELETE CASCADE,
        CONSTRAINT fk_english_speaking_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS career_job_positions (
        job_id VARCHAR(64) CHARACTER SET ascii NOT NULL,
        name VARCHAR(128) NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (job_id),
        KEY idx_career_jobs_status (status, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS career_project_templates (
        project_id VARCHAR(64) CHARACTER SET ascii NOT NULL,
        target_job_id VARCHAR(64) CHARACTER SET ascii NOT NULL,
        title VARCHAR(160) NOT NULL,
        difficulty TINYINT UNSIGNED NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (project_id),
        KEY idx_career_projects_job (target_job_id, status, difficulty)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS career_coding_questions (
        question_id VARCHAR(64) CHARACTER SET ascii NOT NULL,
        target_job_id VARCHAR(64) CHARACTER SET ascii NOT NULL,
        language VARCHAR(24) CHARACTER SET ascii NOT NULL,
        category VARCHAR(48) CHARACTER SET ascii NOT NULL,
        difficulty TINYINT UNSIGNED NOT NULL,
        source_type VARCHAR(32) CHARACTER SET ascii NOT NULL,
        license_name VARCHAR(64) CHARACTER SET ascii NOT NULL,
        review_status VARCHAR(24) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (question_id),
        KEY idx_career_questions_job (target_job_id, language, difficulty),
        KEY idx_career_questions_category (category, review_status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS programming_learner_profiles (
        student_pk BIGINT UNSIGNED NOT NULL,
        learning_mode VARCHAR(24) CHARACTER SET ascii NOT NULL,
        target_direction VARCHAR(64) CHARACTER SET ascii NOT NULL,
        weekly_minutes SMALLINT UNSIGNED NOT NULL,
        exam_period TINYINT(1) NOT NULL DEFAULT 0,
        profile_version INT UNSIGNED NOT NULL DEFAULT 1,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk),
        CONSTRAINT fk_programming_profile_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS programming_learning_records (
        record_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        record_type VARCHAR(32) CHARACTER SET ascii NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (record_id),
        KEY idx_programming_record_student (student_pk, record_type, updated_at),
        CONSTRAINT fk_programming_record_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS programming_learning_events (
        event_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        event_type VARCHAR(40) CHARACTER SET ascii NOT NULL,
        skill_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        score DECIMAL(6,4) NOT NULL,
        hint_level TINYINT UNSIGNED NOT NULL DEFAULT 0,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (event_id),
        KEY idx_programming_event_student (student_pk, created_at),
        KEY idx_programming_event_skill (student_pk, skill_id, created_at),
        CONSTRAINT fk_programming_event_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS programming_skill_states (
        student_pk BIGINT UNSIGNED NOT NULL,
        skill_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        mastery DECIMAL(6,4) NOT NULL,
        level VARCHAR(8) CHARACTER SET ascii NOT NULL,
        confidence DECIMAL(6,4) NOT NULL,
        evidence_count INT UNSIGNED NOT NULL DEFAULT 0,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (student_pk, skill_id),
        KEY idx_programming_skill_mastery (student_pk, mastery),
        CONSTRAINT fk_programming_skill_student FOREIGN KEY (student_pk)
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
    """
    CREATE TABLE IF NOT EXISTS teacher_lesson_plans (
        lesson_plan_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        classroom_pk BIGINT UNSIGNED NOT NULL,
        subject VARCHAR(32) CHARACTER SET ascii NOT NULL,
        topic VARCHAR(200) NOT NULL,
        lesson_type VARCHAR(40) CHARACTER SET ascii NOT NULL,
        current_version INT UNSIGNED NOT NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (lesson_plan_id),
        KEY idx_teacher_lesson_owner (teacher_pk, status, updated_at),
        KEY idx_teacher_lesson_class (classroom_pk, subject, updated_at),
        CONSTRAINT fk_teacher_lesson_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE,
        CONSTRAINT fk_teacher_lesson_classroom FOREIGN KEY (classroom_pk)
            REFERENCES classrooms(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS teacher_lesson_plan_versions (
        lesson_plan_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        version INT UNSIGNED NOT NULL,
        status VARCHAR(40) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        change_summary_json JSON NOT NULL,
        locked_components_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        approved_at DATETIME NULL,
        published_at DATETIME NULL,
        PRIMARY KEY (lesson_plan_id, version),
        KEY idx_teacher_lesson_version_status (status, created_at),
        CONSTRAINT fk_teacher_lesson_version_plan FOREIGN KEY (lesson_plan_id)
            REFERENCES teacher_lesson_plans(lesson_plan_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS teacher_lesson_feedback (
        feedback_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        lesson_plan_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        lesson_version INT UNSIGNED NOT NULL,
        teacher_pk BIGINT UNSIGNED NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (feedback_id),
        KEY idx_teacher_lesson_feedback_plan (lesson_plan_id, lesson_version, created_at),
        CONSTRAINT fk_teacher_lesson_feedback_plan FOREIGN KEY (lesson_plan_id)
            REFERENCES teacher_lesson_plans(lesson_plan_id) ON DELETE CASCADE,
        CONSTRAINT fk_teacher_lesson_feedback_teacher FOREIGN KEY (teacher_pk)
            REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS unified_student_profiles (
        student_pk BIGINT UNSIGNED NOT NULL,
        profile_version INT UNSIGNED NOT NULL DEFAULT 1,
        payload_json JSON NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk),
        CONSTRAINT fk_unified_profile_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS unified_learning_events (
        event_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        event_type VARCHAR(48) CHARACTER SET ascii NOT NULL,
        agent_role VARCHAR(64) CHARACTER SET ascii NOT NULL,
        subject VARCHAR(64) CHARACTER SET ascii NULL,
        knowledge_point VARCHAR(256) NULL,
        difficulty DECIMAL(6,5) NULL,
        score DECIMAL(6,5) NULL,
        confidence DECIMAL(6,5) NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii NULL,
        trace_id VARCHAR(128) CHARACTER SET ascii NULL,
        metadata_json JSON NOT NULL,
        occurred_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (event_id),
        KEY idx_unified_event_student_time (student_pk, occurred_at),
        KEY idx_unified_event_knowledge (student_pk, knowledge_point, occurred_at),
        KEY idx_unified_event_session (session_id, occurred_at),
        CONSTRAINT fk_unified_event_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_orchestration_runs (
        run_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii NULL,
        trace_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        routing_json JSON NULL,
        result_json JSON NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (run_id),
        KEY idx_orchestration_student_time (student_pk, created_at),
        KEY idx_orchestration_trace (trace_id),
        CONSTRAINT fk_orchestration_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_execution_traces (
        trace_record_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        request_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        trace_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii NULL,
        agent_role VARCHAR(64) CHARACTER SET ascii NOT NULL,
        node_name VARCHAR(96) CHARACTER SET ascii NOT NULL,
        model_name VARCHAR(128) CHARACTER SET ascii NULL,
        tool_name VARCHAR(128) CHARACTER SET ascii NULL,
        latency_ms INT UNSIGNED NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        error_message TEXT NULL,
        handoff_json JSON NULL,
        event_count INT UNSIGNED NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (trace_record_id),
        KEY idx_agent_trace_trace (trace_id, created_at),
        KEY idx_agent_trace_student (student_pk, created_at),
        KEY idx_agent_trace_agent (agent_role, status, created_at),
        CONSTRAINT fk_agent_trace_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        checksum CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_event_outbox (
        outbox_id VARCHAR(112) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        event_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        event_type VARCHAR(48) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'pending',
        attempts INT UNSIGNED NOT NULL DEFAULT 0,
        last_error TEXT NULL,
        available_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME NULL,
        PRIMARY KEY (outbox_id),
        UNIQUE KEY uk_learning_event_outbox_event (event_id),
        KEY idx_learning_event_outbox_pending (status, available_at, created_at),
        CONSTRAINT fk_learning_event_outbox_event FOREIGN KEY (event_id)
            REFERENCES unified_learning_events(event_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_orchestration_runs (
        run_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        actor_type VARCHAR(24) CHARACTER SET ascii NOT NULL,
        actor_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii NULL,
        trace_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (run_id),
        KEY idx_actor_run_owner (actor_type, actor_id, created_at),
        KEY idx_actor_run_trace (trace_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_execution_traces (
        trace_record_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        request_id VARCHAR(96) CHARACTER SET ascii NOT NULL,
        trace_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        actor_type VARCHAR(24) CHARACTER SET ascii NOT NULL,
        actor_id VARCHAR(128) CHARACTER SET ascii NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii NULL,
        agent_role VARCHAR(64) CHARACTER SET ascii NOT NULL,
        model_name VARCHAR(128) CHARACTER SET ascii NULL,
        model_capability VARCHAR(48) CHARACTER SET ascii NULL,
        latency_ms INT UNSIGNED NOT NULL,
        status VARCHAR(32) CHARACTER SET ascii NOT NULL,
        error_message TEXT NULL,
        handoff_json JSON NULL,
        event_count INT UNSIGNED NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (trace_record_id),
        KEY idx_actor_trace_owner (actor_type, actor_id, created_at),
        KEY idx_actor_trace_agent (agent_role, status, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS collaboration_memories (
        student_pk BIGINT UNSIGNED NOT NULL,
        memory_version INT UNSIGNED NOT NULL DEFAULT 1,
        personalization_mode VARCHAR(40) CHARACTER SET ascii NOT NULL,
        session_count INT UNSIGNED NOT NULL DEFAULT 0,
        interaction_count INT UNSIGNED NOT NULL DEFAULT 0,
        explicit_profile_json JSON NOT NULL, source_summary_json JSON NOT NULL,
        payload_json JSON NOT NULL, first_seen_at DATETIME NOT NULL,
        last_seen_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (student_pk),
        KEY idx_collaboration_memory_mode (personalization_mode, last_seen_at),
        CONSTRAINT fk_collaboration_memory_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS collaboration_sessions (
        session_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL, interaction_count INT UNSIGNED NOT NULL DEFAULT 0,
        context_json JSON NOT NULL, started_at DATETIME NOT NULL, last_active_at DATETIME NOT NULL,
        PRIMARY KEY (session_id), KEY idx_collaboration_session_student (student_pk, last_active_at),
        CONSTRAINT fk_collaboration_session_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS collaboration_messages (
        message_id VARCHAR(112) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        session_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        student_pk BIGINT UNSIGNED NOT NULL, run_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NULL,
        role VARCHAR(24) CHARACTER SET ascii NOT NULL, subject VARCHAR(64) CHARACTER SET ascii NULL,
        content TEXT NOT NULL, metadata_json JSON NOT NULL, created_at DATETIME NOT NULL,
        PRIMARY KEY (message_id), KEY idx_collaboration_message_student (student_pk, created_at),
        KEY idx_collaboration_message_session (session_id, created_at), KEY idx_collaboration_message_run (run_id),
        CONSTRAINT fk_collaboration_message_student FOREIGN KEY (student_pk)
            REFERENCES students(id) ON DELETE CASCADE,
        CONSTRAINT fk_collaboration_message_session FOREIGN KEY (session_id)
            REFERENCES collaboration_sessions(session_id) ON DELETE CASCADE
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
        self.phone_auth_resend_seconds = settings.phone_auth_resend_seconds

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

    def create_student(
        self, profile: dict[str, Any], password_hash: str | None, *, phone_e164: str | None = None
    ) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO students
                    (student_id, password_hash, phone_e164, student_name, grade, province_code, target_exam_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    profile["student_id"].lower(),
                    password_hash,
                    phone_e164,
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
                SELECT id, student_id, password_hash, phone_e164, student_name, grade, province_code,
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

    def create_teacher(
        self, profile: dict[str, Any], password_hash: str | None, *, phone_e164: str | None = None
    ) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO teachers
                    (teacher_id, password_hash, phone_e164, teacher_name, school_name, subject)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    profile["teacher_id"].lower(),
                    password_hash,
                    phone_e164,
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
                SELECT id, teacher_id, password_hash, phone_e164, teacher_name, school_name, subject,
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
            cursor.execute("DELETE FROM teacher_auth_sessions WHERE token_hash=%s", (token_hash,))

    def guard_sms_send(self, phone_e164: str, client_ip: str, purpose: str, role: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT TIMESTAMPDIFF(SECOND, MAX(sent_at), {BEIJING_NOW_SQL}) AS elapsed,
                       SUM(sent_at >= DATE_SUB({BEIJING_NOW_SQL}, INTERVAL 1 HOUR)) AS hourly
                FROM phone_verification_challenges WHERE phone_e164=%s
                """,
                (phone_e164,),
            )
            limits = cursor.fetchone() or {}
            if limits.get("elapsed") is not None:
                elapsed = max(int(limits["elapsed"]), 0)
                if elapsed < self.phone_auth_resend_seconds:
                    remaining = self.phone_auth_resend_seconds - elapsed
                    raise InputValidationError(f"验证码发送过于频繁，请 {remaining} 秒后再试")
            if int(limits.get("hourly") or 0) >= 5:
                raise InputValidationError("该手机号验证码请求过多，请稍后再试")
            cursor.execute(
                f"""
                SELECT COUNT(*) AS hourly FROM phone_verification_challenges
                WHERE client_ip=%s
                      AND sent_at >= DATE_SUB({BEIJING_NOW_SQL}, INTERVAL 1 HOUR)
                """,
                (client_ip[:45],),
            )
            if int((cursor.fetchone() or {}).get("hourly") or 0) >= 20:
                raise InputValidationError("当前网络验证码请求过多，请稍后再试")

    def record_sms_send(self, phone_e164: str, client_ip: str, purpose: str, role: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO phone_verification_challenges
                    (phone_e164, client_ip, purpose, role, sent_at)
                VALUES (%s,%s,%s,%s,{BEIJING_NOW_SQL})
                """,
                (phone_e164, client_ip[:45], purpose, role),
            )

    def guard_sms_verify(self, phone_e164: str, purpose: str, role: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT attempts FROM phone_verification_challenges
                WHERE phone_e164=%s AND purpose=%s AND role=%s AND consumed_at IS NULL
                      AND sent_at >= DATE_SUB({BEIJING_NOW_SQL}, INTERVAL 15 MINUTE)
                ORDER BY id DESC LIMIT 1
                """,
                (phone_e164, purpose, role),
            )
            challenge = cursor.fetchone()
            if not challenge:
                raise InputValidationError("请先获取短信验证码")
            if int(challenge["attempts"]) >= 5:
                raise InputValidationError("验证码尝试次数过多，请重新获取")

    def record_sms_failure(self, phone_e164: str, purpose: str, role: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE phone_verification_challenges SET attempts=attempts+1
                WHERE phone_e164=%s AND purpose=%s AND role=%s AND consumed_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (phone_e164, purpose, role),
            )

    def consume_sms_challenge(self, phone_e164: str, purpose: str, role: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE phone_verification_challenges SET consumed_at={BEIJING_NOW_SQL}
                WHERE phone_e164=%s AND purpose=%s AND role=%s AND consumed_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (phone_e164, purpose, role),
            )

    def guard_admin_login(self, client_ip: str, username: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS failures FROM admin_audit_logs
                WHERE action='admin.login.failed'
                  AND created_at >= UTC_TIMESTAMP() - INTERVAL 15 MINUTE
                  AND (client_ip=%s OR target_account_id=%s)
                """,
                (client_ip[:45], username[:64].lower()),
            )
            if int((cursor.fetchone() or {}).get("failures") or 0) >= 5:
                raise InputValidationError("管理员登录尝试过多，请 15 分钟后再试")

    def record_admin_login_failure(self, client_ip: str, username: str) -> None:
        self.record_admin_audit(
            admin_username=username[:64].lower() or "unknown",
            action="admin.login.failed",
            target_role="super_admin",
            target_account_id=username[:64].lower() or "unknown",
            reason="管理员登录失败",
            metadata={},
            client_ip=client_ip,
        )

    def create_admin_session(
        self,
        token_hash: str,
        admin_username: str,
        expires_at: datetime,
        client_ip: str,
        user_agent: str,
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM admin_sessions WHERE expires_at<=UTC_TIMESTAMP()")
            cursor.execute(
                """
                INSERT INTO admin_sessions
                    (token_hash, admin_username, expires_at, client_ip, user_agent)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    token_hash,
                    admin_username.lower(),
                    _mysql_datetime(expires_at),
                    client_ip[:45],
                    user_agent[:255],
                ),
            )

    def resolve_admin_session(self, token_hash: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT admin_username, expires_at, created_at, last_seen_at
                FROM admin_sessions
                WHERE token_hash=%s AND expires_at>UTC_TIMESTAMP()
                """,
                (token_hash,),
            )
            session = cursor.fetchone()
            if session:
                cursor.execute(
                    "UPDATE admin_sessions SET last_seen_at=UTC_TIMESTAMP() WHERE token_hash=%s",
                    (token_hash,),
                )
            return session

    def delete_admin_session(self, token_hash: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM admin_sessions WHERE token_hash=%s", (token_hash,))

    @staticmethod
    def _insert_admin_audit(
        cursor: DictCursor,
        *,
        admin_username: str,
        action: str,
        target_role: str | None,
        target_account_id: str | None,
        reason: str,
        metadata: dict[str, Any],
        client_ip: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO admin_audit_logs
                (admin_username, action, target_role, target_account_id,
                 reason, metadata_json, client_ip)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                admin_username.lower(),
                action,
                target_role,
                target_account_id.lower() if target_account_id else None,
                reason,
                _json(metadata),
                client_ip[:45],
            ),
        )

    def record_admin_audit(
        self,
        *,
        admin_username: str,
        action: str,
        target_role: str | None,
        target_account_id: str | None,
        reason: str,
        metadata: dict[str, Any],
        client_ip: str,
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            self._insert_admin_audit(
                cursor,
                admin_username=admin_username,
                action=action,
                target_role=target_role,
                target_account_id=target_account_id,
                reason=reason,
                metadata=metadata,
                client_ip=client_ip,
            )

    def admin_account_overview(self) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(is_active=1) AS active,
                       SUM(phone_e164 IS NULL) AS unbound
                FROM students
                """
            )
            students = cursor.fetchone() or {}
            cursor.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(is_active=1) AS active,
                       SUM(phone_e164 IS NULL) AS unbound
                FROM teachers
                """
            )
            teachers = cursor.fetchone() or {}
            cursor.execute(
                """
                SELECT COUNT(*) AS operations FROM admin_audit_logs
                WHERE created_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
                  AND action<>'admin.login.failed'
                """
            )
            audit = cursor.fetchone() or {}
            return {
                "students": {key: int(students.get(key) or 0) for key in ("total", "active", "unbound")},
                "teachers": {key: int(teachers.get(key) or 0) for key in ("total", "active", "unbound")},
                "operations_24h": int(audit.get("operations") or 0),
            }

    def list_admin_accounts(
        self,
        *,
        role: str,
        query: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        selects: list[str] = []
        params: list[Any] = []
        wildcard = f"%{query}%"
        digits = re.sub(r"\D", "", query)
        phone = f"+86{digits}" if len(digits) == 11 else query
        if role in {"all", "student"}:
            where = ""
            if query:
                where = "WHERE student_id LIKE %s OR student_name LIKE %s OR phone_e164=%s"
                params.extend((wildcard, wildcard, phone))
            selects.append(
                """
                SELECT 'student' AS role, student_id AS account_id,
                       student_name AS display_name, grade AS context,
                       phone_e164, is_active, created_at, updated_at
                FROM students
                """
                + where
            )
        if role in {"all", "teacher"}:
            where = ""
            if query:
                where = "WHERE teacher_id LIKE %s OR teacher_name LIKE %s OR phone_e164=%s"
                params.extend((wildcard, wildcard, phone))
            selects.append(
                """
                SELECT 'teacher' AS role, teacher_id AS account_id,
                       teacher_name AS display_name, school_name AS context,
                       phone_e164, is_active, created_at, updated_at
                FROM teachers
                """
                + where
            )
        sql = "SELECT * FROM (" + " UNION ALL ".join(selects) + ") accounts "
        sql += "ORDER BY created_at DESC, account_id LIMIT %s OFFSET %s"
        params.extend((limit + 1, offset))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return list(cursor.fetchall())

    _STUDENT_IMPACT_TABLES = {
        "登录会话": "auth_sessions",
        "班级关系": "classroom_members",
        "退班申请": "classroom_leave_requests",
        "学习状态": "student_state_records",
        "学习计划": "learning_plans",
        "作业会话": "homework_sessions",
        "答案保险库": "answer_vault_records",
        "英语学习记录": "english_learning_events",
        "编程学习记录": "programming_learning_records",
        "学习证据": "learning_evidence_records",
        "学情诊断": "learning_diagnosis_reports",
        "考试诊断": "exam_diagnostic_sessions",
        "Agent运行": "agent_orchestration_runs",
        "协作消息": "collaboration_messages",
    }
    _TEACHER_IMPACT_TABLES = {
        "登录会话": "teacher_auth_sessions",
        "创建的班级": "classrooms",
        "协作班级关系": "classroom_teachers",
        "班级通知": "classroom_announcements",
        "诊断任务": "classroom_exam_assignments",
        "教案": "teacher_lesson_plans",
        "课后反馈": "teacher_lesson_feedback",
    }

    @classmethod
    def _admin_account_deletion_impact(
        cls,
        cursor: DictCursor,
        role: str,
        account_id: str,
        *,
        lock: bool = False,
    ) -> dict[str, Any] | None:
        if role == "student":
            cursor.execute(
                """
                SELECT id, student_id AS account_id, student_name AS display_name,
                       phone_e164, is_active, created_at
                FROM students WHERE student_id=%s
                """
                + (" FOR UPDATE" if lock else ""),
                (account_id,),
            )
            tables = cls._STUDENT_IMPACT_TABLES
            pk_column = "student_pk"
        elif role == "teacher":
            cursor.execute(
                """
                SELECT id, teacher_id AS account_id, teacher_name AS display_name,
                       phone_e164, is_active, created_at
                FROM teachers WHERE teacher_id=%s
                """
                + (" FOR UPDATE" if lock else ""),
                (account_id,),
            )
            tables = cls._TEACHER_IMPACT_TABLES
            pk_column = "teacher_pk"
        else:
            raise InputValidationError("不支持的账号类型")
        account = cursor.fetchone()
        if not account:
            return None
        related: dict[str, int] = {}
        for label, table in tables.items():
            cursor.execute(f"SELECT COUNT(*) AS amount FROM {table} WHERE {pk_column}=%s", (account["id"],))
            related[label] = int((cursor.fetchone() or {}).get("amount") or 0)
        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM actor_orchestration_runs
               WHERE actor_type=%s AND actor_id=%s)
              + (SELECT COUNT(*) FROM actor_execution_traces
                 WHERE actor_type=%s AND actor_id=%s) AS amount
            """,
            (role, account_id, role, account_id),
        )
        related["跨Agent审计"] = int((cursor.fetchone() or {}).get("amount") or 0)
        result = dict(account)
        result.pop("id", None)
        result["role"] = role
        result["related_counts"] = related
        result["related_records"] = sum(related.values())
        return result

    def admin_account_deletion_impact(
        self, role: str, account_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            return self._admin_account_deletion_impact(cursor, role, account_id)

    def admin_rebind_student_phone(
        self,
        *,
        student_id: str,
        phone_e164: str,
        admin_username: str,
        reason: str,
        client_ip: str,
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, phone_e164 FROM students
                WHERE student_id=%s FOR UPDATE
                """,
                (student_id,),
            )
            current = cursor.fetchone()
            if not current:
                return None
            cursor.execute(
                "UPDATE students SET phone_e164=%s WHERE id=%s",
                (phone_e164, current["id"]),
            )
            cursor.execute("DELETE FROM auth_sessions WHERE student_pk=%s", (current["id"],))
            old_phone = current.get("phone_e164")
            self._insert_admin_audit(
                cursor,
                admin_username=admin_username,
                action="student.phone_rebound",
                target_role="student",
                target_account_id=student_id,
                reason=reason,
                metadata={
                    "old_phone_masked": (
                        f"{old_phone[-11:-8]}****{old_phone[-4:]}" if old_phone else "未绑定"
                    ),
                    "new_phone_masked": f"{phone_e164[-11:-8]}****{phone_e164[-4:]}",
                    "sessions_revoked": True,
                },
                client_ip=client_ip,
            )
            cursor.execute(
                """
                SELECT student_id AS account_id, student_name AS display_name,
                       phone_e164, is_active, created_at, updated_at
                FROM students WHERE id=%s
                """,
                (current["id"],),
            )
            return cursor.fetchone()

    def admin_delete_account(
        self,
        *,
        role: str,
        account_id: str,
        admin_username: str,
        reason: str,
        client_ip: str,
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            impact = self._admin_account_deletion_impact(
                cursor, role, account_id, lock=True
            )
            if not impact:
                return None
            cursor.execute(
                "DELETE FROM actor_execution_traces WHERE actor_type=%s AND actor_id=%s",
                (role, account_id),
            )
            cursor.execute(
                "DELETE FROM actor_orchestration_runs WHERE actor_type=%s AND actor_id=%s",
                (role, account_id),
            )
            self._insert_admin_audit(
                cursor,
                admin_username=admin_username,
                action=f"{role}.account_deleted",
                target_role=role,
                target_account_id=account_id,
                reason=reason,
                metadata={
                    "display_name": impact["display_name"],
                    "phone_was_bound": impact["phone_e164"] is not None,
                    "related_counts": impact["related_counts"],
                    "permanent_deletion": True,
                },
                client_ip=client_ip,
            )
            table = "students" if role == "student" else "teachers"
            id_column = "student_id" if role == "student" else "teacher_id"
            cursor.execute(f"DELETE FROM {table} WHERE {id_column}=%s", (account_id,))
            if cursor.rowcount != 1:
                raise InputValidationError("账号注销失败，请稍后重试")
            return {
                "deleted": True,
                "role": role,
                "account_id": account_id,
                "display_name": impact["display_name"],
                "related_records": impact["related_records"],
            }

    def list_admin_audits(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, admin_username, action, target_role, target_account_id,
                       reason, metadata_json, client_ip, created_at
                FROM admin_audit_logs
                ORDER BY id DESC LIMIT %s OFFSET %s
                """,
                (max(1, min(limit, 101)), max(0, offset)),
            )
            rows = list(cursor.fetchall())
            for row in rows:
                row["metadata"] = _decoded(row.pop("metadata_json"))
                row["client_ip"] = "已记录"
            return rows

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
                    payload["class_code"],
                    teacher_pk,
                    payload["class_name"],
                    payload["grade"],
                    payload.get("subject"),
                ),
            )
            classroom_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO classroom_teachers (classroom_pk, teacher_pk, role, status)
                VALUES (%s,%s,'owner','active')
                ON DUPLICATE KEY UPDATE role='owner', status='active',
                    updated_at=UTC_TIMESTAMP()
                """,
                (classroom_id, teacher_pk),
            )
        return self.teacher_classroom(teacher_id, classroom_id) or {}

    def teacher_classroom(self, teacher_id: str, classroom_id: int) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.join_policy, c.student_join_policy, c.status,
                       c.created_at, c.updated_at, owner.teacher_name AS owner_teacher_name,
                       owner.school_name AS owner_school_name,
                       CASE WHEN c.teacher_pk=actor.id THEN 'owner'
                            ELSE 'collaborator' END AS teacher_access_role,
                       COALESCE(ct.joined_at, c.created_at) AS teacher_joined_at,
                       teacher_leave.request_id AS teacher_leave_request_id,
                       teacher_leave.status AS teacher_leave_request_status,
                       COUNT(CASE WHEN m.status='active' THEN 1 END) AS student_count
                FROM classrooms c
                JOIN teachers owner ON owner.id=c.teacher_pk
                JOIN teachers actor ON actor.teacher_id=%s AND actor.is_active=1
                LEFT JOIN classroom_teachers ct
                    ON ct.classroom_pk=c.id AND ct.teacher_pk=actor.id AND ct.status='active'
                LEFT JOIN classroom_teacher_leave_requests teacher_leave
                    ON teacher_leave.classroom_pk=c.id AND teacher_leave.teacher_pk=actor.id
                LEFT JOIN classroom_members m ON m.classroom_pk=c.id
                WHERE c.id=%s AND c.status='active'
                  AND (c.teacher_pk=actor.id OR ct.teacher_pk IS NOT NULL)
                GROUP BY c.id
                """,
                (teacher_id.lower(), classroom_id),
            )
            return cursor.fetchone()

    def list_teacher_classrooms(self, teacher_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.grade, c.subject, c.join_policy, c.student_join_policy, c.status,
                       c.created_at, c.updated_at, owner.teacher_name AS owner_teacher_name,
                       owner.school_name AS owner_school_name,
                       CASE WHEN c.teacher_pk=actor.id THEN 'owner'
                            ELSE 'collaborator' END AS teacher_access_role,
                       COALESCE(ct.joined_at, c.created_at) AS teacher_joined_at,
                       teacher_leave.request_id AS teacher_leave_request_id,
                       teacher_leave.status AS teacher_leave_request_status,
                       COUNT(CASE WHEN m.status='active' THEN 1 END) AS student_count
                FROM classrooms c
                JOIN teachers owner ON owner.id=c.teacher_pk
                JOIN teachers actor ON actor.teacher_id=%s AND actor.is_active=1
                LEFT JOIN classroom_teachers ct
                    ON ct.classroom_pk=c.id AND ct.teacher_pk=actor.id AND ct.status='active'
                LEFT JOIN classroom_teacher_leave_requests teacher_leave
                    ON teacher_leave.classroom_pk=c.id AND teacher_leave.teacher_pk=actor.id
                LEFT JOIN classroom_members m ON m.classroom_pk=c.id
                WHERE c.status='active'
                  AND (c.teacher_pk=actor.id OR ct.teacher_pk IS NOT NULL)
                GROUP BY c.id
                ORDER BY teacher_access_role='owner' DESC, teacher_joined_at DESC
                """,
                (teacher_id.lower(),),
            )
            return list(cursor.fetchall())

    def join_teacher_classroom(self, teacher_id: str, class_code: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                SELECT id, teacher_pk, class_name, join_policy FROM classrooms
                WHERE class_code=%s AND status='active'
                """,
                (class_code.upper(),),
            )
            classroom = cursor.fetchone()
            if teacher_pk is None or not classroom:
                return None
            role = "owner" if int(classroom["teacher_pk"]) == teacher_pk else "collaborator"
            status = (
                "active"
                if role == "owner" or classroom.get("join_policy", "open") == "open"
                else "pending"
            )
            cursor.execute(
                """
                INSERT INTO classroom_teachers (classroom_pk, teacher_pk, role, status)
                VALUES (%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE role=VALUES(role), status=VALUES(status),
                    updated_at=UTC_TIMESTAMP()
                """,
                (classroom["id"], teacher_pk, role, status),
            )
            classroom_id = int(classroom["id"])
        active = self.teacher_classroom(teacher_id, classroom_id)
        if active:
            return active
        return {
            "id": classroom_id,
            "class_code": class_code.upper(),
            "class_name": classroom.get("class_name", ""),
            "teacher_access_role": role,
            "membership_status": "pending",
            "join_policy": classroom.get("join_policy", "approval"),
        }

    def list_classroom_teachers(
        self, teacher_id: str, classroom_id: int
    ) -> list[dict[str, Any]] | None:
        classroom = self.teacher_classroom(teacher_id, classroom_id)
        if not classroom:
            return None
        membership_filter = (
            "" if classroom["teacher_access_role"] == "owner" else "AND ct.status='active'"
        )
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT t.teacher_id, t.teacher_name, t.school_name, t.subject,
                       CASE WHEN ct.role='owner' THEN 'owner' ELSE 'collaborator' END AS role,
                       ct.status, ct.joined_at, ct.reviewed_at, ct.updated_at
                FROM classroom_teachers ct JOIN teachers t ON t.id=ct.teacher_pk
                WHERE ct.classroom_pk=%s {membership_filter}
                ORDER BY ct.role='owner' DESC, ct.joined_at ASC
            """,
                (classroom_id,),
            )
            return list(cursor.fetchall())

    def remove_classroom_teacher(
        self, teacher_id: str, classroom_id: int, member_teacher_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                "SELECT teacher_pk FROM classrooms WHERE id=%s AND status='active'", (classroom_id,)
            )
            classroom = cursor.fetchone()
            if not classroom or owner_pk is None or int(classroom["teacher_pk"]) != owner_pk:
                return None
            cursor.execute(
                """UPDATE classroom_teachers ct JOIN teachers t ON t.id=ct.teacher_pk
                SET ct.status='removed', ct.updated_at=UTC_TIMESTAMP(), ct.last_action_at=UTC_TIMESTAMP()
                WHERE ct.classroom_pk=%s AND t.teacher_id=%s AND ct.role<>'owner' AND ct.status<>'removed'""",
                (classroom_id, member_teacher_id.lower()),
            )
            if cursor.rowcount == 0:
                return None
        return {
            "classroom_id": classroom_id,
            "teacher_id": member_teacher_id.lower(),
            "status": "removed",
        }

    def create_teacher_classroom_leave_request(
        self, teacher_id: str, classroom_id: int, request_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            if teacher_pk is None:
                return None
            cursor.execute(
                """
                SELECT ct.status, ct.role
                FROM classroom_teachers ct
                JOIN classrooms c ON c.id=ct.classroom_pk
                WHERE ct.classroom_pk=%s AND ct.teacher_pk=%s
                  AND ct.role='collaborator' AND ct.status='active' AND c.status='active'
                FOR UPDATE
                """,
                (classroom_id, teacher_pk),
            )
            if not cursor.fetchone():
                return None
            cursor.execute(
                """
                SELECT request_id FROM classroom_teacher_leave_requests
                WHERE classroom_pk=%s AND teacher_pk=%s AND status='pending'
                """,
                (classroom_id, teacher_pk),
            )
            pending = cursor.fetchone()
            if pending:
                request_id = pending["request_id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO classroom_teacher_leave_requests
                        (request_id, classroom_pk, teacher_pk, status, requested_at,
                         reviewed_at, reviewer_note)
                    VALUES (%s,%s,%s,'pending',UTC_TIMESTAMP(),NULL,NULL)
                    ON DUPLICATE KEY UPDATE request_id=VALUES(request_id), status='pending',
                        requested_at=UTC_TIMESTAMP(), reviewed_at=NULL, reviewer_note=NULL,
                        updated_at=UTC_TIMESTAMP()
                    """,
                    (request_id, classroom_id, teacher_pk),
                )
            cursor.execute(
                """
                SELECT r.request_id, 'collaborator' AS request_source,
                       r.classroom_pk AS classroom_id, c.class_name,
                       applicant.teacher_id AS applicant_id,
                       applicant.teacher_name AS applicant_name,
                       applicant.teacher_id, applicant.teacher_name,
                       owner.teacher_name AS owner_teacher_name,
                       r.status, r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_teacher_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN teachers applicant ON applicant.id=r.teacher_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE r.request_id=%s
                """,
                (request_id,),
            )
            return cursor.fetchone()

    def transfer_classroom_owner(
        self, teacher_id: str, classroom_id: int, member_teacher_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            target_pk = self._teacher_pk(cursor, member_teacher_id)
            if owner_pk is None or target_pk is None or owner_pk == target_pk:
                return None
            cursor.execute(
                "SELECT teacher_pk FROM classrooms WHERE id=%s AND status='active' FOR UPDATE",
                (classroom_id,),
            )
            classroom = cursor.fetchone()
            if not classroom or int(classroom["teacher_pk"]) != owner_pk:
                return None
            cursor.execute(
                """
                SELECT status FROM classroom_teachers
                WHERE classroom_pk=%s AND teacher_pk=%s
                  AND role='collaborator' AND status='active'
                FOR UPDATE
                """,
                (classroom_id, target_pk),
            )
            if not cursor.fetchone():
                return None
            cursor.execute(
                """
                SELECT request_id FROM classroom_teacher_leave_requests
                WHERE classroom_pk=%s AND teacher_pk=%s AND status='pending'
                FOR UPDATE
                """,
                (classroom_id, target_pk),
            )
            if cursor.fetchone():
                return None
            cursor.execute(
                """
                UPDATE classroom_teachers
                SET role='collaborator', status='active', updated_at=UTC_TIMESTAMP(),
                    last_action_at=UTC_TIMESTAMP()
                WHERE classroom_pk=%s AND teacher_pk=%s
                """,
                (classroom_id, owner_pk),
            )
            cursor.execute(
                """
                UPDATE classroom_teachers
                SET role='owner', status='active', reviewed_at=UTC_TIMESTAMP(),
                    updated_at=UTC_TIMESTAMP(), last_action_at=UTC_TIMESTAMP()
                WHERE classroom_pk=%s AND teacher_pk=%s
                """,
                (classroom_id, target_pk),
            )
            cursor.execute(
                """
                UPDATE classrooms SET teacher_pk=%s, updated_at=UTC_TIMESTAMP()
                WHERE id=%s AND teacher_pk=%s AND status='active'
                """,
                (target_pk, classroom_id, owner_pk),
            )
            if cursor.rowcount == 0:
                return None
        classroom = self.teacher_classroom(teacher_id, classroom_id)
        if classroom is not None:
            classroom["transferred_owner_teacher_id"] = member_teacher_id.lower()
        return classroom

    def review_teacher_join(
        self, teacher_id: str, classroom_id: int, member_teacher_id: str, decision: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                "SELECT teacher_pk FROM classrooms WHERE id=%s AND status='active'", (classroom_id,)
            )
            classroom = cursor.fetchone()
            if not classroom or owner_pk is None or int(classroom["teacher_pk"]) != owner_pk:
                return None
            status = "active" if decision == "approved" else "rejected"
            cursor.execute(
                """UPDATE classroom_teachers ct JOIN teachers t ON t.id=ct.teacher_pk
                SET ct.status=%s, ct.reviewed_at=UTC_TIMESTAMP(), ct.updated_at=UTC_TIMESTAMP(), ct.last_action_at=UTC_TIMESTAMP()
                WHERE ct.classroom_pk=%s AND t.teacher_id=%s AND ct.role<>'owner' AND ct.status='pending'""",
                (status, classroom_id, member_teacher_id.lower()),
            )
            if cursor.rowcount == 0:
                return None
        return {
            "classroom_id": classroom_id,
            "teacher_id": member_teacher_id.lower(),
            "status": status,
        }

    def update_classroom_join_policy(
        self, teacher_id: str, classroom_id: int, policy: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                "UPDATE classrooms SET join_policy=%s, updated_at=UTC_TIMESTAMP() WHERE id=%s AND teacher_pk=%s AND status='active'",
                (policy, classroom_id, owner_pk),
            )
            if cursor.rowcount == 0:
                return None
        return self.teacher_classroom(teacher_id, classroom_id)

    def update_student_classroom_join_policy(
        self, teacher_id: str, classroom_id: int, policy: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                UPDATE classrooms
                SET student_join_policy=%s, updated_at=UTC_TIMESTAMP()
                WHERE id=%s AND teacher_pk=%s AND status='active'
                """,
                (policy, classroom_id, owner_pk),
            )
            if cursor.rowcount == 0:
                return None
        return self.teacher_classroom(teacher_id, classroom_id)

    def join_classroom(
        self, student_id: str, class_code: str, request_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            cursor.execute(
                """
                SELECT c.id, c.class_code, c.class_name, c.student_join_policy,
                       t.teacher_name, t.school_name
                FROM classrooms c
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE c.class_code=%s AND c.status='active'
                FOR UPDATE
                """,
                (class_code.upper(),),
            )
            classroom = cursor.fetchone()
            if student_pk is None or not classroom:
                return None
            classroom_id = int(classroom["id"])
            cursor.execute(
                """
                SELECT status FROM classroom_members
                WHERE classroom_pk=%s AND student_pk=%s
                """,
                (classroom_id, student_pk),
            )
            membership = cursor.fetchone()
            if membership and membership["status"] == "active":
                active = self.student_classroom(student_id, classroom_id)
                if active:
                    active["membership_status"] = "active"
                    active["student_join_policy"] = classroom["student_join_policy"]
                return active
            if classroom["student_join_policy"] == "approval":
                cursor.execute(
                    """
                    SELECT request_id, status FROM classroom_join_requests
                    WHERE classroom_pk=%s AND student_pk=%s
                    FOR UPDATE
                    """,
                    (classroom_id, student_pk),
                )
                previous = cursor.fetchone()
                if previous and previous["status"] == "pending":
                    request_id = previous["request_id"]
                else:
                    cursor.execute(
                        """
                        INSERT INTO classroom_join_requests
                            (request_id, classroom_pk, student_pk, status, requested_at,
                             reviewed_at, reviewer_teacher_pk, reviewer_note)
                        VALUES (%s,%s,%s,'pending',UTC_TIMESTAMP(),NULL,NULL,NULL)
                        ON DUPLICATE KEY UPDATE request_id=VALUES(request_id),
                            status='pending', requested_at=UTC_TIMESTAMP(), reviewed_at=NULL,
                            reviewer_teacher_pk=NULL, reviewer_note=NULL,
                            updated_at=UTC_TIMESTAMP()
                        """,
                        (request_id, classroom_id, student_pk),
                    )
                return {
                    "id": classroom_id,
                    "class_code": classroom["class_code"],
                    "class_name": classroom["class_name"],
                    "teacher_name": classroom["teacher_name"],
                    "school_name": classroom["school_name"],
                    "membership_status": "pending",
                    "student_join_policy": "approval",
                    "join_request_id": request_id,
                }
            cursor.execute(
                """
                INSERT INTO classroom_members (classroom_pk, student_pk, status, joined_at)
                VALUES (%s,%s,'active',UTC_TIMESTAMP())
                ON DUPLICATE KEY UPDATE status='active', joined_at=UTC_TIMESTAMP(),
                    updated_at=UTC_TIMESTAMP()
                """,
                (classroom_id, student_pk),
            )
            cursor.execute(
                """
                UPDATE classroom_join_requests
                SET status='approved', reviewed_at=UTC_TIMESTAMP(),
                    reviewer_note='班级设置为直接加入', updated_at=UTC_TIMESTAMP()
                WHERE classroom_pk=%s AND student_pk=%s AND status='pending'
                """,
                (classroom_id, student_pk),
            )
            cursor.execute(
                "DELETE FROM classroom_leave_requests WHERE classroom_pk=%s AND student_pk=%s",
                (classroom_id, student_pk),
            )
        active = self.student_classroom(student_id, classroom_id)
        if active:
            active["membership_status"] = "active"
            active["student_join_policy"] = "open"
        return active

    def list_student_classroom_join_requests(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_code,
                       c.class_name, s.student_id, s.student_name,
                       owner.teacher_name, owner.school_name, r.status,
                       r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_join_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE s.student_id=%s
                ORDER BY r.requested_at DESC LIMIT 100
                """,
                (student_id.lower(),),
            )
            return list(cursor.fetchall())

    def list_teacher_classroom_join_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        filters = ["owner.teacher_id=%s", "r.status='pending'"]
        params: list[Any] = [teacher_id.lower()]
        if classroom_id is not None:
            filters.append("r.classroom_pk=%s")
            params.append(classroom_id)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id, s.student_name, s.grade, s.province_code,
                       s.target_exam_year, r.status, r.requested_at,
                       r.reviewed_at, r.reviewer_note
                FROM classroom_join_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE {" AND ".join(filters)}
                ORDER BY r.requested_at ASC LIMIT 200
                """,
                tuple(params),
            )
            return list(cursor.fetchall())

    def review_student_classroom_join_request(
        self, teacher_id: str, request_id: str, decision: str, reviewer_note: str | None
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            owner_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                SELECT r.classroom_pk, r.student_pk, r.status
                FROM classroom_join_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                WHERE r.request_id=%s AND c.teacher_pk=%s
                FOR UPDATE
                """,
                (request_id, owner_pk),
            )
            request = cursor.fetchone()
            if not request or request["status"] != "pending":
                return None
            cursor.execute(
                """
                UPDATE classroom_join_requests
                SET status=%s, reviewed_at=UTC_TIMESTAMP(), reviewer_teacher_pk=%s,
                    reviewer_note=%s, updated_at=UTC_TIMESTAMP()
                WHERE request_id=%s
                """,
                (decision, owner_pk, reviewer_note, request_id),
            )
            if decision == "approved":
                cursor.execute(
                    """
                    INSERT INTO classroom_members
                        (classroom_pk, student_pk, status, joined_at)
                    VALUES (%s,%s,'active',UTC_TIMESTAMP())
                    ON DUPLICATE KEY UPDATE status='active', joined_at=UTC_TIMESTAMP(),
                        updated_at=UTC_TIMESTAMP()
                    """,
                    (request["classroom_pk"], request["student_pk"]),
                )
                cursor.execute(
                    """
                    DELETE FROM classroom_leave_requests
                    WHERE classroom_pk=%s AND student_pk=%s
                    """,
                    (request["classroom_pk"], request["student_pk"]),
                )
            cursor.execute(
                """
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id, s.student_name, r.status, r.requested_at,
                       r.reviewed_at, r.reviewer_note
                FROM classroom_join_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                WHERE r.request_id=%s
                """,
                (request_id,),
            )
            return cursor.fetchone()

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
                       t.teacher_name, t.school_name, m.joined_at,
                       r.request_id AS leave_request_id,
                       r.status AS leave_request_status
                FROM classroom_members m
                JOIN classrooms c ON c.id=m.classroom_pk
                JOIN teachers t ON t.id=c.teacher_pk
                JOIN students s ON s.id=m.student_pk
                LEFT JOIN classroom_leave_requests r
                    ON r.classroom_pk=m.classroom_pk AND r.student_pk=m.student_pk
                WHERE s.student_id=%s AND m.status='active' AND c.status='active'
                ORDER BY m.joined_at DESC
                """,
                (student_id.lower(),),
            )
            return list(cursor.fetchall())

    def create_classroom_leave_request(
        self, student_id: str, classroom_id: int, request_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.student_pk FROM classroom_members m
                JOIN students s ON s.id=m.student_pk
                JOIN classrooms c ON c.id=m.classroom_pk
                WHERE s.student_id=%s AND m.classroom_pk=%s
                  AND m.status='active' AND c.status='active'
                FOR UPDATE
                """,
                (student_id.lower(), classroom_id),
            )
            membership = cursor.fetchone()
            if not membership:
                return None
            cursor.execute(
                """
                SELECT request_id FROM classroom_leave_requests
                WHERE classroom_pk=%s AND student_pk=%s AND status='pending'
                """,
                (classroom_id, membership["student_pk"]),
            )
            pending = cursor.fetchone()
            if pending:
                request_id = pending["request_id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO classroom_leave_requests
                        (request_id, classroom_pk, student_pk, status, requested_at,
                         reviewed_at, reviewer_note)
                    VALUES (%s,%s,%s,'pending',UTC_TIMESTAMP(),NULL,NULL)
                    ON DUPLICATE KEY UPDATE request_id=VALUES(request_id), status='pending',
                        requested_at=UTC_TIMESTAMP(), reviewed_at=NULL, reviewer_note=NULL,
                        updated_at=UTC_TIMESTAMP()
                    """,
                    (request_id, classroom_id, membership["student_pk"]),
                )
            cursor.execute(
                """
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id, s.student_name, t.teacher_name, r.status,
                       r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE r.request_id=%s
                """,
                (request_id,),
            )
            return cursor.fetchone()

    def list_student_classroom_leave_requests(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id, s.student_name, t.teacher_name, r.status,
                       r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE s.student_id=%s
                ORDER BY r.requested_at DESC LIMIT 100
                """,
                (student_id.lower(),),
            )
            return list(cursor.fetchall())

    def list_teacher_classroom_leave_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        filters = ["t.teacher_id=%s", "r.status='pending'"]
        params: list[Any] = [teacher_id.lower()]
        if classroom_id is not None:
            filters.append("r.classroom_pk=%s")
            params.append(classroom_id)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT r.request_id, 'student' AS request_source,
                       r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id AS applicant_id, s.student_name AS applicant_name,
                       s.student_id, s.student_name, t.teacher_name, r.status,
                       r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE {" AND ".join(filters)}
                ORDER BY r.requested_at ASC LIMIT 200
                """,
                tuple(params),
            )
            return list(cursor.fetchall())

    def review_classroom_leave_request(
        self, teacher_id: str, request_id: str, decision: str, reviewer_note: str | None
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.classroom_pk, r.student_pk, r.status
                FROM classroom_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE r.request_id=%s AND t.teacher_id=%s
                FOR UPDATE
                """,
                (request_id, teacher_id.lower()),
            )
            request = cursor.fetchone()
            if not request or request["status"] != "pending":
                return None
            cursor.execute(
                """
                UPDATE classroom_leave_requests
                SET status=%s, reviewed_at=UTC_TIMESTAMP(), reviewer_note=%s,
                    updated_at=UTC_TIMESTAMP()
                WHERE request_id=%s
                """,
                (decision, reviewer_note, request_id),
            )
            if decision == "approved":
                cursor.execute(
                    """
                    UPDATE classroom_members SET status='left', updated_at=UTC_TIMESTAMP()
                    WHERE classroom_pk=%s AND student_pk=%s AND status='active'
                    """,
                    (request["classroom_pk"], request["student_pk"]),
                )
            cursor.execute(
                """
                SELECT r.request_id, r.classroom_pk AS classroom_id, c.class_name,
                       s.student_id, s.student_name, t.teacher_name, r.status,
                       r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN students s ON s.id=r.student_pk
                JOIN teachers t ON t.id=c.teacher_pk
                WHERE r.request_id=%s
                """,
                (request_id,),
            )
            return cursor.fetchone()

    def list_teacher_leave_requests(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        filters = ["owner.teacher_id=%s", "r.status='pending'"]
        params: list[Any] = [teacher_id.lower()]
        if classroom_id is not None:
            filters.append("r.classroom_pk=%s")
            params.append(classroom_id)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT r.request_id, 'collaborator' AS request_source,
                       r.classroom_pk AS classroom_id, c.class_name,
                       applicant.teacher_id AS applicant_id,
                       applicant.teacher_name AS applicant_name,
                       applicant.teacher_id, applicant.teacher_name,
                       owner.teacher_name AS owner_teacher_name,
                       r.status, r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_teacher_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN teachers applicant ON applicant.id=r.teacher_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE {" AND ".join(filters)}
                ORDER BY r.requested_at ASC LIMIT 200
                """,
                tuple(params),
            )
            return list(cursor.fetchall())

    def review_teacher_leave_request(
        self, teacher_id: str, request_id: str, decision: str, reviewer_note: str | None
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.classroom_pk, r.teacher_pk, r.status
                FROM classroom_teacher_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE r.request_id=%s AND owner.teacher_id=%s
                FOR UPDATE
                """,
                (request_id, teacher_id.lower()),
            )
            request = cursor.fetchone()
            if not request or request["status"] != "pending":
                return None
            cursor.execute(
                """
                UPDATE classroom_teacher_leave_requests
                SET status=%s, reviewed_at=UTC_TIMESTAMP(), reviewer_note=%s,
                    updated_at=UTC_TIMESTAMP()
                WHERE request_id=%s
                """,
                (decision, reviewer_note, request_id),
            )
            if decision == "approved":
                cursor.execute(
                    """
                    UPDATE classroom_teachers
                    SET status='left', updated_at=UTC_TIMESTAMP(),
                        last_action_at=UTC_TIMESTAMP()
                    WHERE classroom_pk=%s AND teacher_pk=%s
                      AND role='collaborator' AND status='active'
                    """,
                    (request["classroom_pk"], request["teacher_pk"]),
                )
            cursor.execute(
                """
                SELECT r.request_id, 'collaborator' AS request_source,
                       r.classroom_pk AS classroom_id, c.class_name,
                       applicant.teacher_id AS applicant_id,
                       applicant.teacher_name AS applicant_name,
                       applicant.teacher_id, applicant.teacher_name,
                       owner.teacher_name AS owner_teacher_name,
                       r.status, r.requested_at, r.reviewed_at, r.reviewer_note
                FROM classroom_teacher_leave_requests r
                JOIN classrooms c ON c.id=r.classroom_pk
                JOIN teachers applicant ON applicant.id=r.teacher_pk
                JOIN teachers owner ON owner.id=c.teacher_pk
                WHERE r.request_id=%s
                """,
                (request_id,),
            )
            return cursor.fetchone()


    def create_announcement(
        self, teacher_id: str, classroom_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        classroom = self.teacher_classroom(teacher_id, classroom_id)
        if not classroom or classroom.get("teacher_access_role") not in {"owner", "collaborator"}:
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
                    payload["announcement_id"],
                    classroom_id,
                    teacher_pk,
                    payload["announcement_type"],
                    payload["title"],
                    payload["content"],
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

    def classroom_announcement(self, announcement_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT announcement_id, classroom_pk AS classroom_id, announcement_type,
                       title, content, due_at, created_at, updated_at
                FROM classroom_announcements WHERE announcement_id=%s
            """,
                (announcement_id,),
            )
            return cursor.fetchone()

    def list_classroom_announcements(self, classroom_ids: list[int]) -> list[dict[str, Any]]:
        if not classroom_ids:
            return []
        placeholders = ",".join(["%s"] * len(classroom_ids))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT a.announcement_id, a.classroom_pk AS classroom_id, c.class_name,
                       publisher.teacher_id AS publisher_teacher_id,
                       publisher.teacher_name AS publisher_teacher_name,
                       a.announcement_type, a.title, a.content, a.due_at,
                       a.created_at, a.updated_at
                FROM classroom_announcements a
                JOIN classrooms c ON c.id=a.classroom_pk
                JOIN teachers publisher ON publisher.id=a.teacher_pk
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
        if not classroom or classroom.get("teacher_access_role") not in {"owner", "collaborator"}:
            return None
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            cursor.execute(
                """
                INSERT INTO classroom_exam_assignments
                    (assignment_id, classroom_pk, teacher_pk, paper_id, title, due_at, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE paper_id=IF(teacher_pk=VALUES(teacher_pk), VALUES(paper_id), paper_id), title=IF(teacher_pk=VALUES(teacher_pk), VALUES(title), title),
                    due_at=IF(teacher_pk=VALUES(teacher_pk), VALUES(due_at), due_at), status=IF(teacher_pk=VALUES(teacher_pk), VALUES(status), status), updated_at=UTC_TIMESTAMP()
                """,
                (
                    payload["assignment_id"],
                    classroom_id,
                    teacher_pk,
                    payload["paper_id"],
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

    def classroom_exam_assignment(self, assignment_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT assignment_id, classroom_pk AS classroom_id, paper_id, title,
                       due_at, status, created_at, updated_at
                FROM classroom_exam_assignments WHERE assignment_id=%s
            """,
                (assignment_id,),
            )
            return cursor.fetchone()

    def list_classroom_exam_assignments(self, classroom_ids: list[int]) -> list[dict[str, Any]]:
        if not classroom_ids:
            return []
        placeholders = ",".join(["%s"] * len(classroom_ids))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT a.assignment_id, a.classroom_pk AS classroom_id, c.class_name,
                       publisher.teacher_id AS publisher_teacher_id,
                       publisher.teacher_name AS publisher_teacher_name,
                       a.paper_id, a.title, a.due_at, a.status, a.created_at, a.updated_at
                FROM classroom_exam_assignments a
                JOIN classrooms c ON c.id=a.classroom_pk
                JOIN teachers publisher ON publisher.id=a.teacher_pk
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

    def save_teacher_lesson_version(self, payload: dict[str, Any]) -> None:
        context = payload["context"]
        teacher_id = context["teacher_id"]
        classroom_id = int(context["classroom_id"])
        if not self.teacher_classroom(teacher_id, classroom_id):
            raise ValueError("班级不存在或不属于当前教师")
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, teacher_id)
            if teacher_pk is None:
                raise ValueError("教师账号不存在")
            cursor.execute(
                """
                INSERT INTO teacher_lesson_plans
                    (lesson_plan_id, teacher_pk, classroom_pk, subject, topic,
                     lesson_type, current_version, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE current_version=VALUES(current_version),
                    status=VALUES(status), subject=VALUES(subject), topic=VALUES(topic),
                    lesson_type=VALUES(lesson_type), updated_at=UTC_TIMESTAMP()
                """,
                (
                    payload["lesson_plan_id"],
                    teacher_pk,
                    classroom_id,
                    context["subject"],
                    context["topic"],
                    context["lesson_type"],
                    payload["version"],
                    payload["status"],
                    _mysql_datetime(payload["created_at"]),
                ),
            )
            cursor.execute(
                """
                INSERT INTO teacher_lesson_plan_versions
                    (lesson_plan_id, version, status, payload_json, change_summary_json,
                     locked_components_json, created_at, approved_at, published_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status),
                    payload_json=VALUES(payload_json),
                    change_summary_json=VALUES(change_summary_json),
                    locked_components_json=VALUES(locked_components_json),
                    approved_at=VALUES(approved_at), published_at=VALUES(published_at)
                """,
                (
                    payload["lesson_plan_id"],
                    payload["version"],
                    payload["status"],
                    _json(payload),
                    _json(payload.get("change_summary") or []),
                    _json(payload.get("locked_component_ids") or []),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["approved_at"]) if payload.get("approved_at") else None,
                    _mysql_datetime(payload["published_at"])
                    if payload.get("published_at")
                    else None,
                ),
            )

    def load_teacher_lesson_versions(
        self, lesson_plan_id: str, teacher_id: str
    ) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.payload_json
                FROM teacher_lesson_plan_versions v
                JOIN teacher_lesson_plans p ON p.lesson_plan_id=v.lesson_plan_id
                JOIN teachers t ON t.id=p.teacher_pk
                WHERE v.lesson_plan_id=%s AND t.teacher_id=%s
                ORDER BY v.version
                """,
                (lesson_plan_id, teacher_id.lower()),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_teacher_lesson_plans(
        self, teacher_id: str, *, classroom_id: int | None = None
    ) -> list[dict[str, Any]]:
        filters = ["t.teacher_id=%s"]
        params: list[Any] = [teacher_id.lower()]
        if classroom_id is not None:
            filters.append("p.classroom_pk=%s")
            params.append(classroom_id)
        where_clause = " AND ".join(filters)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT v.payload_json
                FROM teacher_lesson_plans p
                JOIN teachers t ON t.id=p.teacher_pk
                JOIN teacher_lesson_plan_versions v
                  ON v.lesson_plan_id=p.lesson_plan_id AND v.version=p.current_version
                WHERE {where_clause}
                ORDER BY p.updated_at DESC
                LIMIT 200
                """,
                tuple(params),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_teacher_lesson_feedback(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            teacher_pk = self._teacher_pk(cursor, payload["teacher_id"])
            if teacher_pk is None:
                raise ValueError("教师账号不存在")
            cursor.execute(
                """
                INSERT INTO teacher_lesson_feedback
                    (feedback_id, lesson_plan_id, lesson_version, teacher_pk,
                     payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json)
                """,
                (
                    payload["feedback_id"],
                    payload["lesson_plan_id"],
                    payload["lesson_version"],
                    teacher_pk,
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def save_english_reading_progress(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_reading_progress
                    (student_pk, reading_id, session_id, status, elapsed_seconds,
                     score, payload_json, started_at, submitted_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE session_id=VALUES(session_id),
                    status=VALUES(status), elapsed_seconds=VALUES(elapsed_seconds),
                    score=VALUES(score), payload_json=VALUES(payload_json),
                    submitted_at=VALUES(submitted_at), updated_at=VALUES(updated_at)
                """,
                (
                    student_pk,
                    payload["reading_id"],
                    payload["session_id"],
                    payload["status"],
                    payload["elapsed_seconds"],
                    payload.get("score"),
                    _json(payload),
                    _mysql_datetime(payload["started_at"]),
                    _mysql_datetime(payload.get("submitted_at"))
                    if payload.get("submitted_at")
                    else None,
                    _mysql_datetime(payload["updated_at"]),
                ),
            )

    def load_english_reading_progress(
        self, student_id: str, reading_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM english_reading_progress p
                JOIN students s ON s.id=p.student_pk
                WHERE s.student_id=%s AND p.reading_id=%s
                """,
                (student_id.lower(), reading_id),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def list_english_reading_progress(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM english_reading_progress p
                JOIN students s ON s.id=p.student_pk
                WHERE s.student_id=%s ORDER BY p.updated_at DESC
                """,
                (student_id.lower(),),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_english_analysis(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_text_analyses
                    (analysis_id, student_pk, title, difficulty, payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json)
                """,
                (
                    payload["analysis_id"],
                    student_pk,
                    payload["title"],
                    payload["difficulty"]["absolute_score"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def list_english_analyses(self, student_id: str, *, limit: int) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.payload_json FROM english_text_analyses a
                JOIN students s ON s.id=a.student_pk
                WHERE s.student_id=%s ORDER BY a.created_at DESC LIMIT %s
                """,
                (student_id.lower(), max(1, min(limit, 50))),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_english_session(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_learning_sessions
                    (session_id, student_pk, mode, status, title, article_text,
                     difficulty, payload_json, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    payload["session_id"],
                    student_pk,
                    payload["mode"],
                    payload["status"],
                    payload["title"],
                    payload["article_text"],
                    payload["difficulty"]["absolute_score"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["updated_at"]),
                ),
            )

    def load_english_session(self, session_id: str, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.payload_json FROM english_learning_sessions e
                JOIN students s ON s.id=e.student_pk
                WHERE e.session_id=%s AND s.student_id=%s
                """,
                (session_id, student_id.lower()),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def list_english_sessions(self, student_id: str, *, limit: int) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.payload_json FROM english_learning_sessions e
                JOIN students s ON s.id=e.student_pk
                WHERE s.student_id=%s ORDER BY e.updated_at DESC LIMIT %s
                """,
                (student_id.lower(), max(1, min(limit, 50))),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_english_mastery_states(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.payload_json FROM english_mastery_states m
                JOIN students s ON s.id=m.student_pk
                WHERE s.student_id=%s ORDER BY m.mastery_probability ASC
                """,
                (student_id.lower(),),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_english_reviews(self, student_id: str, *, status: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.payload_json FROM english_review_items r
                JOIN students s ON s.id=r.student_pk
                WHERE s.student_id=%s AND r.status=%s
                ORDER BY r.due_at ASC LIMIT 100
                """,
                (student_id.lower(), status),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_english_attempt_bundle(
        self,
        session: dict[str, Any],
        attempt: dict[str, Any],
        states: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, session["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                UPDATE english_learning_sessions
                SET status=%s, payload_json=%s, updated_at=%s
                WHERE session_id=%s AND student_pk=%s
                """,
                (
                    session["status"],
                    _json(session),
                    _mysql_datetime(session["updated_at"]),
                    session["session_id"],
                    student_pk,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("英语训练会话不存在")
            cursor.execute(
                """
                INSERT INTO english_learning_attempts
                    (attempt_id, session_id, student_pk, score, payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    attempt["attempt_id"],
                    session["session_id"],
                    student_pk,
                    attempt["score"],
                    _json(attempt),
                    _mysql_datetime(attempt["created_at"]),
                ),
            )
            for state in states:
                cursor.execute(
                    """
                    INSERT INTO english_mastery_states
                        (student_pk, skill_id, mastery_probability, stability_days,
                         evidence_count, confidence, next_review_at, payload_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE mastery_probability=VALUES(mastery_probability),
                        stability_days=VALUES(stability_days), evidence_count=VALUES(evidence_count),
                        confidence=VALUES(confidence), next_review_at=VALUES(next_review_at),
                        payload_json=VALUES(payload_json), updated_at=UTC_TIMESTAMP()
                    """,
                    (
                        student_pk,
                        state["skill_id"],
                        state["mastery_probability"],
                        state["stability_days"],
                        state["evidence_count"],
                        state["confidence"],
                        _mysql_datetime(state["next_review_at"]),
                        _json(state),
                    ),
                )
            for review in reviews:
                cursor.execute(
                    """
                    INSERT INTO english_review_items
                        (review_id, student_pk, session_id, skill_id, status, due_at, payload_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        review["review_id"],
                        student_pk,
                        session["session_id"],
                        review["skill_id"],
                        review["status"],
                        _mysql_datetime(review["due_at"]),
                        _json(review),
                    ),
                )

    def complete_english_review(
        self, student_id: str, review_id: str, result: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.payload_json FROM english_review_items r
                JOIN students s ON s.id=r.student_pk
                WHERE r.review_id=%s AND s.student_id=%s AND r.status='pending'
                FOR UPDATE
                """,
                (review_id, student_id.lower()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            payload = _decoded(row["payload_json"])
            payload.update(
                {
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            )
            cursor.execute(
                """
                UPDATE english_review_items
                SET status='completed', completed_at=UTC_TIMESTAMP(), payload_json=%s
                WHERE review_id=%s
                """,
                (_json(payload), review_id),
            )
            return payload

    def save_english_learner_profile(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_learner_profiles
                    (student_pk, estimated_level, self_reported_level, preferred_mode,
                     evidence_count, payload_json)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE estimated_level=VALUES(estimated_level),
                    self_reported_level=VALUES(self_reported_level),
                    preferred_mode=VALUES(preferred_mode), evidence_count=VALUES(evidence_count),
                    payload_json=VALUES(payload_json), updated_at=UTC_TIMESTAMP()
                """,
                (
                    student_pk,
                    payload["estimated_level"],
                    payload["self_reported_level"],
                    payload["preferred_mode"],
                    payload.get("evidence_count", 0),
                    _json(payload),
                ),
            )

    def load_english_learner_profile(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM english_learner_profiles p
                JOIN students s ON s.id=p.student_pk WHERE s.student_id=%s
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_english_learning_task_bundle(
        self,
        event: dict[str, Any],
        vocabulary: list[dict[str, Any]],
        grammar: list[dict[str, Any]],
        writing: dict[str, Any] | None,
        speaking: dict[str, Any] | None,
        reviews: list[dict[str, Any]],
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, event["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_learning_events
                    (event_id, student_pk, task_type, response_mode, source_excerpt,
                     payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    event["event_id"],
                    student_pk,
                    event["task_type"],
                    event["response_mode"],
                    event["source_excerpt"],
                    _json(event),
                    _mysql_datetime(event["created_at"]),
                ),
            )
            for item in vocabulary:
                cursor.execute(
                    """
                    INSERT INTO english_vocabulary_items
                        (student_pk, word_key, word, mastery_score, status, contexts_seen,
                         next_review_at, payload_json, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE word=VALUES(word),
                        mastery_score=VALUES(mastery_score), status=VALUES(status),
                        contexts_seen=VALUES(contexts_seen),
                        next_review_at=VALUES(next_review_at), payload_json=VALUES(payload_json),
                        updated_at=VALUES(updated_at)
                    """,
                    (
                        student_pk,
                        item["word_key"],
                        item["word"],
                        item["mastery_score"],
                        item["status"],
                        item["contexts_seen"],
                        _mysql_datetime(item["next_review_at"]),
                        _json(item),
                        _mysql_datetime(item["updated_at"]),
                    ),
                )

            for item in grammar:
                cursor.execute(
                    """
                    INSERT INTO english_grammar_items
                        (student_pk, grammar_key, error_count, mastery_score, confidence,
                         next_review_at, payload_json, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE error_count=VALUES(error_count),
                        mastery_score=VALUES(mastery_score), confidence=VALUES(confidence),
                        next_review_at=VALUES(next_review_at), payload_json=VALUES(payload_json),
                        updated_at=VALUES(updated_at)
                    """,
                    (
                        student_pk,
                        item["grammar_key"],
                        item["error_count"],
                        item["mastery_score"],
                        item["confidence"],
                        _mysql_datetime(item["next_review_at"]),
                        _json(item),
                        _mysql_datetime(item["updated_at"]),
                    ),
                )
            if writing:
                cursor.execute(
                    """
                    INSERT INTO english_writing_submissions
                        (submission_id, event_id, student_pk, revision_level, source_text,
                         revised_text, payload_json, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        writing["submission_id"],
                        event["event_id"],
                        student_pk,
                        writing["revision_level"],
                        writing["source_text"],
                        writing["revised_text"],
                        _json(writing),
                        _mysql_datetime(writing["created_at"]),
                    ),
                )
            if speaking:
                cursor.execute(
                    """
                    INSERT INTO english_speaking_sessions
                        (speaking_session_id, event_id, student_pk, scenario, feedback_mode,
                         pronunciation_scored, payload_json, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        speaking["speaking_session_id"],
                        event["event_id"],
                        student_pk,
                        speaking["scenario"],
                        speaking["feedback_mode"],
                        0,
                        _json(speaking),
                        _mysql_datetime(speaking["created_at"]),
                    ),
                )
            for review in reviews:
                cursor.execute(
                    """
                    INSERT INTO english_review_items
                        (review_id, student_pk, session_id, skill_id, status, due_at, payload_json)
                    VALUES (%s,%s,NULL,%s,%s,%s,%s)
                    """,
                    (
                        review["review_id"],
                        student_pk,
                        review["skill_id"],
                        review["status"],
                        _mysql_datetime(review["due_at"]),
                        _json(review),
                    ),
                )

    def save_english_national_exam_attempt(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO english_national_exam_attempts
                    (attempt_id, student_pk, section, score, max_score, evidence_count,
                     payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    payload["attempt_id"],
                    student_pk,
                    payload["section"],
                    payload.get("score"),
                    payload.get("max_score"),
                    payload.get("evidence_count", 0),
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def load_english_learning_records(self, student_id: str, *, limit: int = 30) -> dict[str, Any]:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return {"events": [], "vocabulary": [], "grammar": []}
            result: dict[str, Any] = {}
            for key, table, order in (
                ("events", "english_learning_events", "created_at"),
                ("vocabulary", "english_vocabulary_items", "updated_at"),
                ("grammar", "english_grammar_items", "updated_at"),
            ):
                cursor.execute(
                    f"SELECT payload_json FROM {table} WHERE student_pk=%s "
                    f"ORDER BY {order} DESC LIMIT %s",
                    (student_pk, limit),
                )
                result[key] = [_decoded(row["payload_json"]) for row in cursor.fetchall()]
            return result

    def delete_english_learning_record(
        self, student_id: str, record_type: str, record_id: str
    ) -> bool:
        table_and_column = {
            "event": ("english_learning_events", "event_id"),
            "vocabulary": ("english_vocabulary_items", "word_key"),
        }.get(record_type)
        if not table_and_column:
            return False
        table, column = table_and_column
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return False
            cursor.execute(
                f"DELETE FROM {table} WHERE student_pk=%s AND {column}=%s",
                (student_pk, record_id.lower() if record_type == "vocabulary" else record_id),
            )
            return cursor.rowcount == 1

    def save_programming_profile(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO programming_learner_profiles
                    (student_pk, learning_mode, target_direction, weekly_minutes,
                     exam_period, profile_version, payload_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE learning_mode=VALUES(learning_mode),
                    target_direction=VALUES(target_direction),
                    weekly_minutes=VALUES(weekly_minutes), exam_period=VALUES(exam_period),
                    profile_version=VALUES(profile_version), payload_json=VALUES(payload_json),
                    updated_at=UTC_TIMESTAMP()
                """,
                (
                    student_pk,
                    payload["learning_mode"],
                    payload["target_direction"],
                    payload["effective_weekly_minutes"],
                    payload["exam_period"],
                    payload["profile_version"],
                    _json(payload),
                ),
            )

    def load_programming_profile(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM programming_learner_profiles p
                JOIN students s ON s.id=p.student_pk WHERE s.student_id=%s
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_programming_record(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO programming_learning_records
                    (record_id, student_pk, record_type, status, payload_json,
                     created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    payload["record_id"],
                    student_pk,
                    payload["record_type"],
                    payload["status"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["updated_at"]),
                ),
            )

    def load_programming_record(self, record_id: str, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.payload_json FROM programming_learning_records r
                JOIN students s ON s.id=r.student_pk
                WHERE r.record_id=%s AND s.student_id=%s
                """,
                (record_id, student_id.lower()),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def list_programming_records(
        self,
        student_id: str,
        *,
        record_type: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return []
            sql = "SELECT payload_json FROM programming_learning_records WHERE student_pk=%s"
            params: list[Any] = [student_pk]
            if record_type:
                sql += " AND record_type=%s"
                params.append(record_type)
            sql += " ORDER BY updated_at DESC LIMIT %s"
            params.append(limit)
            cursor.execute(sql, tuple(params))
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def save_programming_evidence_bundle(
        self, event: dict[str, Any], skill_state: dict[str, Any]
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, event["student_id"])
            if student_pk is None:
                raise ValueError("学生账号不存在")
            cursor.execute(
                """
                INSERT INTO programming_learning_events
                    (event_id, student_pk, event_type, skill_id, score,
                     hint_level, payload_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    event["event_id"],
                    student_pk,
                    event["event_type"],
                    event["skill_id"],
                    event["score"],
                    event["hint_level"],
                    _json(event),
                    _mysql_datetime(event["created_at"]),
                ),
            )
            cursor.execute(
                """
                INSERT INTO programming_skill_states
                    (student_pk, skill_id, mastery, level, confidence,
                     evidence_count, payload_json, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE mastery=VALUES(mastery), level=VALUES(level),
                    confidence=VALUES(confidence), evidence_count=VALUES(evidence_count),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    student_pk,
                    skill_state["skill_id"],
                    skill_state["mastery"],
                    skill_state["level"],
                    skill_state["confidence"],
                    skill_state["evidence_count"],
                    _json(skill_state),
                    _mysql_datetime(skill_state["updated_at"]),
                ),
            )

    def list_programming_events(self, student_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return []
            cursor.execute(
                """
                SELECT payload_json FROM programming_learning_events
                WHERE student_pk=%s ORDER BY created_at DESC LIMIT %s
                """,
                (student_pk, limit),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_programming_skill_states(self, student_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, student_id)
            if student_pk is None:
                return []
            cursor.execute(
                """
                SELECT payload_json FROM programming_skill_states
                WHERE student_pk=%s ORDER BY mastery DESC, skill_id
                """,
                (student_pk,),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def sync_career_catalog(
        self,
        jobs: list[dict[str, Any]],
        projects: list[dict[str, Any]],
        questions: list[dict[str, Any]],
    ) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            for item in jobs:
                cursor.execute(
                    """
                    INSERT INTO career_job_positions
                        (job_id, name, status, payload_json)
                    VALUES (%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), status=VALUES(status),
                        payload_json=VALUES(payload_json), updated_at=UTC_TIMESTAMP()
                    """,
                    (item["job_id"], item["name"], item.get("status", "active"), _json(item)),
                )
            for item in projects:
                cursor.execute(
                    """
                    INSERT INTO career_project_templates
                        (project_id, target_job_id, title, difficulty, status, payload_json)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE title=VALUES(title),
                        difficulty=VALUES(difficulty), status=VALUES(status),
                        payload_json=VALUES(payload_json), updated_at=UTC_TIMESTAMP()
                    """,
                    (
                        item["project_id"],
                        item["target_job_id"],
                        item["title"],
                        item["difficulty"],
                        item.get("status", "active"),
                        _json(item),
                    ),
                )
            for item in questions:
                cursor.execute(
                    """
                    INSERT INTO career_coding_questions
                        (question_id, target_job_id, language, category, difficulty,
                         source_type, license_name, review_status, payload_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE category=VALUES(category),
                        difficulty=VALUES(difficulty), review_status=VALUES(review_status),
                        payload_json=VALUES(payload_json), updated_at=UTC_TIMESTAMP()
                    """,
                    (
                        item["question_id"],
                        item["target_job_id"],
                        item["language"],
                        item["category"],
                        item["difficulty"],
                        item["source_type"],
                        item["license"],
                        item["review_status"],
                        _json(item),
                    ),
                )

    def list_career_jobs(self) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload_json FROM career_job_positions "
                "WHERE status='active' ORDER BY job_id"
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_career_projects(self, target_job_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload_json FROM career_project_templates
                WHERE target_job_id=%s AND status='active'
                ORDER BY difficulty, project_id
                """,
                (target_job_id,),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def list_career_questions(self, target_job_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload_json FROM career_coding_questions
                WHERE target_job_id=%s AND review_status='approved'
                ORDER BY difficulty, question_id
                """,
                (target_job_id,),
            )
            return [_decoded(row["payload_json"]) for row in cursor.fetchall()]

    def load_unified_student_profile(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.payload_json FROM unified_student_profiles p
                JOIN students s ON s.id=p.student_pk
                WHERE s.student_id=%s
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_unified_student_profile(
        self,
        payload: dict[str, Any],
        *,
        expected_version: int | None = None,
    ) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return False
            values = (
                payload["profile_version"],
                _json(payload),
                _mysql_datetime(payload["updated_at"]),
            )
            if expected_version is None:
                cursor.execute(
                    """
                    INSERT INTO unified_student_profiles
                        (student_pk, profile_version, payload_json, updated_at)
                    VALUES (%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE profile_version=VALUES(profile_version),
                        payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                    """,
                    (student_pk, *values),
                )
                return True
            if expected_version == 0:
                cursor.execute(
                    """
                    INSERT IGNORE INTO unified_student_profiles
                        (student_pk, profile_version, payload_json, updated_at)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (student_pk, *values),
                )
                return cursor.rowcount == 1
            cursor.execute(
                """
                UPDATE unified_student_profiles
                SET profile_version=%s, payload_json=%s, updated_at=%s
                WHERE student_pk=%s AND profile_version=%s
                """,
                (*values, student_pk, expected_version),
            )
            return cursor.rowcount == 1

    def save_unified_learning_event(self, payload: dict[str, Any]) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return False
            cursor.execute(
                """
                INSERT IGNORE INTO unified_learning_events
                    (event_id, student_pk, event_type, agent_role, subject,
                     knowledge_point, difficulty, score, confidence, session_id,
                     trace_id, metadata_json, occurred_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    payload["event_id"],
                    student_pk,
                    payload["event_type"],
                    payload["agent"],
                    payload.get("subject"),
                    payload.get("knowledge_point"),
                    payload.get("difficulty"),
                    payload.get("score"),
                    payload["confidence"],
                    payload.get("session_id"),
                    payload.get("trace_id"),
                    _json(payload.get("metadata", {})),
                    _mysql_datetime(payload["occurred_at"]),
                ),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                cursor.execute(
                    """
                    INSERT IGNORE INTO learning_event_outbox
                        (outbox_id, event_id, event_type, payload_json, status)
                    VALUES (%s,%s,%s,%s,'pending')
                    """,
                    (
                        f"outbox_{payload['event_id']}",
                        payload["event_id"],
                        payload["event_type"],
                        _json(payload),
                    ),
                )
            return inserted

    def list_unified_learning_events(
        self,
        student_id: str,
        *,
        limit: int = 100,
        knowledge_point: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT e.event_id, e.event_type, e.agent_role, e.subject,
                       e.knowledge_point, e.difficulty, e.score, e.confidence,
                       e.session_id, e.trace_id, e.metadata_json, e.occurred_at
                FROM unified_learning_events e
                JOIN students s ON s.id=e.student_pk
                WHERE s.student_id=%s
            """
            params: list[Any] = [student_id.lower()]
            if knowledge_point:
                sql += " AND e.knowledge_point=%s"
                params.append(knowledge_point)
            sql += " ORDER BY e.occurred_at DESC, e.event_id DESC LIMIT %s"
            params.append(max(1, min(limit, 500)))
            cursor.execute(sql, tuple(params))
            return [
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "user_id": student_id.lower(),
                    "agent": row["agent_role"],
                    "subject": row["subject"],
                    "knowledge_point": row["knowledge_point"],
                    "difficulty": (
                        float(row["difficulty"]) if row["difficulty"] is not None else None
                    ),
                    "score": float(row["score"]) if row["score"] is not None else None,
                    "confidence": float(row["confidence"]),
                    "session_id": row["session_id"],
                    "trace_id": row["trace_id"],
                    "metadata": _decoded(row["metadata_json"]),
                    "occurred_at": row["occurred_at"],
                }
                for row in cursor.fetchall()
            ]

    def save_agent_orchestration_run(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO agent_orchestration_runs
                    (run_id, student_pk, session_id, trace_id, status, routing_json,
                     result_json, payload_json, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status),
                    routing_json=VALUES(routing_json), result_json=VALUES(result_json),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    payload["run_id"],
                    student_pk,
                    payload.get("session_id"),
                    payload["trace_id"],
                    payload["status"],
                    _json(payload.get("routing")) if payload.get("routing") else None,
                    _json(payload.get("result")) if payload.get("result") else None,
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["updated_at"]),
                ),
            )

    def load_agent_orchestration_run(self, run_id: str, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.payload_json FROM agent_orchestration_runs r
                JOIN students s ON s.id=r.student_pk
                WHERE r.run_id=%s AND s.student_id=%s
                """,
                (run_id, student_id.lower()),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_agent_execution_trace(self, payload: dict[str, Any]) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return
            cursor.execute(
                """
                INSERT INTO agent_execution_traces
                    (trace_record_id, request_id, trace_id, student_pk, session_id,
                     agent_role, node_name, model_name, tool_name, latency_ms, status,
                     error_message, handoff_json, event_count, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE latency_ms=VALUES(latency_ms),
                    status=VALUES(status), error_message=VALUES(error_message),
                    handoff_json=VALUES(handoff_json), event_count=VALUES(event_count)
                """,
                (
                    payload["trace_record_id"],
                    payload["request_id"],
                    payload["trace_id"],
                    student_pk,
                    payload.get("session_id"),
                    payload["agent"],
                    payload.get("node", "agent_graph"),
                    payload.get("model"),
                    payload.get("tool"),
                    payload["latency_ms"],
                    payload["status"],
                    payload.get("error"),
                    _json(payload.get("handoff")) if payload.get("handoff") else None,
                    payload.get("event_count", 0),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def mark_learning_event_outbox_processed(self, event_id: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE learning_event_outbox
                SET status='processed', attempts=attempts+1,
                    processed_at=CURRENT_TIMESTAMP, last_error=NULL
                WHERE event_id=%s AND status<>'processed'
                """,
                (event_id,),
            )

    def mark_learning_event_outbox_failed(self, event_id: str, error: str) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE learning_event_outbox
                SET status=IF(attempts >= 4, 'dead_letter', 'pending'),
                    attempts=attempts+1, last_error=%s,
                    available_at=DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 30 SECOND)
                WHERE event_id=%s AND status<>'processed'
                """,
                (error[:4000], event_id),
            )

    def list_pending_learning_event_outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT outbox_id, event_id, event_type, payload_json, status,
                       attempts, last_error, available_at, created_at
                FROM learning_event_outbox
                WHERE status='pending' AND available_at<=CURRENT_TIMESTAMP
                ORDER BY created_at, outbox_id
                LIMIT %s
                """,
                (max(1, min(limit, 500)),),
            )
            return [
                {**row, "payload": _decoded(row.pop("payload_json"))} for row in cursor.fetchall()
            ]

    def save_actor_orchestration_run(self, payload: dict[str, Any]) -> None:
        actor_type = str(payload.get("actor_type") or "system")
        actor_id = str(payload["user_id"]).split(":", 1)[-1]
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO actor_orchestration_runs
                    (run_id, actor_type, actor_id, session_id, trace_id, status,
                     payload_json, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE status=VALUES(status),
                    payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                """,
                (
                    payload["run_id"],
                    actor_type,
                    actor_id,
                    payload.get("session_id"),
                    payload["trace_id"],
                    payload["status"],
                    _json(payload),
                    _mysql_datetime(payload["created_at"]),
                    _mysql_datetime(payload["updated_at"]),
                ),
            )

    def load_actor_orchestration_run(
        self, run_id: str, actor_type: str, actor_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload_json FROM actor_orchestration_runs
                WHERE run_id=%s AND actor_type=%s AND actor_id=%s
                """,
                (run_id, actor_type, actor_id),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_actor_execution_trace(self, payload: dict[str, Any]) -> None:
        actor_type = str(payload.get("actor_type") or "system")
        actor_id = str(payload["user_id"]).split(":", 1)[-1]
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO actor_execution_traces
                    (trace_record_id, request_id, trace_id, actor_type, actor_id,
                     session_id, agent_role, model_name, model_capability, latency_ms,
                     status, error_message, handoff_json, event_count, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE latency_ms=VALUES(latency_ms),
                    status=VALUES(status), error_message=VALUES(error_message),
                    handoff_json=VALUES(handoff_json), event_count=VALUES(event_count)
                """,
                (
                    payload["trace_record_id"],
                    payload["request_id"],
                    payload["trace_id"],
                    actor_type,
                    actor_id,
                    payload.get("session_id"),
                    payload["agent"],
                    payload.get("model"),
                    payload.get("model_capability"),
                    payload["latency_ms"],
                    payload["status"],
                    payload.get("error"),
                    _json(payload.get("handoff")) if payload.get("handoff") else None,
                    payload.get("event_count", 0),
                    _mysql_datetime(payload["created_at"]),
                ),
            )

    def ensure_collaboration_session(self, payload: dict[str, Any]) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return False
            cursor.execute(
                """
                INSERT IGNORE INTO collaboration_sessions
                    (session_id, student_pk, interaction_count, context_json,
                     started_at, last_active_at)
                VALUES (%s,%s,0,%s,%s,%s)
                """,
                (
                    payload["session_id"],
                    student_pk,
                    _json(payload.get("context", {})),
                    _mysql_datetime(payload["occurred_at"]),
                    _mysql_datetime(payload["occurred_at"]),
                ),
            )
            inserted = cursor.rowcount == 1
            cursor.execute(
                """
                UPDATE collaboration_sessions
                SET context_json=%s, last_active_at=%s
                WHERE session_id=%s AND student_pk=%s
                """,
                (
                    _json(payload.get("context", {})),
                    _mysql_datetime(payload["occurred_at"]),
                    payload["session_id"],
                    student_pk,
                ),
            )
            return inserted

    def save_collaboration_message(self, payload: dict[str, Any]) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return False
            cursor.execute(
                """
                INSERT IGNORE INTO collaboration_messages
                    (message_id, session_id, student_pk, run_id, role, subject,
                     content, metadata_json, created_at)
                SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s
                FROM collaboration_sessions cs
                WHERE cs.session_id=%s AND cs.student_pk=%s
                """,
                (
                    payload["message_id"],
                    payload["session_id"],
                    student_pk,
                    payload.get("run_id"),
                    payload["role"],
                    payload.get("subject"),
                    payload["content"],
                    _json(payload.get("metadata", {})),
                    _mysql_datetime(payload["created_at"]),
                    payload["session_id"],
                    student_pk,
                ),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                cursor.execute(
                    """
                    UPDATE collaboration_sessions
                    SET interaction_count=interaction_count+1, last_active_at=%s
                    WHERE session_id=%s AND student_pk=%s
                    """,
                    (
                        _mysql_datetime(payload["created_at"]),
                        payload["session_id"],
                        student_pk,
                    ),
                )
            return inserted

    def load_collaboration_memory(self, student_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.payload_json FROM collaboration_memories m
                JOIN students s ON s.id=m.student_pk
                WHERE s.student_id=%s
                """,
                (student_id.lower(),),
            )
            row = cursor.fetchone()
            return _decoded(row["payload_json"]) if row else None

    def save_collaboration_memory(self, payload: dict[str, Any]) -> bool:
        with self.connection() as connection, connection.cursor() as cursor:
            student_pk = self._student_pk(cursor, payload["user_id"])
            if student_pk is None:
                return False
            explicit = {
                "declared_goals": payload.get("declared_goals", []),
                "declared_preferences": payload.get("declared_preferences", []),
                "declared_foundations": payload.get("declared_foundations", []),
                "subject_focus_counts": payload.get("subject_focus_counts", {}),
            }
            cursor.execute(
                """
                INSERT INTO collaboration_memories
                    (student_pk, memory_version, personalization_mode, session_count,
                     interaction_count, explicit_profile_json, source_summary_json,
                     payload_json, first_seen_at, last_seen_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    memory_version=VALUES(memory_version),
                    personalization_mode=VALUES(personalization_mode),
                    session_count=VALUES(session_count),
                    interaction_count=VALUES(interaction_count),
                    explicit_profile_json=VALUES(explicit_profile_json),
                    source_summary_json=VALUES(source_summary_json),
                    payload_json=VALUES(payload_json),
                    last_seen_at=VALUES(last_seen_at)
                """,
                (
                    student_pk,
                    payload["memory_version"],
                    payload["personalization_mode"],
                    payload["session_count"],
                    payload["interaction_count"],
                    _json(explicit),
                    _json(payload.get("source_summary", {})),
                    _json(payload),
                    _mysql_datetime(payload["first_seen_at"]),
                    _mysql_datetime(payload["last_seen_at"]),
                ),
            )
            return True

    def list_collaboration_messages(
        self, student_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.message_id, m.session_id, m.run_id, m.role, m.subject,
                       m.content, m.metadata_json, m.created_at
                FROM collaboration_messages m
                JOIN students s ON s.id=m.student_pk
                WHERE s.student_id=%s
                ORDER BY m.created_at DESC, m.message_id DESC
                LIMIT %s
                """,
                (student_id.lower(), max(1, min(limit, 100))),
            )
            rows = list(cursor.fetchall())
            return [
                {
                    "message_id": row["message_id"],
                    "session_id": row["session_id"],
                    "run_id": row["run_id"],
                    "role": row["role"],
                    "subject": row["subject"],
                    "content": row["content"],
                    "metadata": _decoded(row["metadata_json"]),
                    "created_at": row["created_at"],
                }
                for row in reversed(rows)
            ]
