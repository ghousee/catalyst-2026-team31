-- 008_knowledge_check.sql — what an emerging veteran has shown they know (idempotent).
-- A knowledge check turns a signed veteran note into "what would you do?"; Qwen grades the answer against the note.
-- A pass also adds a `knows` edge (user -> note, created_by 'check') so Synapse shows it.
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).
CREATE TABLE IF NOT EXISTS check_result (
  id        BIGSERIAL PRIMARY KEY,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id   TEXT NOT NULL,
  note_id   TEXT NOT NULL REFERENCES heuristic(id),
  answer    TEXT NOT NULL,
  score     INT  NOT NULL CHECK (score BETWEEN 0 AND 2),   -- 0 missed, 1 partly, 2 got it
  feedback  TEXT
);
CREATE INDEX IF NOT EXISTS check_result_user ON check_result (user_id);

-- allow the new `knows` relation (user -> note they answered correctly)
ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_rel_check;
ALTER TABLE edge ADD CONSTRAINT edge_rel_check CHECK (rel IN (
  'about', 'symptom_of', 'fixed_by', 'precedes', 'extends', 'contradicts', 'supersedes', 'disagrees_with',
  'expert_in', 'depends_on', 'diagnosed_by', 'mentions', 'applies_to', 'knows'));
