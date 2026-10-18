# System design — NonStop Copilot (CAIL challenge, Team #31)

Version 3.1 · 2026-10-18 · adds monitoring-tool connectors, alert priority, roles, knowledge checks and the training sandbox. Brief: [vault/design/challenge brief.md](../vault/design/challenge%20brief.md).

## 1. Problem and goal
CAIL's customers run banking, payments and telecom on HPE NonStop. Experienced operators are retiring (about 5 of 20
at one bank in six months), and the manuals miss their practical judgment. Goal: **get Emerging Veterans (juniors)
to Veteran level faster.** Warn them before failures, explain what to do and why with citations, and capture what
the veterans know before they leave.

| Brief capability | Our feature | Status |
|---|---|---|
| 1. Natural language → commands, approved | Command catalog, risk classes, node/series guards, dry-run, veteran-only 1- or 2-person approval | Built |
| 2. Understand & monitor health | Prognosis/MOMI connectors → watcher (tool alarms, veteran patterns, graph chains, trends); High/Medium/Low priority; alert cards; health charts | Built (tested against stand-ins) |
| 3. Preserve expert knowledge | Teach chat, owner sign-off, automatic graph links, Synapse | Built |
| 4. Guide troubleshooting | Cited answers, "check first" commands, risks, what usually comes next, who to call | Built |
| Training speed (CAIL steer) | Learning maps, starting levels, knowledge checks (`knows` links), guided training sandbox, Emerging Veterans' findings | Built (one guided scenario) |

## 2. The context problem ("system A and B have the same buttons")
The same command means different things depending on four things:

- **node:** `\PROD` / `\DR`
- **release series:** L, J, H
- **subsystem:** TMF, Pathway, SCF Storage, …
- **personality:** Guardian / OSS

Every manual section, note, alert and command carries a context fingerprint (`system_id` = subsystem,
`version_id` = series, `site_id` = node). A hard filter is applied in SQL before any ranking. A note signed for
`\PROD` is never retrieved, alerted on or cited in a `\DR` session; tested with 0 leaks on the 60-question set.
Manuals apply to all series and carry their edition, so an answer can say "the manual citation is from the
H-series edition".

## 3. Components
```mermaid
flowchart TB
  subgraph UI["Operator console (Next.js)"]
    OV["Overview / Investigations<br/>alert cards, health"]
    AS["AI Assistant<br/>cited answers, commands"]
    SY["Synapse<br/>live graph"]
    LM["Learning map"]
    KN["Knowledge<br/>Teach, sign-off, documents"]
  end
  subgraph API["FastAPI (local)"]
    A1["assistant.py<br/>search, rerank, answer"]
    A2["watcher/<br/>rules.py, engine.py"]
    A3["knowledge.py<br/>capture, sign, auto-link"]
    A4["learning.py"]
    A5["documents.py + from_docs.py"]
    A6["commands/ + simulator/"]
  end
  subgraph IN["Event sources (one normalised event)"]
    R["Replay feeds<br/>data/replay"]
    P["Prognosis REST poller<br/>integrations/prognosis.py"]
    M["MOMI export reader<br/>integrations/momi.py"]
  end
  subgraph DB["Postgres 16 + pgvector = Synapse"]
    T1["entity / edge<br/>graph"]
    T2["doc_chunk<br/>sections + vectors"]
    T3["heuristic<br/>veteran notes + rules"]
    T4["person<br/>veteran / emerging"]
    T5["answer_log, self_level"]
    T6["alert"]
  end
  subgraph MOD["Models (Ollama, GPU)"]
    Q["Qwen 3.5 4B"]
    E["embeddinggemma"]
    X["MiniLM cross-encoder (CPU)"]
  end
  AS --> A1
  OV --> A2
  KN --> A3
  KN --> A5
  LM --> A4
  SY --> T1
  AS --> A6
  R --> A2
  P --> A2
  M --> A2
  A1 --> T2
  A1 --> T3
  A1 --> Q
  A1 --> E
  A1 --> X
  A2 --> T1
  A2 --> T3
  A2 --> T6
  A3 --> T3
  A3 --> T1
  A4 --> T5
  A5 --> T2
  A5 --> T1
```

## 4. Flows

### 4.1 Ask (AI Assistant)
1. Context comes from the session's node and series. If the question names the other node, it asks which one.
2. Retrieval:
   - hybrid search over `doc_chunk` (vector + IDF keyword, RRF) inside the context filter, 20 candidates;
   - vector search over signed notes for this node, 6 candidates.
