# RAG feasibility spike (HPE NonStop manuals, RTX 4050 6 GB laptop)

Question: can the design in `docs/SYSTEM_DESIGN.md` §9 (filtered retrieval -> sufficiency gate -> Qwen JSON claims ->
MiniCheck) work on real manuals on this laptop, and with what accuracy and latency?
**Short answer: yes.** Every stage runs locally; the weak spots are vague "how do I fix X" retrieval, tiny eval sets,
and series tagging (see Risks). All numbers below come from `python scripts/rag_spike.py --all` (run 2026-10-17);
anything estimated is marked **(est.)**. Sample sizes are small (27 questions, 10 generations, 24 claim pairs, 10 gate
items): treat differences of one question as noise.

## Setup
| Item | Value |
|---|---|
| Machine | Windows 11, 16 GB RAM, RTX 4050 6 GB, Python 3.12 venv at `.venv` (torch CPU wheel) |
| Postgres | `pgvector/pgvector:pg16`, host port 5433 (compose service `db`) |
| LLM | `qwen3.5:4b` (exists in the Ollama library, 3.3 GB), Ollama service on port 11435, `think=false` |
| Embeddings | `embeddinggemma`, **dimension 768 = `vector(768)` in the schema (verified, no change needed)**. Doc prefix `title: <section> \| text: ...`, query prefix `task: search result \| query: ...` |
| Verifier | `lytang/MiniCheck-Flan-T5-Large` (HF; the model id used by `github.com/Liyan06/MiniCheck` for `flan-t5-large`), fp32 on CPU |
| Data | 7 HPE manuals, `data/raw/hpe/*.txt` (local only, gitignored) |

Reproduce: `docker compose up -d`, pull `qwen3.5:4b` + `embeddinggemma` into our Ollama
(`docker compose exec ollama ollama pull ...`), `python -m backend.ingest.loader`, `python scripts/rag_spike.py --all`.
Results JSON: `eval/results/rag_spike.json` (gitignored).

## 1. Ingestion
Chunker: `backend/ingest/chunker.py`. Extracted text has no reliable indentation, so section boundaries come from
(a) the manual's own table of contents (titles with dot leaders / page refs), (b) message and event numbers
(`3001`, `37`, `MEAS 3000`), (c) the short paragraph(s) before a `Cause.` paragraph (FUP-style all-caps messages),
(d) the running page head (`TMFCOM Commands   STATUS AUDITTRAIL`) for entries missing from the TOC (TACL built-ins,
appendices). Page numbers, doc-id footers, TOC pages and the back-of-book index are dropped. Repeated generic headings
("Examples", "Output Displayed") are prefixed with their parent command. Sections over 800 est. tokens are split on
paragraph boundaries (~600 target); sections under ~120 est. tokens merge into the next one in the same chapter.
Tokens are estimated at 3.5 chars/token (real embeddinggemma count was 1.435 M vs 1.45 M estimated, within 1%).

| Manual | Subsystem (system_id) | Series (version_id) | Edition | Chunks | median est. tok | p10-p90 |
|---|---|---|---|---|---|---|
| TMF-Reference | sub:TMF | **rvu:H** | 540138-001, Jul 2005 | 764 | 249 | 138-588 |
| Pathway | sub:PATHWAY | rvu:J | 426748-005, May 2009 | 436 | 324 | 150-597 |
| SCF-Storage | sub:SCF-STORAGE | rvu:J | 529937-022, Feb 2014 | 583 | 302 | 149-594 |
| TACL-Reference | sub:TACL | rvu:J | 429513-017, Aug 2013 | 794 | 517 | 188-601 |
| PEEK | sub:PEEK | rvu:J | 529657-005, May 2010 | 66 | 568 | 201-689 |
| measure | sub:MEASURE | rvu:J | 523324-013, Mar 2010 | 762 | 409 | 158-598 |
| FUP | sub:FUP | rvu:J | 523323-012, Oct 2009 | 372 | 307 | 148-592 |
| **Total** | | | | **3,777** | | |

