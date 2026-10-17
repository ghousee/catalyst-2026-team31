-- Veteran Knowledge Graph schema (Postgres 16 + pgvector)
-- Shared entity backbone + overlays (doc chunks, person heuristics), all linked by entity IDs.
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------- Shared entity backbone ----------
CREATE TABLE entity (
  id           TEXT PRIMARY KEY,            -- e.g. 'sys:P-201', 'ver:P-201:v3', 'comp:valve-Y', 'alarm:X'
  -- ADR-004: 'system' = subsystem (sub:TMF), 'version' = series (rvu:L), 'site' = node (node:PROD).
  -- 002_knowledge_graph adds event / command / metric / object.
  kind         TEXT NOT NULL CHECK (kind IN ('system','version','component','symptom','alarm','site','procedure',
                                             'event','command','metric','object')),
  name         TEXT NOT NULL,
  aliases      TEXT[] DEFAULT '{}',         -- shop-floor names: 'audit trail filling', 'mirror down', 'pinned'
  parent_id    TEXT REFERENCES entity(id),  -- event/object/metric/command -> subsystem
  props        JSONB NOT NULL DEFAULT '{}'  -- command template fields (risk, source_id, ...), event notes
);

CREATE TABLE person (
  id           TEXT PRIMARY KEY,            -- 'ravi'
  name         TEXT NOT NULL,
  role         TEXT,
  team         TEXT,
  years        INT,                         -- years of NonStop experience
  expertise    TEXT[] DEFAULT '{}',
  availability TEXT CHECK (availability IS NULL OR availability IN ('on_shift','on_call','off_shift','retired')),
  active       BOOLEAN DEFAULT TRUE,
  contact      TEXT
);

-- ---------- Context fingerprint (shared by chunks + heuristics) ----------
-- system_id/version_id/site_id are REQUIRED filters at query time. Use
-- backend.pipeline.retrieve.context_where(): system_id = :system
--   AND (version_id = :version OR version_id IS NULL) AND (site_id = :site OR site_id IS NULL)
-- NULL version/site means "explicitly applies to all"; the CHECKs below forbid an accidental NULL.

-- ---------- Doc overlay ----------
CREATE TABLE doc_chunk (
  id           TEXT PRIMARY KEY,            -- 'doc:P-201-manual:4.2'
  source_file  TEXT NOT NULL,               -- path under data/raw (not committed)
  section      TEXT,
  text         TEXT NOT NULL,
  system_id    TEXT NOT NULL REFERENCES entity(id),
  version_id   TEXT REFERENCES entity(id),  -- NULL only when all_versions (enforced below)
  site_id      TEXT REFERENCES entity(id),  -- NULL only when all_sites (enforced below)
  all_versions BOOLEAN NOT NULL DEFAULT FALSE,  -- set explicitly at ingest; never inferred
  all_sites    BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from   DATE,
  valid_to     DATE,
  owner_id     TEXT REFERENCES person(id),  -- doc owner, for referrals
  acl          TEXT[] DEFAULT '{public}',   -- permission-aware retrieval
  edition      TEXT,                        -- real edition, e.g. 'TMF Reference Manual, H-series edition (540138-001, July 2005)'
  doc_version  TEXT,                        -- publisher part number
  content_hash TEXT,                        -- sha256(text), for re-ingest diffing
  loaded_at    TIMESTAMPTZ,                 -- last POST /documents load of this chunk (003)
  embedding    vector(768),                 -- embeddinggemma dim; adjust if needed
  CHECK ((version_id IS NULL) = all_versions),
  CHECK ((site_id IS NULL) = all_sites)
);

-- ---------- Person overlay (veteran heuristics / warning patterns) ----------
CREATE TABLE heuristic (
  id            TEXT PRIMARY KEY,           -- 'ravi:h12'
  owner_id      TEXT NOT NULL REFERENCES person(id),
  trigger_text  TEXT NOT NULL,              -- "pressure dips + alarm X within 10 min"
  call_text     TEXT NOT NULL,              -- "check valve Y first; almost never the sensor"
  why_text      TEXT,                       -- rationale in their words
  system_id     TEXT NOT NULL REFERENCES entity(id),
  version_id    TEXT REFERENCES entity(id), -- NULL only when all_versions
  site_id       TEXT REFERENCES entity(id), -- NULL only when all_sites
  all_versions  BOOLEAN NOT NULL DEFAULT FALSE,
  all_sites     BOOLEAN NOT NULL DEFAULT FALSE,
  provenance    TEXT NOT NULL,              -- 'interview:2026-10-17' | 'ticket:4512' | 'referral:q88'
  status        TEXT DEFAULT 'draft' CHECK (status IN ('draft','approved','retired')),
  endorsements  INT DEFAULT 0,
  last_validated DATE,
  is_trigger    BOOLEAN DEFAULT FALSE,      -- usable by the watcher
  kind          TEXT NOT NULL DEFAULT 'note' CHECK (kind IN ('note','warning_pattern')),
  pattern       JSONB,                      -- structured watcher trigger: events/metrics/window/predicts
  not_when_text TEXT,                       -- when the note does NOT apply
  captured_via  TEXT CHECK (captured_via IS NULL OR captured_via IN ('interview','referral','debrief','incident','import')),
  captured_at   DATE,
  signed_by     TEXT REFERENCES person(id), -- nothing goes live unsigned (design 8)
  signed_at     DATE,
  entered_by    TEXT,                      -- who typed it: any user id (003, 004); the owner signs
  needs_review  BOOLEAN NOT NULL DEFAULT FALSE,  -- linked manual section changed since signing (003)
  embedding     vector(768),
  CHECK ((version_id IS NULL) = all_versions),
  CHECK ((site_id IS NULL) = all_sites)
);

