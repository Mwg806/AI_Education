-- Data-preserving rollback guidance:
-- 1. Set every class back to direct student joining.
-- 2. Keep request history unless an operator explicitly approves dropping it.
UPDATE classrooms SET student_join_policy='open';
-- Optional destructive cleanup, intentionally not executed automatically:
-- DROP TABLE classroom_join_requests;
