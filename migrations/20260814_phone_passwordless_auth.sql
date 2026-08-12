ALTER TABLE students ADD COLUMN phone_e164 VARCHAR(16) CHARACTER SET ascii NULL;
ALTER TABLE teachers ADD COLUMN phone_e164 VARCHAR(16) CHARACTER SET ascii NULL;
CREATE INDEX idx_students_phone ON students (phone_e164, is_active);
CREATE INDEX idx_teachers_phone ON teachers (phone_e164, is_active);
ALTER TABLE students MODIFY COLUMN password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL;
ALTER TABLE teachers MODIFY COLUMN password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL;
UPDATE students SET password_hash=NULL;
UPDATE teachers SET password_hash=NULL;
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
