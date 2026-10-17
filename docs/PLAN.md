# Project plan — Veteran Knowledge Graph

## 1. Problem (from the company that pitched it)
- Veterans with ~20 years have domain expertise and "warning patterns" that new hires don't.
- Need: **identify issues before they happen**, and **know how to resolve them when the veteran isn't there**. "ChatGPT can't answer everything."
- Their real worry is **context**, not hallucination: "you don't want the wrong instructions for similar keys but different software or systems."
- Team constraints: **must be a chatbot**, **citations mandatory**, **if the AI doesn't know → don't answer, reference a person**.

## 2. Core design decisions
| Decision | Why |
|---|---|
| One **shared entity backbone** + overlays (doc overlay, one overlay per veteran) | Same node IDs → contradictions, gaps, disagreement and bus-factor fall out as edges |
| Context fingerprint on every node: system, version, site, valid_from/valid_to | Kills cross-system contamination at the data layer |
| Filter by resolved context **before** retrieval; ask if ambiguous | Company's #1 concern |
| LLM only writes glue; graph answers when it can | Research: typed KG + deterministic queries beat smarter LLMs |
| Sufficiency gate before generation | Small models are bad at deciding to abstain (Google, ICLR 2025) |
| MiniCheck verifier after generation | GPT-4-level grounding check, 770M, runs on CPU |
| Refusal = referral to the right expert | "Don't know" becomes a feature + knowledge capture |
| No LLM training this weekend | Knowledge in weights can't be cited, scoped, or updated |
| Jev optional | Great fit for typed yes/no gates; hosted API so keep a local fallback |

## 3. Knowledge model
**Layer 1 — Doc overlay (official):** company docs chunked, tagged with context fingerprint. Source of truth for citations.

**Layer 2 — Person overlays (veterans):** each heuristic node has
- `trigger`: e.g. "pressure dips + alarm X within 10 min on P-201 v3"
- `call`: what they do ("check valve Y first; almost never the sensor")
- `why`: rationale in their words
- `owner` + `provenance`: interview / ticket # / referral answer, date
- links to doc nodes: `extends` / `contradicts` / `supersedes`
- `endorsements`, `last_validated` (folklore control)

**"Contradicts" edges are the killer feature**: "Manual §4.2 says X, but Ravi says that's wrong on v3 units."
**Disagreement between veterans is kept, not merged** — shown attributed.

## 4. Two surfaces
### Chatbot (reactive)
- Context chips above every answer: `Assuming: System B · v3 · Plant 2` (tap to fix).
- Confidence lanes: 🟢 documented (doc citation) · 🟡 veteran insight (person citation) · ⚪ unknown (refer).
- "Why Ravi says this" expandable rationale.
- Refer card: "No verified answer for System B v3. Best people: Ravi (12 resolved cases), Priya (doc owner)." + one-click **Ask Ravi** (sends full context).

### Watcher (proactive)
- Veteran triggers stored as symptom → cause → fix paths on specific entity+version nodes.
- Continuously checks live signals against triggers (Jev or local classifier: "matches Ravi's pattern? p=0.87").
- Pattern can only fire on its own entity/version (context built in).
- Pushes into chat: "⚠ Early sign of valve Y failure on P-201 (Ravi's pattern). Fix: … [cited]. Ravi off today; backup: Priya."
- Demo: replay a recorded incident log at 10× → warning fires N hours early → "lead time gained".

## 5. Input (how knowledge gets in)
1. **Docs:** bulk ingest, auto-tag fingerprint, admin reviews once.
2. **Teach mode (veterans):** bot interviews them using the **Critical Decision Method** — show a past incident: "What did you notice first? What would you check? When does that NOT apply? What do you notice *before* X goes wrong?" Bot drafts the heuristic; veteran approves/edits. Nothing goes live unsigned.
3. **Mine past tickets/logs** to *draft* heuristics (research: LLM-inferred tacit knowledge helped novices approach experts) → veteran confirms.
4. **Referral answers:** when Ravi answers a referred question → "Save as knowledge?" one tap → cited node owned by Ravi.
5. **Corrections:** ✓ endorse / ✗ wrong / ⚠ outdated on every answer.

## 6. The loop (pitch line)
New hire asks → bot doesn't know → refers to Ravi → Ravi answers → saved as cited knowledge → next hire gets it instantly. System learns from its own gaps; veteran load drops.

## 7. Veteran buy-in (biggest real risk)
- Credit, not extraction: "Your insights helped 14 people this month."
- Voice-first 2-min "case of the day"; never ask them to write.
- Load protection: digest batching, rotate experts, never ping the same person 10× for one question.

## 8. Spin-offs (often better business than the chatbot)
1. **Knowledge-risk dashboard / bus factor:** "Only Ravi knows System B v2." ← end the demo on this.
2. Doc drift detector: every "contradicts" edge = a doc to fix.
3. Auto onboarding curriculum from questions new hires actually ask.
4. Live warning patterns (the watcher, productized).
5. Expert disagreement map → where processes need standardizing.

## 9. Hackathon scope (cut list)
IN: context-tagged ingest of 1–2 systems, graph+vector retrieval with context filter, clarify/refer, sufficiency gate, MiniCheck, cited answer cards, referral flow, watcher replay, eval + ablation table, security demo.
OUT: full GraphRAG, model fine-tuning, Slack integration, real-time sensor ingestion, auth beyond a role toggle.

## 10. Pitch one-liner
"Starmind's expert routing + Guru's verified citations — but context-aware and built for veterans' judgment, not just documents. And it warns you before things break."
