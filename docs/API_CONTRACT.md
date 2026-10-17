# API contract (lock Friday night — UI builds against these mocks)

Base: `http://localhost:8000`

## POST /chat
Request:
```json
{ "user_id": "newhire1", "question": "pump on line 2 is surging, what do I check?",
  "context_override": { "system": null, "version": null, "site": null },
  "ablation": 4 }
```
`ablation` is optional (default `4`), used by the eval: `1` plain vector RAG · `2` + context resolution/filter ·
`3` + sufficiency gate · `4` + MiniCheck verifier (full pipeline). The UI never sends it.

Response is ONE of three `type`s:

### type = "answer"
```json
{
  "type": "answer",
  "answer_log_id": 123,
  "context": { "system": "sys:P-201", "version": "ver:P-201:v3", "site": "site:plant-2",
               "display": "P-201 · v3 · Plant 2", "confidence": 0.91 },
  "claims": [
    { "text": "Check valve Y before replacing the pressure sensor.",
      "lane": "veteran", "source_id": "ravi:h12", "verified": true, "score": 0.94 },
    { "text": "Normal operating pressure is 4.2–4.8 bar.",
      "lane": "doc", "source_id": "doc:P-201-manual:4.2", "verified": true, "score": 0.97 }
  ],
  "sources": [
    { "id": "doc:P-201-manual:4.2", "kind": "doc", "title": "P-201 Manual §4.2", "snippet": "..." },
    { "id": "ravi:h12", "kind": "heuristic", "owner": "Ravi", "why": "Seen 30+ times on v3 units...",
      "provenance": "interview:2026-10-17", "relation": "contradicts:doc:P-201-manual:4.3" }
  ],
  "dropped_claims": 1,
  "experts": [ { "id": "ravi", "name": "Ravi", "reason": "12 resolved cases on P-201 v3", "active": true } ]
}
```
`lane`: `doc` (🟢) | `veteran` (🟡).
`answer_log_id`: id of the `answer_log` row for this response; the UI sends it back on `/feedback`.

### type = "clarify"
```json
{ "type": "clarify", "question": "Which unit — P-201 (line 2) or P-305 (line 4)?",
  "options": [ { "label": "P-201 · v3", "value": {"system":"sys:P-201","version":"ver:P-201:v3"} },
               { "label": "P-305 · v1", "value": {"system":"sys:P-305","version":"ver:P-305:v1"} } ] }
```
UI resends `/chat` with `context_override` set. `clarify` has no `context` (it is unresolved by definition).

`context` has the same shape in `answer` and `refer`: `system`, `version`, `site` (entity ids), `display`, `confidence`.

### type = "refer"
```json
{ "type": "refer", "reason": "No verified answer for P-305 v1.",
  "context": { "system": "sys:P-305", "version": "ver:P-305:v1", "site": "site:plant-2",
               "display": "P-305 · v1 · Plant 2", "confidence": 0.88 },
  "experts": [ { "id": "ravi", "name": "Ravi", "reason": "12 resolved cases", "active": false },
               { "id": "priya", "name": "Priya", "reason": "Doc owner", "active": true } ] }
```

## POST /refer
```json
{ "expert_id": "priya", "question": "...", "context": { ... }, "from_user": "newhire1" }
→ { "referral_id": "q88", "status": "sent" }
```

## POST /refer/{referral_id}/answer   (veteran answers)
```json
{ "answer": "On P-305 it's the inlet strainer.", "save_as_knowledge": true }
→ { "heuristic_id": "priya:h3", "status": "draft" }
```

## POST /feedback
```json
{ "answer_log_id": 123, "source_id": "ravi:h12", "action": "endorse|wrong|outdated", "user_id": "ravi" }
→ { "feedback_id": 9, "status": "recorded" }
```
`answer_log_id` comes from the `answer` response.

## GET /alerts   (watcher, poll every 2s or SSE /alerts/stream)
```json
[ { "id": "al-7", "ts": "2026-10-18T14:02:00Z", "entity": "P-201 · v3",
    "pattern_id": "ravi:h12", "owner": "Ravi", "probability": 0.87,
    "message": "Early sign of valve Y failure", "fix_claims": [ ...same shape as claims... ],
    "backup_expert": { "id": "priya", "name": "Priya" } } ]
```

## POST /watcher/replay
```json
{ "log_file": "incident_2025_03.csv", "speed": 10 } → { "status": "running" }
```

## GET /risk   (bus-factor dashboard — end-of-demo slide)
```json
[ { "entity": "P-201 · v2", "experts": ["ravi"], "heuristics": 9, "doc_coverage": 0.3, "risk": "high" } ]
```

---
# v2 additions — NonStop copilot (docs/SYSTEM_DESIGN.md). Draft, locked once UI + backend agree.

