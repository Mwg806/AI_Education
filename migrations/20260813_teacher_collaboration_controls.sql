-- Complete the owner/collaborator lifecycle and optional join approval policy.
SET @add_join_policy = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='classrooms' AND COLUMN_NAME='join_policy')=0, 'ALTER TABLE classrooms ADD COLUMN join_policy VARCHAR(16) CHARACTER SET ascii NOT NULL DEFAULT 'open'', 'SELECT 1');
PREPARE stmt FROM @add_join_policy; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @add_reviewed_at = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='classroom_teachers' AND COLUMN_NAME='reviewed_at')=0, 'ALTER TABLE classroom_teachers ADD COLUMN reviewed_at DATETIME NULL AFTER joined_at', 'SELECT 1');
PREPARE stmt FROM @add_reviewed_at; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @add_last_action_at = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='classroom_teachers' AND COLUMN_NAME='last_action_at')=0, 'ALTER TABLE classroom_teachers ADD COLUMN last_action_at DATETIME NULL AFTER updated_at', 'SELECT 1');
PREPARE stmt FROM @add_last_action_at; EXECUTE stmt; DEALLOCATE PREPARE stmt;
ALTER TABLE classroom_teachers MODIFY role VARCHAR(24) CHARACTER SET ascii NOT NULL DEFAULT 'collaborator';
UPDATE classroom_teachers
SET role='collaborator'
WHERE role IN ('manager', 'publisher', 'viewer');