-- ---------- Edges (the graph) ----------
CREATE TABLE edge (
  src     TEXT NOT NULL,                    -- any id: entity / doc_chunk / heuristic / person
  rel     TEXT NOT NULL CHECK (rel IN (
            'about',          -- chunk/heuristic -> entity
            'symptom_of',     -- symptom -> cause component
            'fixed_by',       -- symptom/cause -> procedure|chunk|heuristic
            'precedes',       -- warning signal -> failure (watcher paths)
            'extends','contradicts','supersedes',   -- heuristic <-> doc_chunk
            'disagrees_with', -- heuristic <-> heuristic (keep both!)
            'expert_in',      -- person -> entity (for referrals)
            'depends_on',     -- object -> object (blast radius: SETTLE-SC -> TMF -> $AUDIT)
            'diagnosed_by',   -- event/symptom -> command
            'mentions',       -- chunk/heuristic -> entity (weak link)
            'applies_to'      -- command/heuristic -> series/node/entity
          )),
  dst     TEXT NOT NULL,
  weight  REAL DEFAULT 1.0,                 -- e.g. resolved-case count for expert_in
  source_id  TEXT,                          -- doc_chunk/heuristic id that justifies the link (graph loader enforces non-null)
  created_by TEXT,
  PRIMARY KEY (src, rel, dst)
);

-- ---------- Logs ----------
CREATE TABLE answer_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ DEFAULT now(),
  user_id     TEXT,                         -- asker, e.g. 'newhire1' (not necessarily a person row)
  question    TEXT,
  context     JSONB,                        -- resolved system/version/site
  outcome     TEXT CHECK (outcome IN ('answer','clarify','refer')),
  citations   TEXT[],
  dropped_claims INT DEFAULT 0,             -- removed by verifier
  referred_to TEXT REFERENCES person(id)
);

-- a junior's own starting level per subsystem (005); self-reported, shown on the Learning map, never used to answer
CREATE TABLE self_level (
  user_id   TEXT NOT NULL,
  system_id TEXT NOT NULL REFERENCES entity(id),
  level     TEXT NOT NULL CHECK (level IN ('new','some','confident')),
  set_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, system_id)
);

-- ---------- Referral loop (POST /refer, POST /refer/{id}/answer) ----------
CREATE TABLE referral (
  id            TEXT PRIMARY KEY,           -- 'q88'
  ts            TIMESTAMPTZ DEFAULT now(),
  from_user     TEXT NOT NULL,              -- 'newhire1'
  expert_id     TEXT NOT NULL REFERENCES person(id),
  question      TEXT NOT NULL,
  context       JSONB,                      -- resolved context sent with the question
  answer_log_id BIGINT REFERENCES answer_log(id),   -- the refer response that triggered it
  status        TEXT DEFAULT 'sent' CHECK (status IN ('sent','answered','closed')),
  answer        TEXT,
  answered_at   TIMESTAMPTZ,
  heuristic_id  TEXT REFERENCES heuristic(id)       -- set when saved as knowledge
);

-- ---------- Corrections (POST /feedback) ----------
CREATE TABLE feedback (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ DEFAULT now(),
  answer_log_id BIGINT NOT NULL REFERENCES answer_log(id),
  source_id     TEXT NOT NULL,              -- doc_chunk.id or heuristic.id
  action        TEXT NOT NULL CHECK (action IN ('endorse','wrong','outdated')),
  user_id       TEXT NOT NULL
);

-- ---------- Watcher alerts (GET /alerts) ----------
CREATE TABLE alert (
  id            TEXT PRIMARY KEY,           -- 'al-7'
  ts            TIMESTAMPTZ DEFAULT now(),
  entity_id     TEXT NOT NULL REFERENCES entity(id),  -- the version node the pattern fired on
  pattern_id    TEXT NOT NULL REFERENCES heuristic(id),
  probability   REAL NOT NULL,
  message       TEXT NOT NULL,
  fix_claims    JSONB DEFAULT '[]',         -- same shape as /chat claims
  backup_expert_id TEXT REFERENCES person(id),
  signal        JSONB,                      -- the log/alarm rows that matched
  acknowledged  BOOLEAN DEFAULT FALSE
);

CREATE INDEX ON doc_chunk (system_id, version_id, site_id);
CREATE INDEX ON heuristic (system_id, version_id, site_id);
CREATE INDEX ON edge (dst, rel);
CREATE INDEX ON edge (src, rel);
CREATE INDEX ON referral (expert_id, status);
CREATE INDEX ON feedback (source_id);
CREATE INDEX ON alert (ts DESC);
-- After loading data:
-- CREATE INDEX ON doc_chunk USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX ON heuristic USING hnsw (embedding vector_cosine_ops);
-- Created by backend.ingest.loader.ensure_indexes() (same statements, IF NOT EXISTS):
--   CREATE INDEX doc_chunk_fts_en ON doc_chunk USING gin (to_tsvector('english', text));   -- keyword_search
--   CREATE INDEX doc_chunk_emb_hnsw ON doc_chunk USING hnsw (embedding vector_cosine_ops);
