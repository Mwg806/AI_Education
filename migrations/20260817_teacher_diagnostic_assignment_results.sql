-- Link diagnostic sessions to the exact teacher assignment that launched them.
SET @add_exam_assignment_id = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='exam_diagnostic_sessions'
       AND COLUMN_NAME='assignment_id')=0,
    'ALTER TABLE exam_diagnostic_sessions ADD COLUMN assignment_id VARCHAR(96) CHARACTER SET ascii NULL AFTER student_pk',
    'SELECT 1'
);
PREPARE stmt FROM @add_exam_assignment_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_exam_assignment_index = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
     WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='exam_diagnostic_sessions'
       AND INDEX_NAME='idx_exam_assignment_student')=0,
    'ALTER TABLE exam_diagnostic_sessions ADD KEY idx_exam_assignment_student (assignment_id, student_pk, updated_at)',
    'SELECT 1'
);
PREPARE stmt FROM @add_exam_assignment_index;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_exam_assignment_fk = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
     WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='exam_diagnostic_sessions'
       AND CONSTRAINT_NAME='fk_exam_assignment')=0,
    'ALTER TABLE exam_diagnostic_sessions ADD CONSTRAINT fk_exam_assignment FOREIGN KEY (assignment_id) REFERENCES classroom_exam_assignments(assignment_id) ON DELETE SET NULL',
    'SELECT 1'
);
PREPARE stmt FROM @add_exam_assignment_fk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