3. The MiniLM cross-encoder reranks the candidates. Final order is RRF of search rank and rerank rank; nothing is
   dropped on score alone. Top 5 sources, 1,000 characters each.
4. One Qwen call with the last 3 turns, so follow-ups work. Rules for the answer:
   - cite `[n]`;
   - name the veteran and keep every "do not";
   - use a source only if it answers the question;
   - otherwise say it isn't covered, or ask one short question;
   - about 120 words.
5. Citations are mapped back to sources. "Who knows this" lists **veterans only**, ranked by `expert_in` weight
   and availability. Proposed commands come from the catalog.
6. Logged to `answer_log` per user. This feeds the learning map.

### 4.2 Warn (watcher)
```mermaid
sequenceDiagram
  participant S as Source (replay / Prognosis / MOMI)
  participant W as Watcher
  participant G as Synapse
  participant U as Console
  S->>W: event {node, kind, entity, value, ts}
  W->>W: buffer (3 h), per node
  W->>G: approved warning patterns for this node (heuristic.rule)
  W->>W: pattern rule? graph chain (precedes)? metric trend?
  W->>G: store alert (kind, entity, pattern, lead_min, evidence)
  U->>W: GET /alerts?node=
  W->>G: notes (do / why / not when), manual sections, diagnosed_by commands, backup veteran
  W-->>U: alert card
```
- **Rules** are small JSON shapes stored on the veteran's note:
  - `count`: event X ≥ N times in W minutes, optionally with a metric above a threshold and rising;
  - `stalled`: a metric unchanged for N minutes.
- **Trend:** a straight-line projection to a hard limit; warns within 60 min, critical within 20.
- **De-duplication:** one open card per (kind, key, node). A veteran's card closes and suppresses the chain and
  trend cards for the same event or metric.
- **Tool alarms** (`backend/integrations`):
  - the connector reads the node and the quoted message number ("TMF 185");
  - `mapping.entity_for` puts the alarm on a curated event, else on the manual's own message entity, else on a metric
    or subsystem;
  - the card is shown at once, and the alarm is also fed on as an event, so patterns and chains see it;
  - an unreadable node is dropped, never guessed.
- **Priority** (`rules.priority`): High / Medium / Low from points, with the reasons listed on the card:
  - +2 for `\PROD`;
  - +2 if it is, or leads to, a transaction-stopping event;
  - +1 if a veteran's pattern matched;
  - +1 if failure is expected within 30 min;
  - +1 if the tool marks it critical.
- **No LLM** in detection or priority: explainable, fast and testable (`tests/unit/test_watcher_rules.py`,
  `test_integrations.py`).

### 4.3 Capture and sign (Veterans)
1. Teach chat: the veteran talks, Qwen asks one follow-up at a time, then drafts trigger / do / why / not-when plus
   node and subsystem. The veteran edits it and saves a **draft**. Drafts are never retrieved.
2. Only the owner can sign (403 otherwise). Signing does four things:
   - embeds the note;
   - adds `about` links to the subsystem and to the commands, events and objects the text names, inside the
     same subsystem only;
   - adds `applies_to` the node;
   - adds `expert_in` +1 for the owner.
3. The system suggests related manual sections; the veteran marks each `extends` or `contradicts`.
4. Emerging Veterans can enter "Raj told me…" or "I found…" with `entered_by` = themselves. It stays a draft until
   that veteran signs it.

### 4.4 Learn (Emerging Veterans)
- The learning map comes from `answer_log`. Cited sections and notes are followed along their `about` links to
  the graph nodes "touched". Coverage = touched / nodes per subsystem.
- It shows the veterans learned from, what has never been touched, recent questions, and the starting level per
  subsystem (`self_level`, self-reported, never used to answer).
- **Knowledge check** (`backend/knowledge_check.py`):
  - a signed note becomes "<trigger>. What would you do?";
  - Qwen grades the answer against do / why / not-when (0 missed, 1 partly, 2 got it) and shows the veteran's answer;
  - results go to `check_result`, and a pass adds `knows` (person → note) to Synapse and counts as "Demonstrated".
- **Training sandbox** (`backend/training.py`, Training Simulator → Audit trail filling): a guided exercise.
  - Steps: brief → first check (multiple choice) → simulated command output → decision graded against the notes →
    debrief.
  - It uses its own simulator and stores nothing.
- **Roles:**
  - Veterans: `\PROD`, approve commands, own and sign notes.
  - Emerging Veterans: `\DR`; can ask, dry-run, take checks and practise, but approval is refused by the API.

