# Veteran Knowledge Graph — hackathon starter kit

Context-aware, citation-mandatory chatbot + proactive watcher that captures veterans' know-how.
Start with `CLAUDE.md` (Claude Code reads it automatically), then `docs/PLAN.md`.

## Tonight (≈30 min) — Windows / PowerShell
Needs: Git for Windows, Python 3.11+, Docker Desktop (running), Ollama for Windows, `gh` CLI.
```powershell
# 1. repo (when ready to share; until then just commit locally)
gh repo create veteran-kg --private --source=. --push
#    then: add teammates, protect main (Settings → Branches → require PR)

# 2. services
Copy-Item .env.example .env
docker compose up -d                       # Postgres + pgvector, schema auto-loaded on FIRST start
ollama pull qwen3.5:4b
ollama pull embeddinggemma
python -m venv .venv
.\.venv\Scripts\Activate.ps1               # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
pytest                                     # should pass before anything else

# 3. company docs → data\raw\  (gitignored, share by USB/drive, NEVER git)
#    data\raw already exists in the repo; just drop files in.
```
Schema changed? The init script only runs on an empty volume: `docker compose down -v; docker compose up -d`
(wipes the DB).

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
