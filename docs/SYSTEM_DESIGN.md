# System design — NonStop Operator Copilot (CAIL challenge, Team #31)

Status: **draft for team review** · 2026-10-17 · supersedes the placeholder domain (pumps/P-201) in PLAN.md

## TL;DR
A local assistant that sits beside the operator's CAIL terminal session and does four things, all
**scoped to the node + release + subsystem the operator is actually on**:
1. **Ask** — answers in plain English with two kinds of citation: *which manual/section* and *which veteran*.
2. **Propose commands** — turns a question into commands from a verified catalog; risk-classified,
   dry-run on a simulator, executed only after approval.
3. **Warn early** — veterans' "this usually comes before a failure" patterns run against the live
   event/metric stream and fire *before* the failure, credited to the veteran.
4. **Capture** — every gap becomes a question to a veteran; the answer becomes cited knowledge.

Core bet (from CAIL + the literature): the failure mode is **context**, not eloquence. So context is
locked by software before retrieval, commands come from a catalog not free generation, and every
claim is traced to a document, a veteran, or live command output.

---

## 1. What we're solving (CAIL's brief → our scope)
| CAIL capability | Our feature | Depth for demo |
|---|---|---|
| Translate natural language into commands (with approval) | Command copilot (§6) | **Deep** |
| Understand & monitor system health | Watcher + health explainer (§7) | Medium |
| Preserve & apply expert knowledge | Veteran overlay, citations, capture loop (§5, §8) | **Deep** |
| Guide troubleshooting & decisions | Guided playbooks with next-step proposals | Medium |

Judged on: usefulness, feasibility, accuracy, UX, potential. Constraints: no production access, no
real customer data → **everything runs against a NonStop simulator with simulated telemetry**.

## 2. The context problem, in NonStop terms
"System A and B have the same buttons" maps to four real dimensions (sources in §12):

| Dimension | Examples | Why it bites |
|---|---|---|
| **Node** (Expand) | `\PROD`, `\DR` | Same command, `\node.` prefix or default node decides which machine it hits. Highest safety risk. |
| **Series / RVU** | L (NonStop X, x86), J (Itanium), H | Recovery steps differ by release (e.g. PUP vs SCF `REBUILDDFS`); Measure `CPU-BUSY-TIME` means different things on multi-core. |
| **Subsystem** | SCF STORAGE / EXPAND / TCPIP, PATHCOM, TMFCOM | Same verb (`STOP`, `STATUS`, `ABORT`) on different objects, very different effect. |
| **Personality** | Guardian vs OSS | File naming, process creation errors (Pathway 1159/1160). |

**Mapping onto our existing schema (no rewrite needed):**
`site_id` → **node** · `version_id` → **series/RVU** · `system_id` → **subsystem**.
Docs are usually all-nodes (`all_sites = true`); veteran heuristics are often node-specific
("on `\PROD` the nightly settlement batch pins the audit trail") — exactly the trap we want to show.

**Key insight for CAIL:** their emulator already *knows* which node and user the session is on.
So context comes **from the session, not from guessing the prompt**. The question can override it,
but a mismatch (asks about `\DR` while connected to `\PROD`) triggers a confirmation, never a guess.

## 3. Architecture
```
 ┌──────────────── CAIL 6530 session (simulated) ────────────────┐
 │ node=\PROD  user=OPS.NEWHIRE  screen text                      │
 └───────────────┬───────────────────────────────────────────────┘
                 │ session context + question
 ┌───────────────▼───────────────┐      ┌──────────────────────────────┐
 │ FastAPI                        │      │ NonStop simulator            │
 │  /chat      Ask pipeline       │◄────►│  nodes \PROD \DR, CPUs,      │
 │  /commands  Command copilot    │ dry  │  disks, TMF, Pathway, Expand │
 │  /alerts    Watcher            │ run  │  scenario engine + replay    │
 │  /capture   Teach / referral   │      │  emits EMS events + metrics  │
 └──────┬──────────────┬──────────┘      └──────────────┬───────────────┘
        │              │                                │ event/metric stream
 ┌──────▼──────┐ ┌─────▼───────────┐            ┌───────▼────────┐
 │ Postgres +  │ │ Local models    │            │ Watcher         │
 │ pgvector    │ │ Qwen 4B (glue)  │            │ trigger matcher │
 │ graph+docs+ │ │ embeddinggemma  │            │ (deterministic) │
 │ heuristics+ │ │ MiniCheck (CPU) │            └────────────────┘
 │ commands    │ └─────────────────┘
 └─────────────┘
```
All local. Jev stays off (see §10).

## 4. Knowledge model
One entity backbone, three overlays, all sharing entity ids (existing `sql/schema.sql`, extended):