### 4.5 Ingest documents
- Upload a PDF or text file. It is split into sections and embedded, and added to `doc_chunk` with its edition.
- `from_docs` then extracts commands and numbered messages from section titles (deterministic, no LLM), links
  them to their section and subsystem, and removes stale ones.
- Re-uploading shows added / changed / removed sections and flags notes tied to changed sections "needs review".

### 4.6 Commands
- The catalog (`kg/seed/entities.yaml`) holds each template's risk class:
  - `read_only`: one click;
  - `state_changing`: the operator types the node;
  - `critical`: a second approver.
- Guards: node match and supported series.
- Dry-run shows expected output and blast radius. Execute runs on the simulator only; the output becomes a "live"
  citation.

## 5. Data model (Synapse)
| Table | Holds | Notes |
|---|---|---|
| `entity` | subsystems, series, nodes, events, commands, objects, metrics | 1,718 (1,662 extracted from manuals) |
| `edge` | about, applies_to, symptom_of, diagnosed_by, fixed_by, precedes, depends_on, extends, contradicts, disagrees_with, expert_in, mentions | each cites a `source_id`; `created_by` = seed / auto / auto-docs / human |
| `doc_chunk` | 3,777 manual sections, 7 manuals, 768-d vectors | context columns + edition |
| `heuristic` | veteran notes and warning patterns | owner, scope, status, provenance, `rule`, vector |
| `person` | 5 veterans, 10 emerging veterans | `level` |
| `answer_log`, `self_level` | per-user questions and citations; starting levels | learning maps |
| `alert` | watcher alerts | kind, node, entity, pattern, lead time, evidence |

## 6. Integrations (existing monitoring tools)
One normalised event (`POST /events`): `{node, kind: event|metric, entity, value, tool, text, ts}`. The demo replays
recorded feeds through the same path.

| Tool | How it exposes alerts | Our adapter | Status |
|---|---|---|---|
| IR Prognosis | REST API: admin-defined PQL datasets as JSON over HTTPS, e.g. open problems (`/Prognosis/Rest/v1/data/<id>`); SNMP traps | `Poller`: every 10 s, configurable columns, basic auth (`PROGNOSIS_URL/USER/PASSWORD`) | Built; tested against a local stand-in |
| BlackWood MOMI | No API. Alarms → email, EMS, log; scheduled history/log exports | `InboxReader`: alarm-template blocks and TAB log lines from `MOMI_INBOX`, every 5 s | Built; tested against sample exports |
| Third tool | Unknown | Ask CAIL | — |

The alarm-name → graph-node mapping is done in advance, so an incoming alert lands on a node with its notes and
manual sections already linked. Details: [INTEGRATIONS_PROGNOSIS_MOMI.md](INTEGRATIONS_PROGNOSIS_MOMI.md).

## 7. Models and performance
- **Qwen 3.5 4B** (Ollama, GPU, kept loaded for 60 min). Answers and Teach drafts only; it is never used for
  detection, risk or guards.
- **embeddinggemma** for embeddings. **ms-marco MiniLM** cross-encoder for reranking (0.7 s on CPU).
- Latency: 5–8 s per answer. The first answer after a model reload takes about 25 s. Use `127.0.0.1`, not
  `localhost` (IPv6 adds about 2 s on Windows).
- Eval (60 independent questions): 80% correct behaviour, 89–93% key facts, 2% false refusals, 0 context leaks,
  0 unsafe inversions.

## 8. Safety and trust
- Advisory only: there is no path to a real system, and commands run on the simulator after approval.
- Every claim has a source: a manual section with its edition, or a named veteran with when and how it was captured.
  It says when something isn't covered.
- Unsigned knowledge is never used. Contradictions with the manual are shown, not hidden.
- Detection, risk classes and guards are plain code.

## 9. Limitations and next steps
| Limitation | Next step |
|---|---|
| No incident history, so no "warned early in X of Y" | Record alerts and outcomes; backtest rules |
| Graph links come from section titles only (2,645 sections unlinked) | Body-text "mentions" links (deterministic) |
| Answer path uses graph links only for experts | Follow one hop from named nodes into extra sources |
| Connectors tested only against stand-ins | Point them at a customer's Prognosis URL / MOMI export folder; adjust Prognosis column names |
| One guided training scenario | Add guided steps for CPU down (the brief's scenario), revive stall and Pathway |
| 4B model quality | A larger local model if hardware allows |