Timing: embedding all 3,777 chunks on the **GPU** took **167 s** (about 8.6 k tokens/s); the whole loader run
(chunking + embeddings + inserts + HNSW/GIN indexes) took **5 min 37 s**. Chunking itself is under 0.5 s per manual.
CPU embedding of the corpus: ~650 tokens/s measured on a 16-chunk batch, so **~35 min (est.)**; query embedding on CPU is
fast enough (below). Table size 37 MB.

Tagging: `all_sites = true`, `site_id NULL`, `all_versions = false`. `valid_from` = publication month (cover page).
Entities used: kind `system` for `sub:*`, `version` for `rvu:J|H|L`, `site` for `node:PROD|DR` (no schema change).
The `section` column holds `Chapter > Heading (txt p.N)`; there is no separate page column.

Honest version notes: the cover pages say "J06.03 and subsequent J-series RVUs, H06.03 and subsequent H-series RVUs"
(plus G/D for most) for every manual except TMF, which says **H06.03 and subsequent H-series only**. `version_id`
can hold one series, so the J/H manuals are tagged `rvu:J`, TMF `rvu:H`. **L-series (NonStop X) is not covered by any
edition here; behaviour there is unknown.**

Known extraction defects: `TACL-Reference.txt` has kerning artifacts inside headings ("Com m ands", "#EM PTYV"), which
leak into section labels and slugs (body text is clean). Merged message chunks carry the id of their first message
(`doc:Pathway:msg-3122` holds 3122 and 3123).

