-- Multi-Agent remediation V1: additive-only migration.
-- Rollback is intentionally data-preserving: stop writers, archive these tables, then DROP only after approval.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    checksum CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
