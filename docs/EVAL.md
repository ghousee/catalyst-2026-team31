# How we prove accuracy

No model training this weekend. Accuracy comes from (1) context-tagged data, (2) filter-before-search,
(3) deterministic graph answers, (4) sufficiency gate + MiniCheck, (5) LLM writes glue only.
The golden set is how we **know** — and the ablation table shows which layer fixed what.

## Build the golden set (Sat morning, ~2–3 hrs; teammates write it, not the pipeline builder)
1. **Pick the slice:** the 1–2 demo systems only.
2. **Draft with AI from each doc section:** "Here is §4.2 of the P-201 v3 manual. Write 3 questions a new
   technician would ask that this answers. Use vague shop-floor wording, not the doc's words." → the section
   ID is the `gold_nodes` for free.
3. **Hand-make the hard cases:**
   - Context traps: same symptom, other system. Gold = other system's section, or `refer` if undocumented.
   - Unanswerable: gold = `refer` + expert.
   - Ambiguous (no system named): gold = `clarify`.
   - Veteran items: one question per captured heuristic.
   - Adversarial (security teammate): planted "ignore previous instructions" in a test doc; permission-restricted chunks.
4. **Human review:** delete weak items. 50 good > 200 sloppy.
5. **Save** to `eval/golden.jsonl` (template provided).
6. **FREEZE by Saturday noon.**

| Category | # |
|---|---|
| Doc-answerable | 15 |
| Veteran-heuristic | 10 |
| Context traps | 10 |
| Must refer | 10 |
| Must clarify | 5 |
| Adversarial | 5 |

## Metrics (per stage, so we know where it fails)
- **Context accuracy:** resolved system/version == gold
- **Retrieval recall@5:** any gold node in top-5
- **Behaviour accuracy:** answer/clarify/refer == `expect`
- **Correct refusal rate** AND **false refusal rate** (track both or it learns to refuse everything)
- **Contamination rate:** context-trap items citing the wrong system ← **headline number**
- **Unsupported-claim rate:** claims MiniCheck rejects / total claims
- **Referral accuracy:** right expert suggested
- **Answer correctness:** LLM judge + hand-check 20
- **Watcher:** lead time on 3–5 replayed incidents; false alarms on normal logs

## Ablation table (best slide)
| Config | Contamination ↓ | Unsupported claims ↓ | Behaviour acc ↑ |
|---|---|---|---|
| 1. Plain vector RAG | | | |
| 2. + context resolution/filter | | | |
| 3. + sufficiency gate | | | |
| 4. + MiniCheck verifier | | | |

Run `python eval/run_eval.py --config N` for each row.

## After the hackathon (only where eval shows a weak spot)
- Extractor gets systems wrong → fine-tune a small entity extractor on their terminology.
- MiniCheck misjudges jargon → fine-tune on claim/source pairs (MiniCheck's synthetic-data recipe).
- Never fine-tune knowledge into the LLM.
