-- Safe rollback procedure (no automatic destructive SQL).
-- 1. Switch application back to commit e371c7c1 or the recorded pre-migration commit.
-- 2. Stop writes and verify learning_event_outbox has no pending rows.
-- 3. Keep the additive tables in place; the previous application ignores them.
-- 4. Only after backup and explicit approval may an operator archive/drop:
--    actor_execution_traces, actor_orchestration_runs, learning_event_outbox.
-- schema_migrations should remain as the immutable migration ledger.
SELECT status, COUNT(*) AS row_count
FROM learning_event_outbox
GROUP BY status;
