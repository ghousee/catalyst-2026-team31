-- 003_knowledge_capture.sql — veterans add knowledge, documents are re-uploaded (idempotent; safe to re-run).
-- Apply to a live DB without wiping it:  python -m backend.graph.migrate   (or psql -f this file)
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).

-- who typed a note (the owner signs it; a colleague may enter it on their behalf)
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS entered_by   TEXT REFERENCES person(id);
-- the manual section this note is linked to changed or was removed after the note was signed
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;
-- when POST /documents last (re)loaded the chunk
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS loaded_at    TIMESTAMPTZ;