## 2. Retrieval
`backend/pipeline/retrieve.py` (all behind `context_where`; `ctx=None` is for the eval's no-filter baselines only):
- `vector_search`: pgvector cosine (HNSW index).
- `keyword_search`: Postgres FTS (`english` config, GIN index). Candidates match ANY query term; score =
  sum of BM25-style idf of matched terms + 0.1 * `ts_rank_cd`. **Plain `ts_rank` with an OR query was bad**
  (recall@5 0.44, event questions 0.00) because it has no idf: STATUS drowned the message number.
- `hybrid_search`: reciprocal rank fusion (k=60) of the two top-30 lists.

Eval: 27 operator-style questions written from the manuals (`eval/spike_questions.jsonl`: 7 syntax, 7 event/message,
5 fix, 8 context traps). Every gold chunk id was checked by a script (`--verify-gold`) to exist, belong to the right
subsystem, and contain the key phrase. Filter = the question's subsystem + that manual's series. **Strict** = gold chunk id(s);
**entry** = gold or a sibling chunk of the same manual entry (`stop-tmf-part-2` for `stop-tmf`), because the
strict metric penalises correct near-misses.

| Config | recall@5 | MRR | entry recall@5 | entry MRR | top-5 rows from wrong subsystem | DB ms p50 |
|---|---|---|---|---|---|---|
| vector, no filter | 0.78 | 0.667 | 0.89 | 0.785 | **10%** | 57 |
| keyword, no filter | 0.74 | 0.462 | 0.74 | 0.502 | **27%** | 1314 |
| hybrid, no filter | 0.85 | 0.688 | 0.93 | 0.821 | **15%** | 1304 |
| vector + subsystem filter | 0.78 | 0.674 | 0.93 | 0.818 | 0% | 48 |
| keyword + subsystem filter | 0.81 | 0.513 | 0.85 | 0.590 | 0% | 273 |
| **hybrid + subsystem filter** | **0.81** | **0.736** | 0.89 | **0.887** | 0% | 277 |
| hybrid + filter, but series forced to rvu:J for everything | 0.63 | 0.603 | 0.67 | 0.658 | 0% | 187 |

By question type, strict recall@5 / MRR for hybrid + filter: syntax 0.71 / 0.66, event 0.71 / 0.74, fix 1.00 / 0.72,
trap 0.88 / 0.81 (vector + filter: 0.71 / 0.67, 0.86 / 0.51, 0.60 / 0.65, 0.88 / 0.83). Query embedding on CPU:
p50 301 ms, p95 354 ms.

Reading the table:
- **Contamination without a filter is real but not catastrophic on this corpus**: 10% (vector) to 27% (keyword) of
  top-5 rows come from the wrong subsystem; the filter makes it 0% by construction. The question set is small and the
  subsystem names appear in most questions, so the unfiltered numbers are probably optimistic for truly vague input
  (e.g. "stop it"). Trap questions: even unfiltered vector got 0.88 recall@5, but the filter is what *guarantees*
  the rule rather than relying on wording.
- **Keyword beats vector on message/event and "fix" questions, loses on vague syntax questions**; hybrid takes the
  best of both: best MRR (0.736 vs 0.674). On recall@5 the difference between vector+filter and hybrid+filter is
  one or two questions out of 27 (entry recall 0.93 vs 0.89), so the evidence for hybrid is mainly MRR and the
  event/fix categories, not recall.
- **Series tagging matters**: forcing `rvu:J` on every query drops hybrid recall@5 from 0.81 to 0.63, because the
  TMF manual is H-only. An exact-match series filter is unsafe when manuals support several series (see Risks).
- Misses are mostly near-misses (sibling chunks, `reviving-a-mirrored-disk` instead of `START DISK`). Genuine misses:
  q05 `#PROCESSINFO` (the chunk is found, but many sibling function chunks compete), q12 TACL "unable to open" (generic
  error-number chunks rank first), q14/q22 (vague wording; TMF has several "server" and "stop" chunks).

## 3. Generation (Qwen `qwen3.5:4b`, 10 questions, hybrid + filter top-5, `format` = JSON schema)
| Mode | JSON valid | Claims | Claims citing a retrieved id | Answers citing the gold chunk | p50 / p95 latency | tok/s |
|---|---|---|---|---|---|---|
| raw chunk ids as labels | 10/10 | 28 | 26/28 (92.9%) | 6/10 | 4.2 s / 8.3 s | 49 |
| **S1..Sn aliases mapped back by code** | 10/10 | 29 | **29/29 (100%)** | 7/10 | 3.8 s / 6.3 s | 48 |

- Prompt averaged ~2,000 tokens (5 chunks); ~80-200 generated tokens per answer.
- Two defects found along the way: (1) without `maxItems` an early run looped to the 700-token limit and returned
  invalid JSON (1/10); schema now has `maxItems: 6`. (2) With raw ids the model cited `doc:Pathway:msg-3123` for a claim
  that is correct but lives in the merged chunk `msg-3122`; code-side validation dropped a **correct** claim. Short
  aliases fixed it. Keep alias mapping in production.
- The "gold" shortfall is retrieval-order/choice, not formatting: e.g. for the DENSITY question the model cited a
  different retrieved chunk that also discusses DENSITY.
- VRAM (`ollama ps`): Qwen **3.11 GiB loaded, 100% GPU**, at `num_ctx` 8192. Total GPU memory in use ~3.96 GB of 6.14 GB.
  embeddinggemma runs on CPU (0 GiB VRAM) when `num_gpu: 0`.
- Affordable context: model size and GPU share at different `num_ctx` (same prompt): 4096 -> 2.92 GiB / 100%; 8192 ->
  3.11 / 100%; 12288 -> 3.17 / 100%; **16384 -> 3.30 GiB / 100%**; 32768 -> 4.01 GiB / **85% GPU, tok/s drops 48 -> 27**.
  Use `num_ctx` 8192 (k=5 chunks fit with room); 16384 is the ceiling that stays 100% GPU.

## 4. Verifier: MiniCheck-Flan-T5-Large on CPU
Installed without the `minicheck` package (it pulls vllm/nltk): `backend/pipeline/verify.py` re-implements its flan-t5
path on transformers (input `"predict: " + doc_window + </s> + claim`, one decoder step, softmax over token ids [3, 209];
doc split into 400-word windows, max over windows). Download ~3 GB (`pytorch_model.bin`, fp32; the HF cache dir is
5.9 GB because of Windows no-symlink copies). Loads in a few seconds; RAM ~3 GB **(est. from fp32 weights)**.

24 hand-written claim/chunk pairs (`eval/spike_claims.jsonl`): 12 supported, 12 deliberately unsupported (fabricated
effect, contradicted fact, wrong cause/recovery/range, subsystem swap, option from another subsystem).
- Supported: mean P(support) 0.952, min 0.793. Unsupported: mean 0.034, max 0.128. **Accuracy at threshold 0.5 = 24/24,
  AUC 1.00** (any threshold from 0.13 to 0.79 separates them).
- Latency **1.27 s mean per claim, 2.1 s p95** on CPU (chunk ~600 tokens).
- On Qwen's own 29 cited claims it kept 27/29 (93%) at 0.5; I did not hand-review the two dropped claims.
- Caveat: my unsupported claims are easy (clear contradictions or inventions); subtle paraphrase errors are untested.
Verdict: **practical, keep MiniCheck.** Fallback if it ever hurts: sentence-level lexical-overlap check plus the
existing code-side citation check.

## 5. Sufficiency gate (prompt-based Qwen, structured `{sufficient, reason}`)
10 items, 5 answerable (gold in the filtered top-5) and 5 unanswerable (off-topic for these manuals: BASE24, forgotten
password, NonStop X audit sizing, Expand lines, TCP/IP tuning). **10/10 correct (5/5 and 5/5)**, ~2-4 s each.
An earlier run scored 9/10: the unbounded `reason` string was truncated at the token limit, giving invalid JSON that
counted as wrong; the schema now caps the reason (`maxLength` 160, 200 tokens). **Weak evidence**: the unanswerable
items are easy; near-miss cases (right subsystem, wrong command) are the real test and are not covered.

## Estimated end-to-end latency (est., sum of measured stages, one question)
embed query 0.3 s + retrieval 0.3 s + gate 2.5 s + generation ~4 s + MiniCheck ~1.3 s x ~3 claims = **~10-11 s p50 (est.)**
with the LLM already loaded. Model swap (Qwen reload) costs 10-30 s; keep it resident, MiniCheck and embeddings on CPU.

## Decisions / recommendations
1. **Chunking**: structure-aware (TOC titles + message numbers + running heads), 300-800 est. tokens, as built. Do not
   merge message entries beyond ~400 tokens; ideally emit one chunk per message number (cheap fix, avoids id mismatches).
2. **Hybrid + filter** is the default (best MRR, robust on event/fix). Vector-only is acceptable as a fallback
   (~6x faster DB step: 48 ms vs 277 ms) if keyword latency matters; add a stored `tsvector` column to remove the
   on-the-fly `to_tsvector` cost if so.
3. **k = 5** retrieved chunks, `num_ctx` 8192 (prompt ~2 k tokens). k=8 would still fit (est.), not measured.
4. **Model**: `qwen3.5:4b` with `think=false` and structured output works: 100% valid JSON (after `maxItems`),
   ~48 tok/s, 100% GPU. No need for the `phi4-mini` fallback.
5. **Always alias sources** (S1..Sn) and validate by code; keep dropping claims without a retrieved source.
6. **MiniCheck: yes**, on CPU, threshold 0.5 as a start (observed gap is wide); calibrate on harder pairs.
7. **Gate**: prompt-based is good enough for the demo; add near-miss cases before trusting it.
8. **Series tagging**: do not use a single exact `version_id` for manuals that support several series. Options: tag
   `all_versions = true` for J/H-agnostic manuals, duplicate rows per series, or relax the version filter to a set
   (decision for the team; this spike forced a single tag per manual).

## Risks
- Tiny eval sets, written by one author; gold coverage is by entry, with some arbitrary choices. Numbers are indicative.
- Doc content is 2005-2014 (J/H era); L-series behaviour unknown. Questions were written from the same manuals the
  retriever searches, so wording overlap is higher than real operator questions.
- `Pathway.txt` is the Pathway/iTS (TCP/TERM) manual; PATHMON/server-class (TS/MP) commands are mostly absent
  (e.g. "server" questions land in TMF or in TCP/SEND messages).
- Extraction artifacts (TACL spacing); tables and syntax diagrams lose alignment in text.
- Qwen sometimes picks a lower-ranked but related chunk; MiniCheck only checks support, not that the best source was used.
- Keyword step is 270 ms (filtered) and ~1.3 s unfiltered because tsvectors are computed on the fly.

## Next steps
- Per-message chunking; stored tsvector; add `components`/aliases (operator wording -> command names) as query expansion.
- Series strategy (item 8); wire `context.py` so the filter comes from the session, not from the question text.
- Larger, independently written eval set with real operator phrasing; near-miss gate cases; subtle MiniCheck negatives.
- Assemble `answer.py` with the stages measured here and log latency per stage.