Context dimensions (ADR-004): `system` = subsystem (`sub:TMF`), `version` = series/RVU (`rvu:L`),
`site` = node (`node:PROD`). `display` e.g. `"\\PROD · L-series · TMF"`.

## Claims: lanes and sources (extends /chat `answer`)
`lane`: `doc` (📘) | `veteran` (👤) | `live` (🖥 command output).
```json
"sources": [
  { "id": "doc:TMF-Reference:ch121.185", "kind": "doc", "title": "TMF Reference Manual",
    "part_number": "TMF-REF", "section": "Event 185 — audit file pinned", "applies_to": "L/J-series · all nodes",
    "snippet": "..." },
  { "id": "maria:h7", "kind": "heuristic", "owner": "maria", "owner_name": "Maria Rossi",
    "owner_role": "Sr. NonStop Operator", "years": 24, "captured_via": "interview", "captured_at": "2026-09-30",
    "endorsements": 3, "last_validated": "2026-09-30", "scope": "\\PROD · L-series · TMF",
    "why": "Quarter-end settlement batch holds one transaction open for hours.",
    "relation": "extends:doc:TMF-Reference:ch121.185" },
  { "id": "run:c42", "kind": "live", "command": "TMFCOM STATUS AUDITTRAIL, DETAIL", "node": "\\PROD",
    "ts": "2026-10-17T02:14:05Z", "excerpt": "Active audit trail capacity used: 71%" }
]
```

## GET /session  (from the CAIL emulator session; simulated)
```json
{ "node": "node:PROD", "node_display": "\\PROD", "series": "rvu:L", "user": "OPS.NEWHIRE",
  "nodes_available": [ {"id":"node:PROD","display":"\\PROD"}, {"id":"node:DR","display":"\\DR"} ] }
```
## POST /session  `{ "node": "node:DR" }` → same shape (switch node; UI shows it loudly).

## POST /commands/propose
```json
{ "question": "what's pinning the audit trail?", "context": { "system": "sub:TMF", "site": "node:PROD", "version": "rvu:L" } }
→ { "proposals": [
    { "id": "cmd-17", "template_id": "tmfcom.status_audittrail_detail",
      "command": "TMFCOM STATUS AUDITTRAIL, DETAIL", "node": "\\PROD",
      "risk": "read_only",                       // read_only | state_changing | critical
      "explanation": "Shows capacity used and the first pinned file with its reason.",
      "source_id": "doc:TMF-Reference:ch4.status-audittrail",
      "guards": { "node_match": true, "rvu_ok": true },
      "approval": { "required": "one_click" }    // one_click | type_node | second_approver
    } ],
    "no_template": false }
```
`no_template: true` → UI shows a refer card instead.

## POST /commands/{id}/dryrun
`→ { "id": "cmd-17", "expected_output": "...", "blast_radius": [ {"entity":"Pathway SETTLE-SC","effect":"will retry 1 batch"} ], "warnings": [] }`

## POST /commands/{id}/approve
`{ "user_id": "newhire1", "typed_node": "\\PROD", "second_approver": null }` → `{ "status": "approved" | "needs_second_approver" | "rejected", "reason": "" }`

## POST /commands/{id}/execute   (simulated; only after approve)
`→ { "run_id": "run:c42", "output": "...", "ts": "...", "source_id": "run:c42" }`

## GET /alerts  (v2 shape)
```json
[ { "id": "al-7", "ts": "2026-10-17T02:10:00Z", "node": "\\PROD", "subsystem": "TMF",
    "pattern_id": "maria:h7", "owner": "maria", "owner_name": "Maria Rossi",
    "severity": "warning", "lead_time_min": 40,
    "message": "Audit trail on track to fill in ~40 min — Maria's quarter-end pattern",
    "evidence": [ {"event": "TMF 185", "count": 2}, {"metric": "audit-capacity-pct", "value": 62, "trend": "rising"} ],
    "fix_claims": [ ...claims... ], "next_commands": [ ...proposals... ],
    "backtest": { "hits": 3, "of": 3, "avg_lead_min": 41 },
    "backup_expert": { "id": "raj", "name": "Raj Patel" } } ]
```

## GET /metrics?node=node:PROD&window=60m   (simulated telemetry for the health panel)
`→ { "series": [ { "metric": "audit-capacity-pct", "points": [[ "2026-10-17T01:10:00Z", 41 ], ...] }, ... ] }`

## POST /simulator/scenario  `{ "scenario": "audit_trail_fill" | "disk_revive_stall" | "pathway_no_server" | "cpu_down", "speed": 10 }` → `{ "status": "running" }`

