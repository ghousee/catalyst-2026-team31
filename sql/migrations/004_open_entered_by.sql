-- 004_open_entered_by.sql — anyone may type a note for a veteran ("Raj told me"), not only person rows (idempotent).
-- entered_by is now any user id (a junior's login); the owner (a person row) still signs.
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).
ALTER TABLE heuristic DROP CONSTRAINT IF EXISTS heuristic_entered_by_fkey;
