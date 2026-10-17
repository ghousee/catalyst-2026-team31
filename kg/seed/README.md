# kg/seed: fictional veterans, illustrative knowledge for the demo

**Everything here is invented for the CAIL / HPE NonStop hackathon demo.** Maria Rossi, Raj Patel and Lena
Kowalski are fictional, and so are their notes, years of experience, incident numbers and "resolved case" counts.
The knowledge is plausible for a NonStop shop and is anchored to the manual text we ingested, but it is **not company
data and not HPE guidance**. Do not use it to operate a real system.

What is real: every `source_id` on an edge or command points at a chunk of the public HPE manuals in `doc_chunk`
(the loader fails if one is missing). What is illustrative: event numbers and meanings that come from the demo
scenario (TMF 185/187/109, DISK 5032, Pathway 1034, ...). The ingested TMF/Pathway/SCF manuals describe the commands and
the audit-trail behaviour, but **not** the EMS Operator Messages manual, so those event numbers are marked
`verified: false` in `props`. Edition note: the manuals are J/H editions; `\PROD` is L-series (see ADR-005).

| File | Content |
|---|---|
| `entities.yaml` | aliases for existing subsystem/node/series rows; events, objects, metrics, command templates |
| `persons.yaml` | the three fictional veterans |
| `heuristics.yaml` | 15 notes / warning patterns (2 drafts) with scope, trigger, call, why, not-when, relations |
| `edges.yaml` | graph links; each carries a `source_id` (a real `doc_chunk` or heuristic id) |

Load: `python -m backend.graph.load` (idempotent, validates every `source_id`, embeds heuristics with embeddinggemma).
View: `python scripts/export_graph.py` writes `docs/knowledge_graph.html`.
