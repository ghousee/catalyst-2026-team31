# Team, schedule, and Claude Code workflow

## Roles (3 people)
- **Ghouse — backend/ML/graph:** ingestion, entity schema, graph, pipeline (context → graph → gate → Qwen → MiniCheck), watcher, eval harness.
- **UI teammate:** chat with confidence lanes, context chips, citation cards, "why Ravi says this", alerts panel, Ask-Ravi referral flow, risk dashboard. Builds against mocks in `docs/API_CONTRACT.md` from Saturday morning.
- **Security teammate — owns the trust story:**
  - everything local; nothing leaves the laptop (Jev flag off by default)
  - permission-aware retrieval (ACL on chunks)
  - prompt-injection demo: planted instruction in a doc → verifier/gate blocks it
  - audit log of every answer + citations (`answer_log`)
  - threat model (1 page), owns `.gitignore` / no-confidential-data-in-git check
  - writes the adversarial eval items

## Schedule
**Fri night (tonight)**
- Private GitHub repo, add teammates, protect `main` (PRs only)
- Push this skeleton; `docker compose up -d`; `ollama pull qwen3.5:4b embeddinggemma`
- Pick 1–2 demo systems + one context-trap pair from their docs
- **Lock the API contract**

**Sat AM:** graph + ingestion (Ghouse) · UI on mocks · security threat model · teammates write golden set → freeze by noon
**Sat PM:** pipeline end-to-end; UI wired to real API
**Sat night:** watcher replay + referral loop + risk endpoint
**Sun AM:** eval runs + ablation table; security demo; pitch deck
**Sun ~2 PM:** CODE FREEZE → rehearse → **record a backup demo video**
**Sun evening:** showcase

## Process (keep it light)
- Skip Jira. One GitHub Projects board: To do / Doing / Done. Sprints = Saturday, Sunday.
- Confluence: one architecture/pitch page Sunday morning; set up its MCP only if < 15 min, and turn it off when not writing docs (MCP tool schemas cost context).

## Git
```bash
git checkout -b feat/pipeline          # one branch per workstream: feat/ui, feat/security...
git worktree add ../kg-ingest feat/ingest     # parallel Claude sessions, one folder each
git worktree add ../kg-watcher feat/watcher
```
- `data/raw/`, `.env`, model files are gitignored. Share company docs via USB/shared drive, never git.
- Install `gh` CLI so Claude can open PRs.

## Claude Code usage plan (protect your limits)
- Main session: `claude --model opusplan` (Opus plans, Sonnet executes).
- Subagents pinned in `.claude/agents/`: `implementer` (sonnet), `reviewer` (opus, diffs only, at checkpoints), `test-runner` (haiku).
- Keep effort at default `medium`; `high` only for nasty bugs.
- Plan mode first on every task; one task per session; `/clear` between tasks.
- After spawning subagents, check `/usage` that Sonnet usage actually moves.
- Each teammate uses their own Claude account.
- Every time Claude gets something wrong → add a rule to `CLAUDE.md` → "Learned rules".
- Security teammate: injection/cyber content may trigger safety-classifier model fallback. Expected, not an account issue.
- Optional: `claude --remote-control` to check long tasks from your phone (transcript is stored on Anthropic servers — keep confidential docs out of those sessions).
