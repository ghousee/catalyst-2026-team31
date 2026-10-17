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
`site` = node (`node:PROD`). `display` e.g. `"\PROD · L-series · TMF"`.

## Claims: lanes and sources (extends /chat `answer`)
`lane`: `doc` (📘) | `veteran` (👤) | `live` (🖥 command output).
```json
"sources": [
  { "id": "doc:TMF-Reference:ch121.185", "kind": "doc", "title": "TMF Reference Manual",
    "part_number": "TMF-REF", "section": "Event 185 — audit file pinned", "applies_to": "L/J-series · all nodes",
    "snippet": "..." },
  { "id": "maria:h7", "kind": "heuristic", "owner": "maria", "owner_name": "Maria Rossi",
    "owner_role": "Sr. NonStop Operator", "years": 24, "captured_via": "interview", "captured_at": "2026-09-30",
    "endorsements": 3, "last_validated": "2026-09-30", "scope": "\PROD · L-series · TMF",
    "why": "Quarter-end settlement batch holds one transaction open for hours.",
    "relation": "extends:doc:TMF-Reference:ch121.185" },
  { "id": "run:c42", "kind": "live", "command": "TMFCOM STATUS AUDITTRAIL, DETAIL", "node": "\PROD",
    "ts": "2026-10-17T02:14:05Z", "excerpt": "Active audit trail capacity used: 71%" }
]
```

## GET /session  (from the CAIL emulator session; simulated)
```json
{ "node": "node:PROD", "node_display": "\PROD", "series": "rvu:L", "user": "OPS.NEWHIRE",
  "nodes_available": [ {"id":"node:PROD","display":"\PROD"}, {"id":"node:DR","display":"\DR"} ] }
```
## POST /session  `{ "node": "node:DR" }` → same shape (switch node; UI shows it loudly).

## POST /commands/propose
```json
{ "question": "what's pinning the audit trail?", "context": { "system": "sub:TMF", "site": "node:PROD", "version": "rvu:L" } }
→ { "proposals": [
    { "id": "cmd-17", "template_id": "tmfcom.status_audittrail_detail",
      "command": "TMFCOM STATUS AUDITTRAIL, DETAIL", "node": "\PROD",
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
`{ "user_id": "newhire1", "typed_node": "\PROD", "second_approver": null }` → `{ "status": "approved" | "needs_second_approver" | "rejected", "reason": "" }`

## POST /commands/{id}/execute   (simulated; only after approve)
`→ { "run_id": "run:c42", "output": "...", "ts": "...", "source_id": "run:c42" }`

## GET /alerts  (v2 shape)
```json
[ { "id": "al-7", "ts": "2026-10-17T02:10:00Z", "node": "\PROD", "subsystem": "TMF",
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