**Backbone entities** (`entity.kind`): node, rvu/series, subsystem, object (cpu, disk volume,
process, line, server class, audit trail), **event** (EMS subsystem + number, e.g. `TMF 185`),
**metric** (e.g. `cpu-busy-time`, `audit-capacity-pct`), **command**.

**Overlays**
| Overlay | Table | Source | Cited as |
|---|---|---|---|
| Docs | `doc_chunk` | HPE manuals (Operator Messages, SCF Storage, TMF, Pathway, PEEK, Measure, TACL) — local only, `data/raw/` | 📘 *TMF Reference, ch.121 · L-series* |
| Veterans | `heuristic` | teach-mode interviews, incident debriefs, referral answers | 👤 *Maria R., Sr. Ops (24 yrs) · interview 2026-10-17 · 3 endorsements* |
| Commands | `command` (new) | catalog of verified templates, each linked to a doc section | 📘 + risk class |
| Live evidence | `command_run` (new) | output of approved/dry-run commands | 🖥 *`STATUS AUDITTRAIL, DETAIL` on `\PROD` at 02:14* |

**Edges** (existing + new): `about`, `symptom_of`, `fixed_by`, `precedes` (warning → failure),
`extends`/`contradicts`/`supersedes` (veteran ↔ doc), `disagrees_with` (veteran ↔ veteran, both kept),
`expert_in`, **`depends_on`** (Pathway server class → TMF → disk volume; for blast radius),
**`diagnosed_by`** (event/symptom → command).