## Expert objects (v2) — used in answer/refer `experts` and alert `backup_expert`
Referrals are **reference only** for now: the UI shows who to talk to, it does not send messages.
```json
{ "id": "raj", "name": "Raj Patel", "active": true, "availability": "on_call",
  "role": "NonStop Systems Specialist", "team": "Production Operations", "years": 15,
  "expertise": ["Pathway", "TMF"], "reason": "Resolved 12 TMF/Pathway incidents on \PROD and \DR",
  "contact": "ext. 4417 · on-call pager 555-0142" }
```
`availability`: `on_shift` | `on_call` | `off_shift` | `retired`. All fields beyond id/name/reason/active are optional.
`POST /refer` stays in the contract for the later capture loop but the UI doesn't call it.

---
# v3 additions — knowledge capture, documents, persons
Implemented in `backend/knowledge.py` and `backend/documents.py`. Errors are `{"detail": "..."}` (403 wrong signer, 404 unknown id,
409 wrong state, 422 bad input). `/commands/*` is NOT part of v3 (owned by the command-workflow branch).

## GET /persons
`→ [ { "id": "lena", "name": "Lena Kowalski", "role": "...", "team": "...", "years": 19, "expertise": [...], "availability": "on_shift", "active": true } ]`

## POST /persons
`{ "id": "omar", "name": "Omar Haddad", "role"?, "team"?, "years"?, "expertise"?: [...], "availability"?: "on_shift"|"on_call"|"off_shift"|"retired", "contact"? }`
→ the person (as GET, plus `contact`). 409 if the id exists, 422 on a bad id/availability. The new person can own, teach and sign notes at once.

## GET /knowledge?status=draft|approved|retired
`→ [ Note ]` (all statuses when omitted). Note:
```json
{ "id": "lena:h5", "owner_id": "lena", "owner_name": "Lena Kowalski", "entered_by": "lena", "kind": "note",
  "trigger_text": "...", "call_text": "...", "why_text": "...", "not_when_text": "...", "node": "DR",
  "subsystem": "sub:SCF-STORAGE", "status": "approved", "captured_via": "interview", "captured_at": "2026-10-17",
  "signed_by": "lena", "signed_at": "2026-10-17", "needs_review": false,
  "links": [ { "rel": "about", "dst": "sub:SCF-STORAGE", "created_by": "auto" } ] }
```

## POST /knowledge  → Note (status `draft`)
`{ "owner_id", "entered_by", "kind": "note"|"warning_pattern", "trigger_text", "call_text", "why_text", "not_when_text", "node": "PROD"|"DR"|"ALL", "subsystem": "sub:TMF" }`
`owner_id` must be a person; `entered_by` can be any user id (a junior writing down "Raj told me"). Only the owner can sign.
`captured_via` = `interview` if `entered_by == owner_id`, else `referral`. Id = `<owner>:h<N>`. A draft is never retrieved.

## POST /knowledge/{id}/approve  `{ "signed_by": "lena" }`
`signed_by` must equal the note's owner (else 403). Embeds the note and auto-links (code, no LLM): `about` the subsystem and the graph
entities the text names (same subsystem), `applies_to` the node(s), owner's `expert_in` weight +1. The note is usable by `/chat` at once.
`→ { "note": Note, "auto_links": [ { "rel", "dst" } ], "suggested_sections": [ { "id": "doc:...", "section", "snippet" } ] }`

## POST /knowledge/{id}/link  `{ "doc_id": "doc:...", "rel": "extends" | "contradicts" }`  → Note
Human-confirmed link to a manual section (`created_by = 'human'`). `contradicts` makes the answer show the "Veteran contradicts the manual"
box, but only when that section is itself cited in the answer.

## POST /knowledge/{id}/retire → Note (status `retired`, no longer retrieved)

## POST /documents  (multipart: `file` .pdf|.txt, `title`, `subsystem`, `edition`)
Same title = same document. Unchanged chunks keep their id, changed chunks are replaced, vanished ones get `valid_to = today` and are no longer
retrieved. Approved notes linked to a changed/removed chunk get `needs_review: true`. An unknown `subsystem` name creates a `system` entity.
`→ { "key", "title", "edition", "subsystem", "subsystem_created", "added", "changed", "unchanged", "removed", "changed_ids": [], "removed_ids": [], "notes_flagged": ["raj:h9"] }`

## GET /documents
`→ [ { "key", "title", "edition", "subsystem", "chunks", "removed", "last_loaded" } ]`

## `/chat` additions
- Veteran claim: `"needs_review": true` when the note's manual section changed since signing (UI: "manual changed since this note was signed - needs re-check"). Source card has the same field.
- `claims[].contradicts` is only set when that doc section is among the answer's cited sources.
- `debug.note_sims` / `debug.notes_below_cutoff`: cosine of the notes offered to / withheld from Qwen.

