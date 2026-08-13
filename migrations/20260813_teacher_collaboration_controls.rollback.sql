-- Data-preserving rollback: retain membership rows and restore open joining.
UPDATE classrooms SET join_policy='open';
UPDATE classroom_teachers SET role='publisher' WHERE role IN ('manager','viewer');
