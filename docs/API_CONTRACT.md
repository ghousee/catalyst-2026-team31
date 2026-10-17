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
