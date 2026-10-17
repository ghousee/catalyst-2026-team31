-- 007_person_level.sql — veterans (senior, own and sign knowledge, suggested as "who to call") vs emerging veterans
-- (juniors in training: a few expert_in links, a learning map, never suggested as the expert). Idempotent.
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).
ALTER TABLE person ADD COLUMN IF NOT EXISTS level TEXT NOT NULL DEFAULT 'veteran';
DO $$ BEGIN
  ALTER TABLE person ADD CONSTRAINT person_level_check CHECK (level IN ('veteran', 'emerging'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
