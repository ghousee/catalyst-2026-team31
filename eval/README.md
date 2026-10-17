# eval/

`golden.jsonl` is an independent evaluation set (60 items). It was written from the veterans' seed notes
(`kg/seed/*.yaml`) and the manual text only, **without looking at the retrieval/answer pipeline, its code, or
the RAG spike questions**, so the questions are not tuned to what the pipeline already does well. Doc chunk ids
in `gold_nodes` were looked up in the `doc_chunk` table.

Run: `python eval/run_eval.py --golden eval/golden.jsonl [--config 1..4]` (API on :8000, or `EVAL_API_BASE`).
It exits with a clear message if the API is not up. Before each item the runner POSTs `/session {"node": ...}`.

| category | n | what it tests |
|---|---|---|
| doc | 15 | answerable from a manual (TMF, Pathway, SCF-Storage, TACL, PEEK, Measure, FUP); vague operator wording |
| veteran | 12 | answerable from one veteran note, including its `not_when` clauses |
| context_trap | 10 | same symptom on `\DR` vs `\PROD`; PROD-only notes must not appear on DR (and DR-only `raj:h8` not on PROD). Includes reverse traps where a node-agnostic note (`lena:h2`) must still be used |
| conflict | 5 | both sides must surface: `maria:h12` vs `raj:h6`, and `maria:h11` vs the TMF manual |
| negation | 5 | correct advice contains a "do not" (do not start with FILESPERVOLUME, do not restart a stalled revive, check the owner before abort, ...) |
| must_refer | 8 | out of scope or undocumented; must refer, not invent |
| must_clarify | 5 | too vague to act on; must ask |

Fields: `id, category, q, node, system, version, gold_nodes, expect (answer|refer|clarify), expert, must_include,
must_not_include, forbidden_sources, both_sides (conflict only), notes`.

- `must_include`: lowercase facts matched case-insensitively over the concatenated claim texts. Each entry is a
  phrase or a list of alternatives (any-of); all entries must match.
- `must_not_include`: phrases that indicate a wrong, inverted or wrong-node answer.
- `forbidden_sources`: ids (globs allowed) that must not be cited; scored on answers.
- `both_sides`: list of any-of id groups; every group needs at least one citation.
- `expert`: counted as routed if listed in `experts` or if a cited source belongs to that owner.

Every metric is printed as `k/n (pct) 95% CI [lo-hi%] n=N` (Wilson interval); with ~5-15 items per slice the
intervals are wide, so read per-category numbers as indicative.
