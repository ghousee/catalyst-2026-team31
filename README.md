# NonStop Copilot — CAIL challenge, Team #31

> "How might we use AI to help the next generation of IT operators understand, monitor, and troubleshoot
> mission-critical enterprise systems through natural language, while preserving the expertise of experienced
> professionals?" — CAIL challenge statement ([full brief](vault/design/challenge%20brief.md))

A local AI operations assistant for **HPE NonStop** operators. It gets **Emerging Veterans** (juniors) to work like
**Veterans** (seniors) faster:

- **Takes alarms from the monitoring tools operators already use** (IR Prognosis REST API, BlackWood MOMI alarm
  exports) and puts the steps next to each one, taken from **Synapse**, the knowledge graph: the veterans' advice, the
  manual section for that exact message, read-only checks and who to call. Each alert gets a **High / Medium / Low**
  priority with a plain-English reason.
- **Warns before failures.** A named veteran's warning pattern fires ahead of the failure ("Grace's pattern: about
  20 min before failure"), and so do the graph's "usually comes before" links and metric trends.
- **Answers in plain English with two kinds of citation:** *which manual section* and *which veteran*. Answers are
  always scoped to the node (`\PROD` / `\DR`), release series and subsystem the operator is on.
- **Turns questions into commands** from a verified catalog. Each command is risk-labelled and dry-run on a
  simulator. Only a **Veteran** can approve it; critical commands need a second veteran. Emerging Veterans can ask,
  dry-run and learn, but not approve.
- **Keeps veterans' knowledge.** Veterans teach by talking. A note goes live only after its owner signs it, and is
  then linked into **Synapse**, the knowledge graph, automatically.
- **Measures learning.** Every Emerging Veteran has a learning map: what they have been shown, the starting level
  they gave themselves, and what they have **demonstrated**. A knowledge check turns veterans' notes into "what would
  you do?" questions, grades the answer against the note, and links a pass into Synapse (`knows`). A guided training
  sandbox walks through an incident step by step without recording anything.

Everything runs locally (Postgres + pgvector, Ollama on one 6 GB GPU). No cloud calls and no production access.

**Read next:** [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) (current design) →
[docs/API_CONTRACT.md](docs/API_CONTRACT.md) → [vault/00 Index.md](vault/00%20Index.md) (code map, open `vault/` in Obsidian).

## How it works

```mermaid
flowchart LR
  subgraph SRC["Sources"]
    MAN["HPE manuals<br/>7 PDFs, 3,777 sections"]
    VET["Veterans<br/>Teach chat, sign-off"]
    PRG["IR Prognosis<br/>REST API: open problems"]
    MOM["BlackWood MOMI<br/>alarm export folder"]
    RPL["Demo replay feeds"]
  end
  subgraph CORE["Copilot API (FastAPI, local)"]
    ING["Ingest<br/>sections, embeddings,<br/>commands and messages"]
    CON["Connectors<br/>poller, folder reader,<br/>map alarm to graph node"]
    WAT["Watcher<br/>tool alarms, veteran patterns,<br/>graph chains, trends, priority"]
    ASK["Assistant<br/>hybrid search, rerank,<br/>one cited answer"]
    CMD["Commands<br/>catalog, risk, guards,<br/>veteran approval, simulate"]
    LRN["Learning<br/>maps, knowledge checks,<br/>training sandbox"]
  end
  subgraph DB["Synapse (Postgres + pgvector)"]
    G["graph<br/>1,718 nodes, ~3,560 links"]
    N["signed veteran notes"]
    D["manual sections + vectors"]
    L["question log, checks,<br/>learning maps"]
  end
  UI["Operator console<br/>Next.js"]
  MAN --> ING --> D
  ING --> G
  VET --> N --> G
  PRG --> CON
  MOM --> CON
  RPL --> WAT
  CON -- "alarm + node + entity" --> WAT
  WAT -- "steps from" --> G
  WAT -- "alert card" --> UI
  UI -- "question + node" --> ASK
  ASK --> D
  ASK --> N
  UI -- "approve (veterans)" --> CMD
  UI -- "check / practice" --> LRN
  LRN -- "grade against" --> N
  LRN -- "knows link" --> G
  ASK --> L
```

