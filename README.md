# NonStop Copilot (CAIL challenge, Team #31)

A local AI operator assistant for HPE NonStop systems. It answers with citations to the HPE manuals
and to named veterans, proposes commands that run only after approval, and warns early using
veterans' warning patterns. Every answer is scoped to the node, release and subsystem the operator is on.

**Start here:** `docs/architecture.html` (diagrams) → `docs/SYSTEM_DESIGN.md` → `docs/RAG_SPIKE.md` (measured results)
→ `vault/00 Index.md` (code map; open `vault/` in Obsidian). Claude Code reads `CLAUDE.md` automatically.

## Status (2026-10-17)
- Done: schema + context filter, manual ingest (7 HPE manuals, 3,777 chunks), hybrid search, Qwen answer
  generation, MiniCheck verifier, sufficiency gate, UI on mock data, API contract v2.
- Next: knowledge graph + veteran knowledge, `/chat` backend wired to the UI, command catalog + simulator, watcher, eval set.

## Setup — Windows / PowerShell
Needs: Git, Python 3.11+, Node 20+, Docker Desktop (running; NVIDIA GPU optional but recommended).
```powershell
# 1. services (Postgres + pgvector, Ollama with GPU)
Copy-Item .env.example .env              # change PG_PORT/OLLAMA_PORT + URLs if 5432/11434 are taken
docker compose up -d                     # schema auto-loads on the FIRST start of an empty volume
docker compose exec ollama ollama pull qwen3.5:4b
docker compose exec ollama ollama pull embeddinggemma

# 2. Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1             # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
pytest                                   # should pass

# 3. HPE manuals → data\raw\hpe\  (gitignored; public HPE docs, but don't commit or redistribute them)
#    Get the PDFs from the HPE NonStop Technical Library (support.hpe.com, docId a00099017en_us)
#    or ask Ghouse for the copies used here: TACL-Reference, SCF-Storage, TMF-Reference, Pathway,
#    PEEK, measure, FUP (.pdf + extracted .txt). Then load them:
python -m backend.ingest.loader          # ~6 min with GPU embeddings
python scripts/rag_spike.py --all        # optional: reproduce the numbers in docs/RAG_SPIKE.md

# 4. UI (runs on built-in mock data, no backend needed)
cd frontend; npm install; npm run dev    # http://localhost:3000
```
Schema changed? The init script only runs on an empty volume: `docker compose rm -sf db; docker volume rm veteran-kg_pgdata; docker compose up -d db`
(wipes the DB, keeps the Ollama models). Don't run `npm run build` while `npm run dev` is running.

## First Claude Code prompts (each in its own session/worktree)
1. `claude --model opusplan` → plan mode: "Read CLAUDE.md, docs/PLAN.md, sql/schema.sql. Plan the ingestion module for the docs in data/raw: chunk by section, tag system/version/site, embed with embeddinggemma, load into doc_chunk + entity + edge. Ask me about anything ambiguous in the docs."
2. "Use the implementer agent to build backend/pipeline/context.py per backend/pipeline/README.md, with unit tests."
3. UI teammate: "Build the Next.js chat UI against the mock responses in docs/API_CONTRACT.md (answer / clarify / refer cards, lanes, context chips, alerts panel)."
4. Before merging: "Use the reviewer agent on this branch."
5. Eval: "Use the test-runner agent to run python eval/run_eval.py --config 4."

## What's in here
| Path | What |
|---|---|
| `CLAUDE.md` | Rules, pipeline, stack, commands, how to work with Ghouse |
| `docs/PLAN.md` | Problem, design decisions, knowledge model, UX, loop, spin-offs, scope |
| `docs/RESEARCH.md` | Competitors, papers → design changes, Jev, model choice, costs, Claude Code practices, all sources |
| `docs/API_CONTRACT.md` | Exact JSON for /chat, /refer, /feedback, /alerts, /risk |
| `docs/EVAL.md` | How to build the golden set, metrics, ablation table |
| `docs/TEAM_AND_SCHEDULE.md` | Roles, weekend schedule, git + Claude Code usage plan |
| `docs/SYSTEM_DESIGN.md` | **NonStop/CAIL architecture (current)** — read before PLAN.md |
| `docs/PITCH.md` | 5-minute demo script |
| `sql/schema.sql` | Entity backbone + doc/person overlays + edges |
| `eval/` | Golden-set template + scoring harness |
| `.claude/` | Subagents (sonnet implementer, opus reviewer, haiku test-runner), opusplan default, Stop hook running unit tests |

Notes:
- The Stop hook (`.claude/hooks/stop_tests.py`) blocks Claude from finishing while `tests/unit` fails, at most once per stop. It calls `python`, so start Claude Code from a shell where the venv is active. If it misbehaves, remove the `hooks` block from `.claude/settings.json`.
- Check the exact MiniCheck model ID on its GitHub (github.com/Liyan06/MiniCheck) before wiring `verify.py`.
- Vector dim in `schema.sql` is 768; confirm against `embeddinggemma`'s output and adjust.
