-- Add per-class student join policy and owner-reviewed student join requests.
SET @add_student_join_policy = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='classrooms'
       AND COLUMN_NAME='student_join_policy')=0,
    'ALTER TABLE classrooms ADD COLUMN student_join_policy VARCHAR(16) CHARACTER SET ascii NOT NULL DEFAULT ''open'' AFTER join_policy',
    'SELECT 1'
);
PREPARE stmt FROM @add_student_join_policy;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