## GET /learning/users  → `[ { "user_id": "newhire1", "questions": 40, "last_seen": "2026-10-17 12:00:00+00" } ]`
Operators seen in `answer_log` or `self_level` (a new junior who only set a starting level shows with 0 questions), most questions first; test/script ids (`eval`, `conncheck`, `check`, `t`, `test`, `cli`) are left out.

## GET /learning/{user_id}  → learning map (404 only for a test id; a brand-new junior gets an empty map)
What the operator has *encountered* through questions, not a test of knowledge.
```json
{ "user_id": "newhire1",
  "totals": { "questions": 40, "subsystems_touched": 7, "subsystems_total": 7, "notes_seen": 8, "sections_cited": 36,
              "entities_touched": 17, "entities_total": 44, "coverage": 0.39 },
  "subsystems": [ { "id": "sub:TMF", "name": "TMF (TMFCOM)", "questions": 20, "sections_cited": 11,
                    "notes": [ { "id": "maria:h7", "owner": "Maria Rossi" } ],
                    "entities_touched": 8, "entities_total": 15, "coverage": 0.53, "last_seen": "2026-10-17 12:00:00+00" } ],
  "veterans": [ { "id": "maria", "name": "Maria Rossi", "notes": 4 } ],
  "gaps": { "subsystems": ["FUP"], "events": [ { "id": "evt:TMF-187", "name": "...", "subsystem": "TMF (TMFCOM)" } ] },
  "recent": [ { "ts": "...", "question": "...", "outcome": "answer", "subsystem": "TMF (TMFCOM)" } ] }
```
Also `"self_levels": { "sub:TMF": "some" }`: the junior's own starting level (self-reported, never used to answer).

## PUT /learning/{user_id}/self  `{ "levels": { "sub:TMF": "new"|"some"|"confident" } }` → the learning map
422 on an unknown subsystem or level. Upserts; leaving a subsystem out keeps its old level.

Entities touched = entities the cited veteran notes and manual sections are linked to (`about` edges); coverage = touched / entities of that subsystem.

## POST /knowledge/teach  (Teach chat)
`{ "owner_id": "lena", "messages": [ { "role": "veteran"|"assistant", "text": "..." } ], "node_hint"?: "DR", "subsystem_hint"?: "sub:TMF" }`
One Qwen call per turn. `→ { "type": "question", "text": "..." }` (one short follow-up) or
`{ "type": "draft", "draft": { "trigger_text", "call_text", "why_text", "not_when_text", "node": "PROD"|"DR"|"ALL", "subsystem": "sub:...", "kind": "note"|"warning_pattern" } }`.
After 3 assistant questions it drafts with what is known (unknown subsystem = `""`, node defaults to `ALL`; the editable form fixes them).
Code guards: a text field not grounded in the veteran's own words is emptied, never invented; `subsystem` must be an existing `sub:*` entity.
Nothing is saved: the UI posts the (edited) draft to `POST /knowledge` (entered_by = owner), then the normal approve flow signs and auto-links.

## v5: watcher (early warnings) — backend/watcher
- `POST /events` `{node, kind: "event"|"metric", entity: "evt:TMF-185"|"met:audit-capacity-pct", value?, tool?, text?, ts?}` → `{alerts: [ids]}`.
  The one entry point for any source (replay, Prognosis REST poller, MOMI export reader).
- `GET /alerts?node=node:PROD` (default: session node) → `[Alert]` (frontend `Alert` type). `kind`: `pattern` (a veteran's
  warning-pattern note with a `rule` fired; `owner_name`, `pattern_id`, `lead_time_min` from the rule) | `chain` (graph
  `precedes`: this event usually comes before worse) | `trend` (metric projected to hit its limit within 60 min).
  `fix_claims` = the linked veteran notes verbatim (do / why / not when) + manual sections; `next_commands` = catalog
  proposals for the `diagnosed_by` commands (normal approval flow); `backtest` is null (no incident history yet).
  A pattern card replaces the chain/trend cards about the same event or metric.
- `POST /alerts/{id}/ack` dismisses. `GET /watcher/replays`, `POST /watcher/replay {name, speed}` plays `data/replay/<name>.jsonl`.
- `POST /simulator/scenario` also starts the matching replay (audit_trail_fill, disk_revive_stall, pathway_no_server).
- `GET /metrics`: a metric the watcher has received replaces the simulator curve, so charts and alerts agree.
- `POST /knowledge` accepts `rule` (warning_pattern only), e.g. `{"type":"count","event":"evt:TMF-185","count":2,"window_min":30,
  "metric":"met:audit-capacity-pct","above":60,"rising":true,"lead_min":40}` or `{"type":"stalled","metric":"...","minutes":10}`.
