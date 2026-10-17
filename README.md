# Veteran Knowledge Graph — hackathon starter kit

Context-aware, citation-mandatory chatbot + proactive watcher that captures veterans' know-how.
Start with `CLAUDE.md` (Claude Code reads it automatically), then `docs/PLAN.md`.

## Tonight (≈30 min)
```bash
# 1. repo
git init && git add . && git commit -m "skeleton"
gh repo create veteran-kg --private --source=. --push
#    then: add teammates, protect main (Settings → Branches → require PR)

# 2. services
cp .env.example .env
docker compose up -d                       # Postgres + pgvector, schema auto-loaded
ollama pull qwen3.5:4b && ollama pull embeddinggemma
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. company docs → data/raw/  (gitignored, share by USB/drive, NEVER git)
mkdir -p data/raw
```

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
| `docs/PITCH.md` | 5-minute demo script |
| `sql/schema.sql` | Entity backbone + doc/person overlays + edges |
| `eval/` | Golden-set template + scoring harness |
| `.claude/` | Subagents (sonnet implementer, opus reviewer, haiku test-runner), opusplan default, Stop hook running unit tests |

Notes:
- The Stop hook blocks Claude from finishing while `tests/unit` fails. If it misbehaves, remove the `hooks` block from `.claude/settings.json`.
- Check the exact MiniCheck model ID on its GitHub (github.com/Liyan06/MiniCheck) before wiring `verify.py`.
- Vector dim in `schema.sql` is 768; confirm against `embeddinggemma`'s output and adjust.
