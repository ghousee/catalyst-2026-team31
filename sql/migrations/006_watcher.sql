-- 006_watcher.sql — early warnings (idempotent). Apply: python -m backend.graph.migrate
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).

-- a warning pattern's machine-checkable trigger (the note text stays the human version). Shapes:
--   {"type":"count","event":"evt:TMF-185","count":2,"window_min":30,"metric":"met:audit-capacity-pct","above":60,"rising":true,"lead_min":40}
--   {"type":"stalled","metric":"met:revive-current-sector","minutes":10}
ALTER TABLE heuristic ADD COLUMN IF NOT EXISTS rule JSONB;

-- alerts now come from three detectors: a veteran's pattern, a graph 'precedes' chain, or a metric trend
ALTER TABLE alert ALTER COLUMN pattern_id DROP NOT NULL;
ALTER TABLE alert ADD COLUMN IF NOT EXISTS node_id   TEXT;
ALTER TABLE alert ADD COLUMN IF NOT EXISTS kind      TEXT;   -- pattern | chain | trend
ALTER TABLE alert ADD COLUMN IF NOT EXISTS severity  TEXT;   -- info | warning | critical
ALTER TABLE alert ADD COLUMN IF NOT EXISTS lead_min  INT;    -- expected minutes until the failure, if known

-- rules for the two seeded warning patterns (written from their trigger text)
UPDATE heuristic SET rule = '{"type":"count","event":"evt:TMF-185","count":2,"window_min":30,"metric":"met:audit-capacity-pct","above":60,"rising":true,"lead_min":40}'
 WHERE id = 'maria:h7' AND rule IS NULL;
UPDATE heuristic SET rule = '{"type":"stalled","metric":"met:revive-current-sector","minutes":10}'
 WHERE id = 'lena:h2' AND rule IS NULL;
