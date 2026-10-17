# Research notes (checked Oct 16, 2026)

## A. Competitors / market
| Category | Players | What they do | Gap vs us |
|---|---|---|---|
| Expert routing | **Starmind** | Routes questions in Teams/Slack to the colleague with the knowledge; answers verified by humans; stores answers in a Knowledge Suite. Weakness: repository stagnates if response rates/incentives are low | No context scoping, no proactive warnings |
| Expert routing | **Glean** | Enterprise knowledge graph of people/content/activity; "Expert Detection" maps subjects to people | Reviewers note tacit knowledge rarely exists as searchable docs |
| Verified/cited answers | **Guru** | Filters unverified content before the LLM; every answer has source + owner; configurable honest refusal | Flattens knowledge; no per-veteran heuristics/disagreement |
| Verified/cited answers | **Stack Overflow Internal** | Auto-designates SMEs by tag reputation; attribution non-negotiable | Q&A, not context-aware ops |
| Capture | **Sensay** | AI interviewer ("Sophia") at offboarding → chatbot in Slack/Teams | One-time offboarding, not continuous |
| Capture | **KNOWRON**, **Ascendo AI**, **iFactory**, Manual.to, Tribal-knowledge.nl | Voice/video capture, mining work orders/tickets; iFactory links near-misses across shifts via a KG | Capture-focused |
| Industrial copilots | Rockwell (in-house), Augmentir, Siemens, VSight Nova, MS Dynamics 365 Guides | Source-cited answers from manuals + expert notes for frontline techs | Mostly doc RAG; no context-trap focus |

**Our gap:** (1) context disambiguation as a first-class feature, (2) per-person heuristics with "contradicts the doc" edges and visible expert disagreement, (3) continuous capture through referrals, (4) proactive watcher.

## B. Research papers → design changes
1. **Knowledge Graphs as the Missing Data Layer for LLM-Based Industrial Asset Operations** (VLDB AG2026 workshop, arXiv 2605.26874). GPT-4 on flat docs 65% → LLM-generated Cypher over a typed KG 82–83% → deterministic graph queries 99% on graph-answerable scenarios. "Inverted LLM usage": LLM generates queries, graph executes. → **Route graph-answerable questions to deterministic queries; the data layer is the lever.**
2. **Sufficient Context** (Google, ICLR 2025, arXiv 2411.06037). Small open models hallucinate or abstain even when context is sufficient; fine-tuning a 7B to say "I don't know" helped only modestly. Selective generation with a sufficiency signal improves accuracy. → **Explicit sufficiency gate; don't trust Qwen 4B to decide refusal.**
3. **MiniCheck** (EMNLP 2024, arXiv 2404.10774). 770M Flan-T5 checker reaches GPT-4 accuracy at ~400× lower cost; atomic-fact decomposition not needed. Code: github.com/Liyan06/MiniCheck. → **Verifier; runs on CPU.**
4. **KG + LLM diagnostics** (arXiv 2505.21291, battery/aviation/FMEA KG-RAG papers). KGs built from maintenance records; symptom→cause pathways traced in the graph. → **Store veteran triggers as symptom→cause→fix paths.**
5. **Critical Decision Method** (Klein et al.; Taylor 2005). Retrospective interviews on real incidents with cognitive probes surface tacit knowledge beyond espoused theory. → **Teach-mode interview script.**
6. **LLMs Explain Experts Better Than Experts Themselves** (alphaXiv 2608.07488). LLM-externalized tacit knowledge from expert behavior helped novices approach expert performance, often beating expert-articulated knowledge. → **Mine tickets to draft heuristics; veterans confirm.**
7. **GraphRAG** (Microsoft, arXiv 2404.16130). Built for *global* sensemaking questions; heavy indexing (LazyGraphRAG cut cost to 0.1%). → **Skip; our questions are local.** Maybe community summaries for the risk dashboard.

## C. TypeSafe Jev (optional)
- System One decision model: returns typed decisions (choice / score / yes-no) with calibrated probabilities, no free text, single pass.
- Trained with RLCD → higher confidence should mean higher accuracy. "Can't hallucinate" = can't emit out-of-schema output; it *can* still be wrong.
- Price: $0.042 per 1M input tokens, output free (~$15 per 1M decisions in one test). Latency 70–500 ms. Context 64k per request.
- Hosted/proprietary API only (zero-data-retention option per request); waitlist/early access reported.
- Best uses here: sufficiency gate, applicability check ("does node apply to P-201 v3?"), watcher trigger matching.

## D. Local model choice (RTX 4050, 6GB VRAM)
- **Pick: `qwen3.5:4b`** (Ollama, ~3.4GB, tool calling) → leaves ~2GB for context.
- Alt: `phi4-mini` (~2.5GB, most headroom). `qwen3:8b` Q4 (~5GB) fits only with ~2K context — too tight for RAG.
- Embeddings: `embeddinggemma` (568M) on CPU.
- Verify with `ollama ps` → must say `100% GPU`.
- A local RAG repo (github.com/Another-DevX/RAG) uses qwen3:4b to emit grounded claims and rejects citations to unknown chunks — same pattern as ours.