**Asking a question:** context is locked to the session's node and series. Then hybrid search (vector + keyword)
runs over the manual sections, plus a vector search over signed veteran notes for this node only. A cross-encoder
reranks the results, and the top 5 sources go to **Qwen 3.5 4B**. Qwen writes one answer with `[n]` citations,
names the veteran, and keeps every "do not". If the sources don't cover the question, it says so or asks one short
question. Typical answer time is 5–8 s on the GPU.

**An alarm from a monitoring tool:** the connector reads the tool's own output:
- **Prognosis:** polls its REST API dataset of open problems every 10 s; the column names are configurable.
- **MOMI:** reads its alarm export files (template blocks or TAB log lines) every 5 s.

It reads the node, and the message number quoted in the text ("TMF 185", "PATHWAY 1034") puts the alarm on its
Synapse node. **The steps come from the graph, not from the tool:**
- curated events carry veteran notes, commands and manual sections;
- every other message number in the manuals lands on its own manual section.

An alarm whose node can't be read is dropped, never guessed.

**Early warnings:** every source becomes one normalised event. The watcher runs plain-code detectors (no LLM), and
each alert card is built from the graph:

| Detector | Example | Card shows |
|---|---|---|
| **Tool alarm** (Prognosis, MOMI) | "IR Prognosis: TMF 185: audit file pinned. Usually comes before TMF 187" | Steps from Synapse; source tool |
| **Veteran pattern** (a signed warning-pattern note with a rule) | Grace: CPU 101 then busy > 80% and rising within 15 min | Her steps / why / when not, word for word; lead time; read-only checks; backup veteran |
| **Graph chain** (`precedes` links) | TMF 185 usually comes before TMF 187 | Notes about what comes next; manual sections; checks |
| **Metric trend** | Audit trail at 66% and rising, full in about 57 min | Notes about the metric; checks |

**Priority (High / Medium / Low), with the reasons on the card:**

| Signal | Points |
|---|---|
| On `\PROD` | 2 |
| Is, or usually leads to, a transaction-stopping event (audit trail full, BEGINTRANS disabled, no server available, mirror down, CPU down) | 2 |
| A veteran's pattern matched | 1 |
| Failure expected within 30 min | 1 |
| The tool marks it critical | 1 |

4 points or more is High, 2–3 is Medium, below 2 is Low. A veteran's card replaces the chain and trend cards for the
same event or metric. Alerts are open to everyone, and each card keeps its node: a `\PROD` pattern never fires on
`\DR`.

## Demo scenarios
**Alerts → Connected monitoring tools:** sample alarms go through the real Prognosis and MOMI connectors (via local
stand-ins), and their cards appear within seconds.

