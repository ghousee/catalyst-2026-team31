# ingest

Folder `backend/ingest/`. Turns HPE manual text (`data/raw/hpe/*.txt`, gitignored) into `doc_chunk` rows with
embeddings. Run: `python -m backend.ingest.loader` (needs `docker compose up -d`, `embeddinggemma` pulled).
Results and rationale: [[rag spike]] / `docs/RAG_SPIKE.md`.

## Entry points
- `chunker.py:314` `chunk_manual(text, manual)` -> `[Chunk]` (id `doc:<manual>:<slug>`). Pure, unit-tested.
  - `:209` `sections()` finds boundaries; `:63` `strip_running_lines()` drops page numbers/footers and extracts running heads;
    `:129` `toc_titles()` (first 15% of pages only); `:268` `_qualify_generic()`; `:283` `_split_big()`.
- `manuals.py:13` `Manual` + `MANUALS` table: subsystem entity, series entity, edition, cover-page "supports" text.
- `embedder.py:20` `embed(texts, cpu=False)`; `:35` `embed_query()` (CPU by default). Task prefixes in `doc_text`/`query_text`.
- `loader.py:49` `load_manual()`; `:29` `ensure_entities()`; `:42` `ensure_indexes()` (GIN FTS + HNSW).
- `backend/settings.py` reads `.env` (DATABASE_URL, OLLAMA_URL, LLM_MODEL, EMBED_MODEL).

## Invariants
- Docs: `all_sites = TRUE`, `site_id NULL`, `all_versions = FALSE`, `version_id` from `manuals.py` ([[ADR-004 context dimensions]]).
  Entity kinds: `system` = `sub:*`, `version` = `rvu:*`, `site` = `node:*` (schema CHECK untouched).
- Loader is idempotent per manual (deletes `doc:<manual>:%` first). Embedding dim 768 = `vector(768)`.
- Never commit anything under `data/`; tests use synthetic text only.
- Bare 1-4 digit lines are message numbers, not page numbers, unless last on the page or after a doc-id footer.

## Gotchas
- TMF is H-series only -> `rvu:H`; every other manual `rvu:J` (they also claim H). A single exact `version_id`
  filter hurts when a manual supports several series: see [[retrieve]].
- Merged message chunks take the first message's id (`msg-3122` holds 3122 and 3123).
- `TACL-Reference.txt` headings have kerning spaces ("Com m ands"); slugs inherit them.
- `Pathway.txt` is the Pathway/iTS (TCP/TERM) manual; server-class (TS/MP) commands are mostly absent.
- GPU embedding of the whole corpus: ~170 s; CPU ~35 min (est.). Query embeddings: CPU, ~300 ms.
- Windows: `.txt` read as UTF-8 with `errors="replace"`; use `PYTHONIOENCODING=utf-8` when printing.

Tested by [[tests]] -> `test_chunker.py`.

## Document upload (2026-10-17) — `backend/documents.py`
- `POST /documents` saves to `data/raw/uploads/` (gitignored), `chunk_text` = HPE chunker if its chunks cover >= 60% of the text, else `generic_chunks`
  (short single-line paragraph = heading; ids `doc:<key>:<heading slug>`, stable across re-uploads). Key = title with non-alphanumerics -> `-`.
- `diff_chunks` (pure): added / changed (same id, new hash) / unchanged / removed. Only added+changed are embedded. Removed -> `valid_to = today`.
- `mentions` edges (`created_by='auto'`) from new chunks to entities whose name/alias occurs (`alias_tokens` / `mentioned`, pure).
- `flag_notes`: approved notes linked (edge src/dst/source_id) to a changed/removed chunk -> `needs_review = TRUE`. No endpoint clears the flag yet.
- Clears `retrieve._df_cache` (keyword idf cache would ignore terms only the new text has). Unknown subsystem name -> new `sub:<NAME>` system entity (alias = the name).
- A question must name the subsystem (e.g. "Gadget Test System") for `resolve` to find a new one.