## 5. Citations (non-negotiable)
Every claim the user sees is `{text, source_id, lane, verified}`; code drops claims without a valid
`source_id`, MiniCheck drops claims the source doesn't support. Source cards carry:
- **Doc:** manual title, part number, section, series/RVU it applies to, snippet.
- **Veteran:** name, role, years, *how* captured (interview / incident #/ referral answer), date,
  endorsements, last validated, and the relation to the docs ("contradicts TMF Ref §… on `\PROD`").
- **Live:** the command, node, timestamp, and the output line the claim rests on.

Lanes in the UI: 📘 documented · 👤 veteran insight · 🖥 observed now · ⚪ unknown → refer.
Veterans who disagree are shown side by side, attributed — never merged.

## 6. Command copilot (NL → command, safely)
Pipeline:
1. **Intent + slots** — LLM picks a *template* from the `command` catalog for the locked subsystem/RVU
   and fills slots (disk name, process, transid). It cannot emit free text commands. No template →
   say so and refer.
2. **Static safety check (deterministic code, not the LLM)**
   - Risk class from the **full parsed command**, not the verb. Trap: TACL `STATUS *, STOP` and
     `, FORCED` stop processes; `SCF ABORT DISK … FORCED` on the system disk is forbidden.
   - Classes: 🟢 read-only (`STATUS`, `INFO`, `STATS`, `PEEK`, `LISTOPENS`) · 🟠 state-changing
     (`START`, `STOP`, `ALTER`, `FREEZE/THAW`, `ALTPRI`, `SUSPEND`) · 🔴 critical (`ABORT TRANSACTION`,
     `DISABLE BEGINTRANS`, `STOP TMF`, `ABORT DISK`).
   - **Node guard**: target `\node` must equal the session node; otherwise blocked pending explicit confirm.
   - RVU guard: template must apply to the node's series/RVU.
3. **Dry run** on the simulator → expected output + **blast radius** from `depends_on` edges
   ("aborting this transaction backs out 1 settlement batch; Pathway class SETTLE-SC will retry").
4. **Approval** — 🟢 one click · 🟠 approve + type the node name · 🔴 approve + second approver (veteran on call).
5. **Execute (simulated)** → output parsed → becomes 🖥 live evidence for the next answer.
6. Everything logged (`answer_log`, `command_run`).

Why catalog-constrained: NL→Bash research shows free generation is unreliable; constraining to a grammar
and checking by execution raised accuracy up to 32% (Westenfelder, NAACL 2025); even the safest agents
failed 23.9% of high-stakes cases without oversight (ToolEmu, ICLR 2024).

## 7. Watcher (veterans' warning signals)
- Veteran triggers are stored as **patterns** on `heuristic` (`is_trigger = true`), scoped to node/RVU/subsystem:
  ```yaml
  id: maria:h7
  scope: {node: \PROD, series: L, subsystem: TMF}
  when:  # all within 30 min
    - event: TMF 185            # audit file pinned
      count: ">= 2"
    - metric: audit-capacity-pct
      trend: rising
      above: 60
  predicts: TMF 187 (audit trail critically full) → BEGINTRANS disabled
  call: "Check STATUS TRANSACTION for the nightly settlement batch before adding overflow volumes."
  why:  "Seen it every quarter-end since 2009; the batch holds one transaction open for hours."
  ```
- Matching is **deterministic** (rules over a sliding window). The LLM only writes the explanation.
- An alert = pattern + owner + lead time + cited fix + next commands as *proposals* (§6) + backup expert.
- **Back-testing:** replay recorded incidents through the watcher → "this pattern would have warned
  41 min before the failure in 3/3 past incidents". That number is the proof veterans' knowledge works.

## 8. Knowledge capture (keeping veterans' knowledge alive)
1. **Teach mode** — Critical Decision Method interview on a past incident: "What did you notice
   first? What did you check? When does this *not* apply? What do you see before it goes wrong?"
   The LLM drafts the heuristic/trigger; the veteran edits and signs. Nothing goes live unsigned.
2. **Referral loop** — bot can't answer → asks the right veteran with full context → their reply is
   one tap from becoming a cited heuristic owned by them.
3. **Incident debrief** — after an alert closes, the operator's actual commands + the veteran's
   comments become a draft playbook.
4. **Feedback** — ✓ endorse / ✗ wrong / ⚠ outdated on every claim; heuristics decay without re-validation.

## 9. Ask pipeline (reactive)
`context lock (session) → clarify if ambiguous → graph query (deterministic) ∪ filtered vector search
(context_where) → sufficiency gate → Qwen writes [{claim, source_id}] → MiniCheck → answer card`
(existing plan in `backend/pipeline/README.md`; unchanged except context dimensions in §2).

## 10. Models
| Role | Model | Where | Note |
|---|---|---|---|
| Glue text, slot filling | Qwen 4B via Ollama | GPU | constrained JSON output |
| Embeddings | embeddinggemma | CPU | |
| Claim verification | MiniCheck (770M) | CPU | |
| Sufficiency gate | prompt + threshold | GPU | |
| Trigger matching, risk class, node guard | **plain code** | CPU | never an LLM |

**Jev (System-1 typed model): not used.** Independent evidence is thin: one non-peer-reviewed benchmark
(arXiv 2609.37647) shows strong results on simple tasks but degradation on fine-grained labels, and a
critique (arXiv 2609.26758) shows typed outputs follow label names rather than definitions (AUC 93.8% →
23.2% when labels are swapped). At most a future cheap router; never a safety decision.

## 11. Demo scenario (end to end)
**02:10, quarter-end, `\PROD` (L-series). New operator alone; Maria (24 yrs) retired last month.**
1. Simulator replays quarter-end load. Watcher sees two `TMF 185` + audit capacity 62% and rising →
   ⚠ alert: *"Maria's pattern: audit trail will fill in ~40 min. Likely the settlement batch."* 👤📘
2. Operator: "why is the audit trail filling?" → context chip `\PROD · L · TMF` → answer with
   📘 TMF manual (pinned-file reasons) + 👤 Maria's heuristic + proposed 🟢 `TMFCOM STATUS AUDITTRAIL, DETAIL`.
3. Runs it → 🖥 output shows first pinned file, reason: long-running transaction.
4. Proposed 🟢 `STATUS TRANSACTION` → finds the old transid → proposed 🔴 `ABORT TRANSACTION \PROD(1).3.45678`
   with blast radius; needs second approver → pinged on-call veteran approves.
5. **Context trap:** switch session to `\DR`, ask the same question → Maria's heuristic does *not*
   apply (it's `\PROD`-scoped, no settlement batch on DR) → doc-only answer, or refer. Same words, different node, different answer.
6. **Gap → capture:** operator asks something nobody documented → refer to Raj → his answer saved as 👤 Raj's knowledge → ask again → instant cited answer.
7. Close on **knowledge-at-risk map**: "If Raj leaves, 11 warning patterns for `\PROD` Pathway have no other owner."

## 12. Creative angle (pick one or two)
1. **Operator flight simulator ("Drill mode")** — the simulator runs incident scenarios; new operators
   practice with the copilot; their path is scored against the veteran's path. Veterans play the same
   drill and their moves are captured as heuristics → training and knowledge capture in one loop.
   *Recommended: it reuses the simulator we need anyway, and it's memorable on stage.*
2. **Lead-time scoreboard** — every veteran pattern shows "warned N min early in K/K replays".
   Turns tacit knowledge into a measurable asset; credits the veteran.
3. **Knowledge-at-risk map** — topology of `\PROD` coloured by how many people hold each pattern
   (bus factor). The retirement problem in one picture.
4. **Contradiction radar** — every 👤 "the manual is wrong here" edge is a doc fix for CAIL's customers.
5. **Session-aware context from the emulator** — the product angle for CAIL specifically: the
   assistant reads the 6530 session's node/user, so it can't confuse `\PROD` with `\DR`.

## 13. Data we need (all simulated or public)
- **Docs:** HPE manuals (operator messages, SCF Storage, TMF, Pathway, PEEK, Measure, TACL). Many
  available versions are J/H-era; tag them honestly and treat L-series differences as unknown.
- **Command catalog:** ~25 templates from the verified list (TACL, SCF, PATHCOM, TMFCOM, PEEK, MEASCOM, FUP),
  each with risk class, scope and doc citation. Unverified syntax is flagged and kept out of the demo.
- **Simulated telemetry:** Measure field names (`cpu-busy-time`, `cpu-qtime`, `request-qtime`,
  `trans-backout-qtime`, …), PEEK page counters, TMF audit capacity %, EMS events by subsystem/number.
- **Scenarios (4):** audit trail filling (hero), disk mirror revive stalled, Pathway "NO SERVER AVAILABLE",
  CPU down + process-pair takeover.
- **Veterans (fictional):** 3 personas with ~15 heuristics total, incl. one disagreement and one
  "contradicts the manual".
- **Not modelled:** BASE24/Connex commands (proprietary, no public syntax) — shown only as generic link/approval-rate KPIs.

## 14. Changes to the repo
- Schema: new `command`, `command_run`, trigger pattern column on `heuristic`, edges `depends_on`, `diagnosed_by`; reinterpret system/version/site as subsystem/RVU/node (ADR-004).
- API: `/session` (context from emulator), `/commands/propose`, `/commands/{id}/dryrun`, `/commands/{id}/approve`, `/commands/{id}/execute`, `/simulator/scenario`, `/capture/*`; answer claims gain lane `live`.
- New modules: `backend/simulator/`, `backend/commands/` (catalog, parser, risk, guards), `backend/watcher/`.
- Eval: add command items (right template, right risk class, node guard holds) and replay lead time.

## 15. Risks & assumptions
- Manual versions predate some L-series RVUs → answers state the series they're sourced from.
- Simulator fidelity is approximate; we claim the *workflow*, not NonStop-accurate internals.
- Qwen 4B slot filling may miss → catalog + parser catch malformed commands; no template → refer.
- Veterans' buy-in: credit and lead-time stats are the incentive; nothing published unsigned.

## 16. Research behind the decisions
| Decision | Evidence |
|---|---|
| Lock version/system before retrieval | VersionRAG (arXiv 2510.08109): 90% vs 58% plain RAG on version-sensitive Qs; Ciena multi-release QA (SANER 2026, arXiv 2601.02345): +16.5 pts |
| Software asks when ambiguous | AMBROSIA (NeurIPS 2024, arXiv 2406.19073): strong LLMs fail to notice ambiguity |
| Typed graph under RAG | KG data layer for industrial ops (arXiv 2605.26874): 65% → 82–83%, deterministic queries higher |
| Runbooks as structured, versioned steps | AutoTSG (arXiv 2205.13457); LLexus (SIGOPS OSR 2024); Nissist (arXiv 2402.17531) |
| Alert-type handlers before the LLM | RCACopilot (EuroSys 2024, arXiv 2305.15778) |
| Query/command recommendation from incidents | Xpert (ICSE 2024, arXiv 2312.11988) |
| Constrained command generation + execution check | Westenfelder (NAACL 2025); IBM NL2Bash/PowerShell remediation (arXiv 2405.06807); InterCode (NeurIPS 2023, arXiv 2306.14898) |
| Human approval mandatory | ToolEmu (ICLR 2024, arXiv 2309.15817) |
| Sufficiency gate | Sufficient Context (ICLR 2025, arXiv 2411.06037) |
| Claim verification | MiniCheck (EMNLP 2024, arXiv 2404.10774) |
| Expert elicitation | Critical Decision Method (Klein et al., IEEE SMC 1989); LLM-extracted expert knowledge (arXiv 2608.07488, preprint) |
| Explaining events/logs | LogPrompt (ICPC 2024, arXiv 2308.07610) |
| Competitor | IR "Iris for HPE NonStop" (Jun 2026): NL Q&A over Prognosis telemetry, advisory only — we differ by session context, command safety, veteran knowledge |

NonStop domain sources: HPE NonStop Technical Library (docId a00099017en_us — a link index to L/J/H
manual libraries); Operator Messages manual (TMF ch.121, Pathway ch.78, Expand ch.36, Disk ch.21, CPU ch.17);
SCF Storage, TMF, Pathway, PEEK, Measure (523324-013), TACL (429513-017) references; comforte TACL cheat sheet;
CAIL Suite (cail.com).