**Training Simulator:**
- **Audit trail filling** opens a **guided sandbox exercise**:
  1. the alarm and the task;
  2. pick a first check (wrong picks are explained with the veteran's reason);
  3. read simulated `STATUS AUDITTRAIL` and `STATUS TRANSACTION` output;
  4. write your decision, which Qwen grades against Maria's notes;
  5. debrief.

  Nothing is recorded: it has its own simulator, and there is no log, learning map, Synapse or alert entry.
- The other three play a synthetic incident (real manual message numbers) into the watcher as if live:

1. **CPU down and takeover**: the brief's own example (a hardware failure cuts capacity). CPU 101 → Grace's pattern
   about 20 min before Pathway 1034 (no server available) → PEEK and Pathway checks.
2. **Audit trail filling** (also available as a replay): TMF 185 → trend countdown → Maria's quarter-end pattern
   about 40 min before TMF 187.
3. **Disk mirror revive stalled**: path error → Lena's "sector has not moved for 10 min" pattern.
4. **Pathway no server available**: Pathway 1038 warns before 1034.

## Results (independent 60-question set, `eval/`)
| Measure | Result |
|---|---|
| Correct behaviour (answer / clarify / refer as expected) | 80% |
| Key facts present in the answer | 89–93% |
| False refusals | 2% |
| Context leaks (another node's veteran note used) | **0** |
| Unsafe or inverted advice ("do not" turned into "do") | **0** |
| Answers citing the right manual / the right veteran when expected | 100% / 100% |
| Answer time | 5–8 s typical (Qwen 3.5 4B on an RTX 4050 6 GB) |

Weak spots: correctly refusing out-of-scope questions (about 50%) and asking for clarification when expected.
Detectors, connectors, priority and knowledge-check logic are unit-tested (191 unit tests pass). The eval figures
predate the latest answer-length change; re-run before quoting them.

## People
- **Veterans** (5, fictional): Maria Rossi (TMF, retired), Raj Patel (Pathway/TMF), Lena Kowalski (SCF Storage),
  Grace Okafor (performance/CPU), Tom Becker (TACL/FUP). They own and sign notes, have `expert_in` links to several
  subsystems, work on `\PROD`, approve commands, and are the only people suggested as "who to call".
- **Emerging Veterans** (10, fictional juniors): 1–2 subsystems each, a learning map, and a starting level. They work
  on `\DR`, can ask, dry-run, take knowledge checks and practise, but cannot approve commands. They can write down
  "Raj told me…" or "I found…"; a veteran has to sign it before it is used.
- Anyone picks who they are in **You: …** (top bar), which also switches the node. "New here?" creates a new
  Emerging Veteran. New veterans: Knowledge → Add knowledge / sign-off → **Add a veteran**.

## How knowledge gets in
| Who / what | How | What gets linked |
|---|---|---|
| Veteran | Teach chat or form → draft → owner signs | about (subsystem, commands, events it names), applies_to (node), expert_in +1, agrees/contradicts manual |
| Emerging Veteran | "Share something you found" / "Raj told me" | Same, after the named veteran signs |
| Emerging Veteran passes a knowledge check | Learning map → Check what I know → answer graded against the note | `knows` (person → note); "Demonstrated" on the learning map |
| New manual | Knowledge → Add document | sections + embeddings, commands and messages from section titles, changed sections flag notes "needs review" |
| Monitoring tool | Prognosis REST poller, MOMI export reader, `POST /events`; replay for the demo | alert cards on graph nodes, steps from the graph |

To see a new connection, after signing a note or passing a check click **See it in Synapse**, or use **Show latest
change** on the Synapse toolbar. Links made at sign-off are blue, and `knows` links are green.

## Assumptions and limitations
- **Real:** the HPE NonStop manuals (public documentation). **Fictional:** the veterans, emerging veterans and their
  notes (written for the demo, anchored to real manual sections). **Synthetic:** alerts, metrics, command output and
  incident feeds (simulator and replay). No production systems, customer data or real transactions.
- Commands never run on a real system. They are dry-run on a simulator, after approval.
- Monitoring connectors are built against the tools' documented outputs, but tested only against our stand-ins (see
  [docs/INTEGRATIONS_PROGNOSIS_MOMI.md](docs/INTEGRATIONS_PROGNOSIS_MOMI.md)):
  - **Prognosis:** REST API, open problems as JSON;
  - **MOMI:** no API; alarm emails / EMS and log exports.

  A real connection needs a customer's Prognosis URL and credentials (`PROGNOSIS_URL`, `PROGNOSIS_USER`,
  `PROGNOSIS_PASSWORD`) or their MOMI export folder (`MOMI_INBOX`). Prognosis column names depend on the customer's
  dataset (`backend/integrations/prognosis.py` FIELDS).
- No incident history yet, so alert cards do not show "warned early in X of Y past incidents".
- Commands and messages are extracted from manual section titles only. 2,645 of 3,777 sections are searchable but
  not linked to a graph node.
- A small local model (4B) keeps everything on-prem; a bigger model would answer better but needs more GPU.

