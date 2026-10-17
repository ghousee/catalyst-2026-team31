-- 002_knowledge_graph.sql — knowledge-graph + veteran-knowledge layer (idempotent; safe to re-run).
-- Apply to a live DB without wiping it:  python -m backend.graph.migrate   (or psql -f this file)
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).

-- ---------- entity: more kinds, free-form props ----------
ALTER TABLE entity DROP CONSTRAINT IF EXISTS entity_kind_check;
ALTER TABLE entity ADD CONSTRAINT entity_kind_check CHECK (kind IN (
  'system','version','component','symptom','alarm','site','procedure',   -- original (ADR-004: system=subsystem, version=series, site=node)
  'event','command','metric','object'));
ALTER TABLE entity ADD COLUMN IF NOT EXISTS props JSONB NOT NULL DEFAULT '{}';  -- command template fields, event notes, ...

-- ---------- person ----------
ALTER TABLE person ADD COLUMN IF NOT EXISTS team         TEXT;
ALTER TABLE person ADD COLUMN IF NOT EXISTS years        INT;
ALTER TABLE person ADD COLUMN IF NOT EXISTS expertise    TEXT[] DEFAULT '{}';
ALTER TABLE person ADD COLUMN IF NOT EXISTS availability TEXT;
ALTER TABLE person DROP CONSTRAINT IF EXISTS person_availability_check;
ALTER TABLE person ADD CONSTRAINT person_availability_check
  CHECK (availability IS NULL OR availability IN ('on_shift','on_call','off_shift','retired'));
-- person.role and person.contact already exist in schema.sql

-- ---------- heuristic ----------
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS kind         TEXT NOT NULL DEFAULT 'note';
ALTER TABLE heuristic DROP CONSTRAINT IF EXISTS heuristic_kind_check;
ALTER TABLE heuristic ADD CONSTRAINT heuristic_kind_check CHECK (kind IN ('note','warning_pattern'));
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS pattern      JSONB;   -- structured watcher trigger: events/metrics/window/predicts
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS not_when_text TEXT;   -- when the note does NOT apply
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS captured_via TEXT;
ALTER TABLE heuristic DROP CONSTRAINT IF EXISTS heuristic_captured_via_check;
ALTER TABLE heuristic ADD CONSTRAINT heuristic_captured_via_check
  CHECK (captured_via IS NULL OR captured_via IN ('interview','referral','debrief','incident','import'));
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS captured_at  DATE;
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS signed_by    TEXT REFERENCES person(id);
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS signed_at    DATE;

-- ---------- edge: every link is citable ----------
ALTER TABLE edge ADD COLUMN IF NOT EXISTS source_id  TEXT;   -- doc_chunk.id or heuristic.id that justifies the link
ALTER TABLE edge ADD COLUMN IF NOT EXISTS created_by TEXT;
ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_rel_check;
ALTER TABLE edge ADD CONSTRAINT edge_rel_check CHECK (rel IN (
  'about','symptom_of','fixed_by','precedes','extends','contradicts','supersedes',
  'disagrees_with','expert_in',
  'depends_on','diagnosed_by','mentions','applies_to'));

-- ---------- doc_chunk: edition + re-ingest diffing ----------
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS edition      TEXT;  -- e.g. 'TMF Reference Manual, H-series edition (540138-001, July 2005)'
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS doc_version  TEXT;  -- publisher part number, e.g. '540138-001'
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS content_hash TEXT;  -- sha256 of text

-- ADR-005: manuals are J/H editions but \PROD is L-series, so an exact version filter returns nothing.
-- Declare them explicitly applicable to all series (ADR-001: flag + NULL together) and keep the real edition.
UPDATE doc_chunk SET version_id = NULL, all_versions = TRUE WHERE all_versions = FALSE;
UPDATE doc_chunk SET
  edition = CASE split_part(id, ':', 2)
    WHEN 'TMF-Reference' THEN 'TMF Reference Manual, H-series edition (540138-001, July 2005)'
    WHEN 'Pathway'       THEN 'Pathway/iTS manual, J/H-series edition (426748-005, May 2009)'
    WHEN 'SCF-Storage'   THEN 'SCF Reference Manual for the Storage Subsystem, J/H-series edition (529937-022, Feb 2014)'
    WHEN 'TACL-Reference' THEN 'TACL Reference Manual, J/H-series edition (429513-017, Aug 2013)'
    WHEN 'PEEK'          THEN 'PEEK Utility Reference, J/H-series edition (529657-005, May 2010)'
    WHEN 'measure'       THEN 'Measure Reference Manual, J/H-series edition (523324-013, Mar 2010)'
    WHEN 'FUP'           THEN 'FUP Reference Manual, J/H-series edition (523323-012, Oct 2009)'
  END,
  doc_version = CASE split_part(id, ':', 2)
    WHEN 'TMF-Reference' THEN '540138-001' WHEN 'Pathway' THEN '426748-005' WHEN 'SCF-Storage' THEN '529937-022'
    WHEN 'TACL-Reference' THEN '429513-017' WHEN 'PEEK' THEN '529657-005' WHEN 'measure' THEN '523324-013'
    WHEN 'FUP' THEN '523323-012'
  END
WHERE edition IS NULL;
UPDATE doc_chunk SET content_hash = encode(sha256(convert_to(text, 'UTF8')), 'hex') WHERE content_hash IS NULL;

-- ---------- indexes ----------
CREATE INDEX IF NOT EXISTS edge_src_rel ON edge (src, rel);
CREATE INDEX IF NOT EXISTS heuristic_owner ON heuristic (owner_id);
