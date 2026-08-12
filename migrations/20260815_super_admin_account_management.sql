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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
