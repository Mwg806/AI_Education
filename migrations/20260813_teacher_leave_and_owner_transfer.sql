-- Add approval-based collaborator leave requests.
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
