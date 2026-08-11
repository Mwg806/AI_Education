-- Persistent collaboration memory for cross-login personalization; additive-only.

CREATE TABLE IF NOT EXISTS collaboration_memories (
    student_pk BIGINT UNSIGNED NOT NULL,
    memory_version INT UNSIGNED NOT NULL DEFAULT 1,
    personalization_mode VARCHAR(40) CHARACTER SET ascii NOT NULL,
    session_count INT UNSIGNED NOT NULL DEFAULT 0,
    interaction_count INT UNSIGNED NOT NULL DEFAULT 0,
    explicit_profile_json JSON NOT NULL,
    source_summary_json JSON NOT NULL,
    payload_json JSON NOT NULL,
    first_seen_at DATETIME NOT NULL,
    last_seen_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (student_pk),
    KEY idx_collaboration_memory_mode (personalization_mode, last_seen_at),
    CONSTRAINT fk_collaboration_memory_student FOREIGN KEY (student_pk)
        REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collaboration_sessions (
    session_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    student_pk BIGINT UNSIGNED NOT NULL,
    interaction_count INT UNSIGNED NOT NULL DEFAULT 0,
    context_json JSON NOT NULL,
    started_at DATETIME NOT NULL,
    last_active_at DATETIME NOT NULL,
    PRIMARY KEY (session_id),
    KEY idx_collaboration_session_student (student_pk, last_active_at),
    CONSTRAINT fk_collaboration_session_student FOREIGN KEY (student_pk)
        REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collaboration_messages (
    message_id VARCHAR(112) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    session_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    student_pk BIGINT UNSIGNED NOT NULL,
    run_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NULL,
    role VARCHAR(24) CHARACTER SET ascii NOT NULL,
    subject VARCHAR(64) CHARACTER SET ascii NULL,
    content TEXT NOT NULL,
    metadata_json JSON NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (message_id),
    KEY idx_collaboration_message_student (student_pk, created_at),
    KEY idx_collaboration_message_session (session_id, created_at),
    KEY idx_collaboration_message_run (run_id),
    CONSTRAINT fk_collaboration_message_student FOREIGN KEY (student_pk)
        REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_collaboration_message_session FOREIGN KEY (session_id)
        REFERENCES collaboration_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
