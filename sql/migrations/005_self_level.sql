-- 005_self_level.sql — a junior's own starting level per subsystem (idempotent).
-- Self-reported, shown on the Learning map next to what they have actually covered. Never used to answer questions.
-- Fresh installs get the same result from sql/schema.sql (keep the two in sync).
CREATE TABLE IF NOT EXISTS self_level (
  user_id   TEXT NOT NULL,
  system_id TEXT NOT NULL REFERENCES entity(id),
  level     TEXT NOT NULL CHECK (level IN ('new','some','confident')),
  set_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, system_id)
);
