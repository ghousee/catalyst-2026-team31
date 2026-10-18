-- 009_learning_links.sql — an emerging veteran's use of the assistant shows in Synapse (idempotent).
-- asked_about: person -> subsystem they asked about; learned_from: person -> veteran note an answer cited them.
-- (knows, from 008, is the stronger link: they answered a check on that note correctly.)
ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_rel_check;
ALTER TABLE edge ADD CONSTRAINT edge_rel_check CHECK (rel IN (
  'about', 'symptom_of', 'fixed_by', 'precedes', 'extends', 'contradicts', 'supersedes', 'disagrees_with',
  'expert_in', 'depends_on', 'diagnosed_by', 'mentions', 'applies_to', 'knows', 'asked_about', 'learned_from'));
