-- Data-preserving rollback: disable collaborator access without deleting memberships.
UPDATE classroom_teachers
SET status='inactive', updated_at=UTC_TIMESTAMP()
WHERE role='collaborator';

-- Owner rows and the table are intentionally retained so rollback is recoverable.
