# CLAUDE.md — Veteran Knowledge Graph (hackathon)

Read this first, every session. Full context lives in `docs/`.

**Navigation (saves context):** read `vault/00 Index.md` next, then only the vault notes for the area
you're touching; jump to the `file:line` they give instead of scanning folders. When you change code,
update its vault note in the same commit (new module → new note + link from the index). Notes stay short.

**UI work:** follow `frontend/CLAUDE.md` (scope, fixed API contract, demo script, `feat/ui` branch).

**Domain:** the sponsor is **CAIL**; the target is **HPE NonStop** operations (banking/ATM, POS, telecom).
Placeholder examples in docs (P-201 pumps, Ravi, valve Y) predate this and are being replaced — see `vault/todo.md`.

## What we're building (1 paragraph)
A **local, citation-mandatory chatbot + proactive watcher** that captures long-tenured
employees' domain knowledge ("warning patterns") and guides new hires. Two halves share
one knowledge graph:
- **Chatbot (reactive):** answers ONLY with cited facts; if unsure → refers to the right veteran.
- **Watcher (proactive):** matches live signals (alarms/tickets/logs) against veterans'
  trigger patterns and warns *before* failures, with the fix + who to ask.

The company's #1 concern is **context, not hallucination**: never give instructions for
System A when the user is on System B (same symptom/"key", different system/version).

## Non-negotiable rules
1. **Every claim has a citation** (`source_id`). Claims without one are dropped *by code*.
2. **Never answer outside the resolved context** (system + version + site). Filter BEFORE retrieval.
3. **Ambiguous context → ask one clarifying question.** Insufficient context → **refer to a person**. Never guess.
4. The LLM **only writes glue text**. Facts come from the graph/docs. Prefer deterministic graph queries when a question is graph-answerable.
5. **Company docs never enter git.** They live in `data/raw/` (gitignored). No secrets in code; use `.env`.
6. Everything runs **locally** on the laptop (RTX 4050 6GB, Ultra 7 155H, 16GB RAM). Jev is the only optional cloud call, behind a flag.
7. Don't mark work done until `pytest tests/unit` passes.

## Pipeline (in order)
```
question
 → 1. extract entities + resolve context (system, version, site)   # ask if ambiguous
 → 2. graph query (deterministic when possible) + filtered vector search in that slice
 → 3. sufficiency gate  ("is retrieved context enough?")            # no → refer
 → 4. Qwen writes answer as JSON [{claim, source_id}]               # glue only
 → 5. MiniCheck verifies each claim vs its source; drop unsupported
 → 6. answer card (doc lane / veteran lane) OR referral to best expert
```

## Stack
- Backend: Python 3.11 + FastAPI. Frontend: Next.js chat on localhost.
- Graph + vectors: Postgres 16 + pgvector in Docker (`docker compose up -d`). Entities, edges, chunks, heuristics are tables (see `sql/schema.sql`).
- LLM: Ollama `qwen3.5:4b` (fallback `phi4-mini`). Must show `100% GPU` in `ollama ps`.
- Embeddings: Ollama `embeddinggemma` — run on CPU to keep VRAM for the LLM.
- Verifier: MiniCheck (Flan-T5 770M) on CPU. Sufficiency gate: small classifier/prompt; Jev optional.
- Jev (TypeSafe): optional, `USE_JEV=false` by default. Good for typed yes/no + calibrated probability (sufficiency gate, trigger matching).

## Repo layout
```
backend/      FastAPI app: ingest/, graph/, pipeline/, watcher/, api/
frontend/     Next.js chat UI (builds against mocks in docs/API_CONTRACT.md)
sql/          schema.sql
eval/         golden.jsonl, run_eval.py, results/
data/raw/     COMPANY DOCS — gitignored, never commit
tests/unit/   fast tests the Stop hook runs
docs/         PLAN, RESEARCH, SCHEMA, API_CONTRACT, EVAL, TEAM_AND_SCHEDULE, PITCH
vault/        Obsidian vault: code map, decisions, glossary, todo (read 00 Index.md first)
```

## Commands (Windows / PowerShell — no `&&` in PS 5.1; one command per line)
```powershell
docker compose up -d                      # postgres+pgvector (Docker Desktop must be running)
ollama pull qwen3.5:4b
ollama pull embeddinggemma
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.api.main:app --reload     # API on :8000
pytest tests/unit -q                      # fast tests
python eval/run_eval.py                   # golden-set scores → eval/results/
```
Dev machine is Windows: use Windows paths/commands in docs and scripts; prefer Python over bash for tooling.

## Working style (for Claude Code)
- Plan mode first for anything non-trivial; keep tasks small and single-purpose.
- One task per session; `/clear` between tasks. Parallel sessions use git worktrees.
- Match `docs/API_CONTRACT.md` exactly — frontend depends on it.
- When you make a mistake the team corrects, **add a one-line rule here**.

## How to talk to Ghouse (repo owner)
- Casual, direct, TL;DR first. Engineering terms are fine. No filler or encouragement.
- He pushes back — give your honest view and the trade-off, not agreement.
- Check claims against the actual source/docs before asserting; say when unverified.
- New open-ended topic → ask up to 3 clarifying questions in one go before a big answer.
- When an artifact/file changes, reprint the full updated version.

## Learned rules (append below)
- HARD RULE (Ghouse): don't overengineer. Simplest solution that works well; cut scope before adding machinery. Extras are proposals, never built unasked.
- Never run `npm run build` / `next build` in `frontend/` while a dev server may be running there: both use `.next/` and the build breaks the dev server (CSS/JS 404). Verify with `npx tsc --noEmit` + `npm run lint`; if a build is needed, stop dev first and delete `.next/` after.