## E. Costs
- **Hackathon (laptop):** ~$0 + a few cents of Jev.
- **If deployed 24/7 (one-site pilot), est.:** L40S GPU ~$577/mo (RunPod $0.79/hr) + RDS db.t4g.medium Canada ~$51/mo + Jev ~$15/1M decisions + app/logs ~$50 (estimate) ≈ **$700–750/mo**. Neo4j AuraDB Pro is $65/GB/mo (10GB = $650/mo) → Postgres is cheaper at small scale. GPU is ~80% of cost; serverless GPU can cut it.

## F. Claude Code usage (from Anthropic docs + Boris Cherny's workflow)
- `opusplan`: Opus in plan mode, Sonnet for execution.
- Subagents inherit the session model unless `model:` is set in their definition. Verify routing with `/usage` (a GitHub issue reported subagent model settings being ignored).
- Opus 5.5 / Sonnet 5.5 default effort = medium; keep it.
- Safety classifiers most often flag cybersecurity content → requests may fall back to an older model. Expect this during prompt-injection testing; not an account problem.
- Boris: 5 parallel sessions + worktrees, plan mode first, CLAUDE.md ~2.5k tokens updated on every mistake, verify every change, PostToolUse format hook, `/commit-push-pr` command, almost never `--dangerously-skip-permissions`.
- Anthropic: context fills fast and performance degrades → fresh session per task; explore → plan → code → commit.

## Sources
- Starmind: https://www.starmind.ai/expert-finder · https://us.fitgap.com/products/007408/starmind
- Glean: https://research.contrary.com/report/glean · https://bloomfire.com/resources/what-is-glean/
- Guru: https://www.getguru.com/landing-page/grounded-llm-search · https://www.kmworld.com/Articles/Editorial/Features/Guru-the-AI-source-of-truth-for-enterprise-knowledge-176368.aspx
- Stack Overflow SMEs: https://support.stackenterprise.co/support/solutions/articles/22000294486
- Sensay: https://blog.sensay.io/how-sensay-ai-offboarding-works
- KNOWRON: https://www.knowron.com/usecases/knowledge-capture · Ascendo: https://www.ascendo.ai/post/capture-technician-knowledge-before-retirement · iFactory: https://ifactoryapp.com/industries/manufacturing-plant/knowledge-management-ai-tribal-manufacturing
- Rockwell: https://news.microsoft.com/source/features/digital-transformation/rockwell-automation-pairs-ai-with-decades-of-shop-floor-know-how-so-workers-can-solve-glitches-faster/
- MS Dynamics 365 Guides: https://www.microsoft.com/en-us/microsoft-cloud/blog/manufacturing/2023/11/15/introducing-copilot-in-microsoft-dynamics-365-guides-bringing-generative-ai-in-mixed-reality-to-frontline-workers/
- KG data layer paper: https://arxiv.org/html/2605.26874
- Sufficient Context: https://iclr.cc/virtual/2025/poster/30092 · https://academy.dair.ai/papers/new-lens-on-rag-systems
- MiniCheck: https://arxiv.org/abs/2404.10774v2
- KG diagnostics: https://arxiv.org/pdf/2505.21291
- Critical Decision Method: https://www.academia.edu/125697474/Eliciting_Tacit_Knowledge_Using_the_Critical_Decision_Interview_Method
- LLMs explain experts: https://www.alphaxiv.org/abs/2608.07488
- GraphRAG: https://arxiv.org/html/2404.16130v2
- Jev: https://runware.ai/creators/typesafe-ai · https://nexos.ai/blog/what-is-jev/ · https://www.eesel.ai/blog/typesafe-jev-pricing · https://www.ayautomate.com/blog/jev-pricing-cost-per-decision · https://www.beri.net/tools/typesafe-jev · https://freeapihub.com/blog/jev-ai-model
- 6GB models: https://localaimaster.com/vram/best-ollama-models-6gb-vram · https://www.promptquorum.com/prompt-bites/best-local-llm-6gb-vram · https://canitrun.dev/guides/6gb-vram-llms/ · https://insiderllm.com/guides/best-local-llms-rag/
- Costs: https://neo4j.com/cloud/aura/pricing/ · https://computeprices.com/providers/runpod/gpus/l40s · https://www.bytebase.com/dbcost/rds/instance/db.t4g.medium/
- Claude Code: https://code.claude.com/docs/en/model-config.md · https://code.claude.com/docs/en/best-practices · https://code.claude.com/docs/en/remote-control · https://infoq.com/news/2026/01/claude-code-creator-workflow/ · https://github.com/anthropics/claude-code/issues/43869
