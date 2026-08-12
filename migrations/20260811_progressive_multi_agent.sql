-- Additive migration for progressive multi-agent orchestration.
-- Existing domain tables and APIs remain unchanged.

CREATE TABLE IF NOT EXISTS unified_student_profiles (
    student_pk BIGINT UNSIGNED NOT NULL,
    profile_version INT UNSIGNED NOT NULL DEFAULT 1,
    payload_json JSON NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (student_pk),
    CONSTRAINT fk_unified_profile_student FOREIGN KEY (student_pk)
        REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
