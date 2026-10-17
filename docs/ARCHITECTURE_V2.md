# Answer architecture v2: assistant mode

Status: built 2026-10-17 behind `ANSWER_MODE=assistant` (default still `classic` until the bake-off says otherwise).
Code: `backend/pipeline/assistant.py`. The classic pipeline (`backend/pipeline/answer.py`) is unchanged.

## Why
The classic pipeline wrapped a small model in rules: claims forced into JSON, a separate yes/no "is this enough"
check, claims deleted after checking, relevance cutoffs, special cases for greetings and typos. Each rule fixed one
case and broke another; answers felt like a form, and the yes/no check refused questions the manuals cover.

Current practice for this kind of assistant is simpler: good retrieval, a reranker, one LLM call that must cite its
sources, and access/context separation as a filter on the search itself.

## Flow
```
question (+ last 3 turns)
  -> hybrid search over manual sections (vector + keyword), top 20
     + vector search over approved veteran notes, HARD-filtered to the session node (or all-nodes notes), top 6
  -> small cross-encoder reranker (ms-marco-MiniLM-L-6-v2, ~0.7 s on CPU), fused with the search order (RRF)
  -> top 6 sources -> ONE Qwen call: answer like a colleague, cite [n] after each sentence, name the veteran,
     keep every "do not", say plainly if the sources don't cover it and who to ask, may ask a clarifying question
  -> citations mapped to real source ids (unknown numbers dropped) -> reply + cited source cards + who to ask
```

## What stays in code (not the LLM)
- Node separation: notes for other nodes are never retrieved, so they cannot be cited.
- A question naming another node than the session asks which node first.
- Commands only from the catalog, with risk, guards and approvals (`/commands/*`, unchanged).
- Citations only to sources that were actually retrieved.

## What the LLM decides
Wording, which retrieved sources answer the question, follow-ups, clarifying questions, greetings, and declining
when the sources don't cover it. Typos and loose wording are handled by vector search, not by special code.

## Trade-offs
- No MiniCheck in this mode: a wrong paraphrase is less likely to be caught automatically. Mitigation: every
  sentence carries a clickable citation, and the eval decides whether a checker is needed.
- The small reranker scores typo'd or vague questions near zero; its score is therefore only used for ordering
  (fused with search rank), never to discard sources.
- The model is replaceable (one setting): Qwen 3.5 4B on the 6 GB laptop; a 14-32B open model on an on-prem GPU
  server at a customer site.

## Switching
`ANSWER_MODE=assistant` in `.env` (or the environment) and restart the API. The UI renders both modes.
