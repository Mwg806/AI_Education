-- Move unanswered legacy teacher assignments from each subject's platform half
-- (01-05) to the matching teacher-only half (06-10).
UPDATE classroom_exam_assignments AS assignment
LEFT JOIN exam_diagnostic_sessions AS session
  ON session.assignment_id = assignment.assignment_id
SET assignment.paper_id = CONCAT(
  LEFT(assignment.paper_id, LENGTH(assignment.paper_id) - 2),
  LPAD(CAST(RIGHT(assignment.paper_id, 2) AS UNSIGNED) + 5, 2, '0')
)
WHERE assignment.status <> 'archived'
  AND session.session_id IS NULL
  AND assignment.paper_id REGEXP '^gaokao_diag_[a-z_]+_0[1-5]$';

-- Tasks with existing sessions remain untouched so their questions, scores,
-- evidence records and learning analysis keep referring to the original paper.
