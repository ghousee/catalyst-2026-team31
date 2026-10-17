-- Veteran Knowledge Graph schema (Postgres 16 + pgvector)
-- Shared entity backbone + overlays (doc chunks, person heuristics), all linked by entity IDs.
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------- Shared entity backbone ----------
CREATE TABLE entity (
  id           TEXT PRIMARY KEY,            -- e.g. 'sys:P-201', 'ver:P-201:v3', 'comp:valve-Y', 'alarm:X'
  kind         TEXT NOT NULL CHECK (kind IN ('system','version','component','symptom','alarm','site','procedure')),
  name         TEXT NOT NULL,
  aliases      TEXT[] DEFAULT '{}',         -- shop-floor names: 'line 2 pump', 'the big pump'
  parent_id    TEXT REFERENCES entity(id)   -- version -> system, component -> system
);

CREATE TABLE person (
  id           TEXT PRIMARY KEY,            -- 'ravi'
  name         TEXT NOT NULL,
  role         TEXT,
  active       BOOLEAN DEFAULT TRUE,
  contact      TEXT
);

-- ---------- Context fingerprint (shared by chunks + heuristics) ----------
-- system_id/version_id/site_id are REQUIRED filters at query time.

-- ---------- Doc overlay ----------
CREATE TABLE doc_chunk (
  id           TEXT PRIMARY KEY,            -- 'doc:P-201-manual:4.2'
  source_file  TEXT NOT NULL,               -- path under data/raw (not committed)
  section      TEXT,
  text         TEXT NOT NULL,
  system_id    TEXT REFERENCES entity(id),
  version_id   TEXT REFERENCES entity(id),  -- NULL = applies to all versions (be explicit!)
  site_id      TEXT REFERENCES entity(id),
  valid_from   DATE,
  valid_to     DATE,
  owner_id     TEXT REFERENCES person(id),  -- doc owner, for referrals
  acl          TEXT[] DEFAULT '{public}',   -- permission-aware retrieval
  embedding    vector(768)                  -- embeddinggemma dim; adjust if needed
);

-- ---------- Person overlay (veteran heuristics / warning patterns) ----------
CREATE TABLE heuristic (
  id            TEXT PRIMARY KEY,           -- 'ravi:h12'
  owner_id      TEXT NOT NULL REFERENCES person(id),
  trigger_text  TEXT NOT NULL,              -- "pressure dips + alarm X within 10 min"
  call_text     TEXT NOT NULL,              -- "check valve Y first; almost never the sensor"
  why_text      TEXT,                       -- rationale in their words
  system_id     TEXT REFERENCES entity(id),
  version_id    TEXT REFERENCES entity(id),
  site_id       TEXT REFERENCES entity(id),
  provenance    TEXT NOT NULL,              -- 'interview:2026-10-17' | 'ticket:4512' | 'referral:q88'
  status        TEXT DEFAULT 'draft' CHECK (status IN ('draft','approved','retired')),
  endorsements  INT DEFAULT 0,
  last_validated DATE,
  is_trigger    BOOLEAN DEFAULT FALSE,      -- usable by the watcher
  embedding     vector(768)
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
            'expert_in'       -- person -> entity (for referrals)
          )),
  dst     TEXT NOT NULL,
  weight  REAL DEFAULT 1.0,                 -- e.g. resolved-case count for expert_in
  PRIMARY KEY (src, rel, dst)
);

-- ---------- Logs ----------
CREATE TABLE answer_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ DEFAULT now(),
  question    TEXT,
  context     JSONB,                        -- resolved system/version/site
  outcome     TEXT CHECK (outcome IN ('answer','clarify','refer')),
  citations   TEXT[],
  dropped_claims INT DEFAULT 0,             -- removed by verifier
  referred_to TEXT REFERENCES person(id)
);

CREATE INDEX ON doc_chunk (system_id, version_id, site_id);
CREATE INDEX ON heuristic (system_id, version_id, site_id);
CREATE INDEX ON edge (dst, rel);
-- After loading data:
-- CREATE INDEX ON doc_chunk USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX ON heuristic USING hnsw (embedding vector_cosine_ops);
