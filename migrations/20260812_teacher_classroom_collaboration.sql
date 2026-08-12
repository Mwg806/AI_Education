-- Allow multiple teachers to collaborate in one class while preserving its owner.

CREATE TABLE IF NOT EXISTS classroom_teachers (
    classroom_pk BIGINT UNSIGNED NOT NULL,
    teacher_pk BIGINT UNSIGNED NOT NULL,
    role VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'collaborator',
    status VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'active',
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (classroom_pk, teacher_pk),
    KEY idx_classroom_teachers_teacher (teacher_pk, status, joined_at),
    CONSTRAINT fk_classroom_teachers_classroom FOREIGN KEY (classroom_pk)
        REFERENCES classrooms(id) ON DELETE CASCADE,
    CONSTRAINT fk_classroom_teachers_teacher FOREIGN KEY (teacher_pk)
        REFERENCES teachers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO classroom_teachers (classroom_pk, teacher_pk, role, status, joined_at)
SELECT id, teacher_pk, 'owner', 'active', created_at
FROM classrooms
ON DUPLICATE KEY UPDATE role='owner', status='active', updated_at=UTC_TIMESTAMP();