## Database (Postgres 16 + pgvector)
```mermaid
erDiagram
  entity {
    text id PK "sub:TMF, evt:TMF-185, cmd:..., node:PROD"
    text kind
    text name
    text_array aliases
    text parent_id
  }
  doc_chunk {
    text id PK
    text section
    text text
    text system_id
    text edition
    vector768 embedding
  }
  person {
    text id PK
    text name
    text role
    int years
    text availability
    text level "veteran or emerging"
  }
  heuristic {
    text id PK
    text owner_id FK
    text kind "note or warning_pattern"
    text trigger_text
    text call_text
    text why_text
    text not_when_text
    text system_id
    text site_id "NULL = all nodes"
    text status "draft, approved, retired"
    jsonb rule "watcher trigger"
    vector768 embedding
  }
  edge {
    text src PK
    text rel PK
    text dst PK
    real weight
    text source_id "section or note that justifies it"
    text created_by "seed, auto, auto-docs, check, human"
  }
  answer_log {
    bigint id PK
    text user_id
    text question
    jsonb context
    text outcome
    text_array citations
  }
  self_level {
    text user_id PK
    text system_id PK
    text level "new, some, confident"
  }
  check_result {
    bigint id PK
    text user_id
    text note_id FK
    int score "0 missed, 1 partly, 2 got it"
  }
  alert {
    text id PK
    text kind "tool, pattern, chain, trend"
    text node_id
    text entity_id
    text pattern_id FK
    int lead_min
    text severity
    jsonb signal
  }
  person ||--o{ heuristic : "owns and signs"
  entity ||--o{ edge : "src or dst"
  heuristic ||--o{ edge : "src or dst"
  doc_chunk ||--o{ edge : "cited by"
  heuristic ||--o{ alert : "fires"
  heuristic ||--o{ check_result : "asked in"
```
Edge `rel` includes `knows` (a person passed a check on a note). Schema: `sql/schema.sql`; migrations
`sql/migrations/002–008` (apply with `python -m backend.graph.migrate`).

## Setup (Windows / PowerShell)
Needs Git, Python 3.11+, Node 20+, Docker Desktop (NVIDIA GPU recommended).
```powershell
# 1. services: Postgres + pgvector, Ollama
Copy-Item .env.example .env              # change ports/URLs if 5432/11434 are taken (we use 5433 / 11435)
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:4b
docker compose exec ollama ollama pull embeddinggemma

# 2. Python
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest tests/unit -q

# 3. HPE manuals -> data\raw\hpe\ (gitignored; public HPE docs, don't commit them), then load
python -m backend.ingest.loader          # sections + embeddings (~6 min with GPU)
python -m backend.graph.migrate          # migrations 002-008
python -m backend.graph.load             # Synapse seed: graph, veterans, emerging veterans, notes
python -m backend.graph.from_docs        # commands and messages from the manuals
python -m backend.graph.demo_learning    # demo learning history for the emerging veterans

# 4. run
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
cd frontend; Copy-Item .env.local.example .env.local; npm install; npm run dev   # http://localhost:3000
```
Use `127.0.0.1`, not `localhost`: on Windows `localhost` tries IPv6 first and adds about 2 s to every request.
Don't run `npm run build` while `npm run dev` is running.

## What's in here
| Path | What |
|---|---|
| `backend/pipeline/assistant.py` | Answer path (search, rerank, one cited Qwen answer) |
| `backend/watcher/` | Early warnings: `rules.py` (detectors, priority), `engine.py` (alerts, cards, replay) |
| `backend/integrations/` | Prognosis REST poller, MOMI export reader, alarm → graph mapping, demo stand-ins |
| `backend/knowledge_check.py`, `training.py` | Knowledge checks (graded, recorded) and the training sandbox (graded, not recorded) |
| `backend/knowledge.py`, `learning.py`, `documents.py` | Knowledge capture and sign-off, learning maps, document upload |
| `backend/graph/` | Seed loader, manual extraction, Synapse view, demo learning history |
| `backend/commands/`, `backend/simulator/` | Command catalog, guards, approval; simulated NonStop |
| `kg/seed/` | Fictional people, notes and curated links (YAML) |
| `data/replay/` | Demo incident feeds |
| `frontend/` | Operator console (Next.js); UI rules in `frontend/CLAUDE.md` |
| `docs/` | System design, API contract, integrations research, eval |
| `vault/` | Obsidian notes: code map, decisions (ADRs), requirements, the challenge brief |
