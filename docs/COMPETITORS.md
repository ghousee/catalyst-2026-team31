# Competitive Landscape: Local AI Operator Copilot for HPE NonStop

Research date: 2026-10-17. Method: web/vendor/press research only (no paper citations; the LibKey scholarly connector is not authorized in this session, so no academic sources were used).

Legend: Y = vendor states it; N = not offered / contradicted; ? = could not verify. Every row is vendor-stated unless noted. "On-prem" means the product (including the LLM) can run with no cloud dependency. Several vendors say nothing about this, which we mark `?`, not `N`.

## 1. Summary

- **The NonStop space just woke up (Feb-Jun 2026).** Three NonStop-native AI efforts launched in 2026: IR "Iris for HPE Nonstop" (17 Jun 2026), XYPRO "Lionel" (19 Feb 2026, internal tool), and Idelji "ManAIge" (article 31 May 2026). Infrasoft is pushing MCP access to NonStop (uLinga Nexus). HPE itself shows no NonStop operator copilot (its AI ops story is OpsRamp / GreenLake Intelligence, a different product line).
- **Iris is the closest direct threat**, but it is a conversational layer on Prognosis telemetry (health, performance, capacity). The release does not mention manuals, named-expert knowledge, command execution, on-prem LLM, or per-node context rules.
- **Mainframe vendors (IBM, BMC, Rocket, Kyndryl)** are shipping agentic AI ops assistants for z/OS in 2025-2026. They validate the market and show the pattern (RAG over docs, human-in-the-loop, policy guardrails). None targets NonStop.
- **Expert/tribal-knowledge tools (Starmind, Sensay, KNOWRON, Augmentir, Rockwell)** capture human knowledge but are built for manufacturing or generic enterprise Q&A, mostly SaaS, with no operational telemetry, command generation or early warning.
- **No product found combines all five of our properties** (cited answers from manuals AND named veterans, approved NL-to-command, veteran-pattern early warning, strict node/version context-gating, fully on-prem). This is the gap. Several products come close on 1-2 properties.

## 2. Comparison table

Columns: Cites = cites sources; Expert = captures named-expert knowledge; Cmd = NL to commands with human approval; Warn = proactive warnings; Ctx = context-aware (node/version scoping); On-prem = runs without cloud.

### A. HPE NonStop ecosystem (same industry)

| # | Product (company) | Category | Cites | Expert | Cmd | Warn | Ctx | On-prem | Pricing |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Iris for HPE Nonstop (IR, Prognosis) | NonStop observability + conversational AI | ? | N | N (gives "recommended next steps") | Y (capacity/batch planning; Prognosis alerting) | ? | ? | Not public |
| 2 | Lionel (XYPRO / PartnerOne) | Internal NonStop knowledge assistant | Y ("verified answers") | Partly (manuals, tickets, specialists' knowledge) | N | N | ? | ? | Internal; customer access "eventually", no price |
| 3 | ManAIge / iManAIge (Idelji) | NonStop AIOps, predictive | ? | N (learns from feedback, not named experts) | Y-ish (runs fixes "when authorized"; approval flow undescribed) | Y (forecasts up to a year) | ? | iManAIge is described as SaaS; ManAIge ? | Not public |
| 4 | uLinga Nexus MCP (Infrasoft) | MCP bridge exposing Pathway/PATHCOM to AI agents | N | N | Partly (curated tools; "human makes the call") | N | N | Runs natively on NonStop; model location unaddressed | Not public |
| 5 | QoreStor Anomaly Detection (ETI-NET) | NonStop backup anomaly detection (ML) | N | N | N | Y (backup-data anomalies only) | N | ? | Not public |
| 6 | TIC Navigator (TIC Software) | NonStop code analysis | ? | N | N | N | ? | ? | Not verified |
| 7 | INETCO Insight / BullzAI | Payment transaction monitoring, fraud ML | N | N | N | Y (fraud/perf) | N | ? | Not public |
| 8 | HPE OpsRamp Operations Copilot / GreenLake Intelligence | HPE AIOps (not NonStop-specific) | ? | N | Partly (agentic with human-in-the-loop) | Y | ? | OpsRamp is SaaS; on-prem unverified | Not public |

Not found or no AI product located: comforte, Gravic/Shadowbase, NuWave, Insider Technologies, TCM/Lusis Payments, IR Transact (as separate AI), ACI BASE24 ops AI. See "Unverified" below.

### B. Mainframe / mission-critical IT operations

| # | Product (company) | Category | Cites | Expert | Cmd | Warn | Ctx | On-prem | Pricing |
|---|---|---|---|---|---|---|---|---|---|
| 9 | watsonx Assistant for Z + Z AIOps / Concert for Z (IBM) | z/OS operator assistant, agentic | Y (RAG over IBM + customer docs) | N | Y-ish (skills/automation, Z ChatOps) | Y (via Z AIOps/OMEGAMON incidents) | Partly (per-environment data) | Runs as containers on OpenShift; fully air-gapped ? | Not public |
| 10 | BMC AMI Assistant / AMI Platform (BMC) | z/OS gen-AI assistant | ? | N | N | Y (hybrid AI root-cause explanation) | ? | BYO-LLM, containerized/Kubernetes; fully on-prem ? | Not public |
| 11 | Rocket EVA + PlanGuard (Rocket Software; Geniez AI acquired 13 Oct 2026) | Agentic AI for mainframe ops | ? | N | Y (agents suggest/execute within policy; audit logs) | Y (correlation, MTTR) | ? | ? | Not public |
| 12 | Kyndryl Agentic AI Framework + mainframe services | Managed services / agents | ? | N | Y-ish (agents with human oversight) | Y (predictive analytics) | ? | Services model; ? | Services pricing |
| 13 | Broadcom Mainframe AIOps (OI / WatchTower) | Mainframe AIOps | ? | N | N | Y | ? | Customer on-prem data (Futurum); gen-AI assistant not confirmed | Not public |

### C. General AIOps / incident copilots

| # | Product (company) | Category | Cites | Expert | Cmd | Warn | Ctx | On-prem | Pricing |
|---|---|---|---|---|---|---|---|---|---|
| 14 | PagerDuty Advance / SRE Agent | Incident AI agent | ? | Learns from past incidents | Y (diagnostics, remediation executed after approval) | Y | ? | Self-hosted runner in early access (Sept 2026), K8s first | Not public here |
| 15 | Dynatrace Davis CoPilot / agentic workflows | Observability copilot | ? | N | N (NL to DQL queries) | Y (causal/predictive AI) | ? | Managed availability unverified | Not public |
| 16 | Datadog Bits AI SRE | AI SRE agent | ? | N | ? | Y | ? | N (SaaS) | AI credits from $500 per 500 credits/month (third-party tracker, June 2026) |
| 17 | ServiceNow Now Assist for ITOM | ITSM/ITOM gen-AI | ? | N | N | Y | ? | Limited; some features unavailable to self-hosted | Not public |
| 18 | Splunk AI Assistant for SPL | NL to SPL queries | Partly (public docs) | N | Y (SPL generation) | N | N | Cloud-connected for on-prem Splunk (no local GPU, needs Splunk cloud) | Not public |
| 19 | BigPanda AI Incident Assistant (Biggy) | Incident correlation, expert routing | ? | Routes to SMEs by incident history | N (runbook execution on roadmap) | Y | ? | ? | Not public |

### D. Knowledge capture / expert tools

| # | Product (company) | Category | Cites | Expert | Cmd | Warn | Ctx | On-prem | Pricing |
|---|---|---|---|---|---|---|---|---|---|
| 20 | Starmind | Expert finder + knowledge | ? | Y (maps experts; expert-verified answers) | N | N | N | ? | Custom |
| 21 | Sensay | AI offboarding, expert chatbot | ? | Y (voice interviews of departing staff) | N | N | N | ? | Not verified |
| 22 | KNOWRON | Industrial knowledge + retiring-worker capture | ? | Y (claimed) | N | N | ? | ? | Not verified |
| 23 | Augmentir (Augie) | Frontline copilot (manufacturing) | ? | Y (documents expert procedures) | N | Partly | ? | ? | Not verified |
| 24 | Rockwell Maintenance Copilot | Plant tribal knowledge + manuals | ? | Y (worker expertise + manuals + data) | N | ? | ? | ? | Internal case study |
| 25 | Guru | Verified knowledge, agents | Y (citations, audit trails) | Verified by owners | N | N | N | N (SaaS) | Custom; older $25/seat/mo |
| 26 | Glean | Enterprise AI search | Y (as generally marketed) | N | N | N | N | Dell on-prem option reported, conflicting sources | ~$50+/user/mo, high minimums (third-party) |
| 27 | Stack Internal / OverflowAI (Stack Overflow) | Internal Q&A + AI | Y | Y (community-verified) | N | N | N | Appears SaaS; unverified | Enterprise add-on |
| 28 | Bloomfire / Tettra / Shelf / Capacity | Knowledge platforms | Bloomfire Y | Partly | N | N | N | ? | Third-party: Bloomfire ~$25/user, Tettra ~$4/user |
| 29 | Onyx (open source) | Self-hostable enterprise RAG | Y | N | N | N | N | Y (Ollama/vLLM, claimed air-gapped) | Open source + paid tier |
| 30 | Ascendo AI | Service/support copilot | ? | Auto-generates knowledge from tickets | N | Partly | ? | ? | Not verified |
| 31 | iFactory, Dynamics 365 Guides | Plant copilot; AR guides | ? | Guides: expert capture planned | N | N | ? | ? | Guides: reported end of availability 31 Dec 2026 (secondary source) |

### E. NL-to-command tools

| # | Product (company) | Cites | Expert | Cmd | Warn | Ctx | On-prem | Pricing |
|---|---|---|---|---|---|---|---|---|
| 32 | Warp Agent Mode | N | N | Y (asks permission per command; allow/deny lists) | N | Partly (session context) | Enterprise BYO-LLM; ZDR | Enterprise plan |
| 33 | GitHub Copilot CLI | N | N | Y (approves tool calls) | N | ? | Y with BYOK/local models (Ollama, vLLM) and COPILOT_OFFLINE | Subscription |
| 34 | Kiro CLI (successor to Amazon Q CLI) | N | N | Y (per-tool trust; confirms commands) | N | ? | N (AWS) | Not verified |
| 35 | Microsoft AI Shell / Copilot in Azure | N | N | Y (Azure CLI/PowerShell generation) | N | N | N | Azure |

None of the E tools know NonStop (TACL, SCF, PATHCOM, TMF, etc.); those are generic shells.

## 3. Notes on the most relevant competitors

### Iris for HPE Nonstop (IR) - closest direct competitor
- Launched 17 Jun 2026; adds a conversational layer to the Prognosis Platform; "available now with Prognosis 13.3". Plain-language questions on health, performance and capacity; explanations, recommended next steps; faster root cause; summaries for non-specialists; capacity and batch planning.
- Not stated in the release: LLM used, cloud vs on-prem, data privacy, citations, pricing. A later PR Newswire correction re-framed Iris as a platform for mission-critical applications "such as" NonStop and said Prognosis is the only validated HPE Partner Technology solution mentioned.
- Strength: owns the telemetry and the install base. Weakness vs us: telemetry-only; no veteran knowledge, no manuals grounding stated, no command execution stated.
- Sources: https://www.aap.com.au/aapreleases/cision20260617ae85909/ ; https://tools.prnewswire.com/en-us/live/20813/release/20260617EN85909

### XYPRO Lionel
- 19 Feb 2026. Internal assistant that unifies manuals, support tickets, internal systems and specialist expertise into "verified answers". Customers may use it "eventually". XYPRO: "augments human expertise rather than replacing it". Closest in spirit to our Q&A pillar, but it is a vendor-internal support tool, not an operator-side product. No on-prem or citation format disclosed. Benefit claims are XYPRO's own.
- Sources: https://cioinfluence.com/security/partnerone-continues-investment-in-ai-with-xypro-applied-ai-technology/ ; https://www.aap.com.au/aapreleases/cision20260219ae91236

### Idelji ManAIge / iManAIge
- Article by Khody Khodayari (The Connection, 31 May 2026): analyzes transactions, logs, dependencies and metrics each minute; claims forecasts up to a year ahead; evidence-based explanation "in under 3 seconds"; can execute fixes autonomously "when authorized" (how authorization works is not described). iManAIge (Jan 2024 article) is described as SaaS, tests fixes in a "playroom" sandbox, and is expanding to z/OS.
- Learns from "human feedback", not from named veterans. Pure statistical/ML prediction; no manuals grounding mentioned. All claims are vendor-authored and unverified.
- Sources: https://connect2nonstop.com/manaige-intelligent-aiops-for-hpe-nonstop-servers/ ; https://connect2nonstop.com/meet-imanaige-the-future-of-ai-driven-enterprise-server-management/

### Infrasoft uLinga Nexus (MCP for NonStop)
- Articles by Andrew Price (Infrasoft), "AI meets Nonstop" series, 31 Mar and 31 May 2026. MCP turns Pathway servers and PATHCOM commands into tools an AI assistant can call; OAuth/JWT/TLS and audit trails; "curated capabilities rather than unrestricted backend access". No formal approval workflow described; the engineer "makes the call".
- Importance: this is an enabling layer and a possible integration path for us, but also shows that "LLM to NonStop commands via MCP" is becoming a standard pattern that any assistant (including Iris, Lionel or a Claude/Copilot client) could use. Whether a model runs on-prem is not addressed.
- Sources: https://connect2nonstop.com/ai-and-the-nonstop-advantage/ ; https://connect2nonstop.com/from-connectivity-to-capability-leveraging-ai-on-hpe-nonstop/

### Other NonStop AI items
- ETI-NET QoreStor Anomaly Detection: isolation-forest model on NonStop backup data, baseline learned over up to 90 days (data sheet). Narrow scope. https://connect2nonstop.com/wp-content/uploads/sites/8/2025/07/ETI-NET-QoreStor-Anomaly-Detection-Data-Sheet-2.pdf
- The Connection (May-Jun 2026) article "AI-Based Programming and Application Support in HPE NonStop Environments": code review, legacy documentation, EMS event analysis (a trade article, not a product; page URL sits under a "__trashed" path, so it may move). https://connect2nonstop.com/__trashed/
- TIC Software's TIC Navigator is mentioned in search coverage as a code-analysis tool (not verified further).
- HPE NRF 2026: NonStop retail solution paired with Aruba and Mist AIOps; AI is on the networking side, not NonStop operations. No HPE-branded NonStop operator copilot was found.
- INETCO Insight (NonStop Collector, BullzAI ML fraud scoring): payment monitoring, no operator copilot. https://connect2nonstop.com/?p=7866

### IBM watsonx Assistant for Z / Z AIOps / Concert for Z
- Agentic release announced (IBM): pre-built System Insights Agents query environments managed by IBM Z tools in natural language and use IBM Z knowledge plus customer documentation; Z ChatOps surfaces OMEGAMON/System Automation incidents in Slack/Mattermost with AI explanations and recommended actions; 60+ skills; Skills Studio low-code automation. Runs as containers on OpenShift. Kyndryl deploys it for customers.
- Why it matters: this is the template for what NonStop customers will compare us to. Not NonStop-aware and not built around capturing named retirees.
- Sources: https://www.ibm.com/new/announcements/ibm-watsonx-assistant-for-z-bringing-intelligence-and-automation-to-mainframe-it-management-with-agentic-ai ; https://www.ibm.com/new/announcements/ibm-watsonx-assistant-for-z-v2-1-expanding-generative-ai-conversations-with-ibm-z-operational-insights ; https://community.ibm.com/community/user/blogs/wolfgang-schberle1/2025/10/24/system-insights-agents-in-wxa4z

### BMC AMI Assistant
- Gen-AI assistant for mainframe: code explanation, COBOL-to-Java, root-cause explanation, "knowledge expert" chat; LLM library with bring-your-own-model; containerized/Kubernetes platform. Fully on-prem operation not confirmed in what I found.
- Sources: https://www.bmc.com/it-solutions/mainframe-ai.html ; https://devops.com/bmc-adds-ai-assistant-to-help-modernize-mainframe-applications/ ; https://docs.bmc.com/xwiki/bin/view/Mainframe/Common/BMC-AMI-Platform/amip21/Getting-started/Product-overview

### Rocket EVA + PlanGuard; Geniez AI acquisition
- Rocket EVA: agents correlate logs/metrics/operational data and can suggest or execute actions within policy limits; PlanGuard adds a policy decision point and identity checks, with all activity logged (itdaily, 24 Sep 2026). Rocket bought Geniez AI on 13 Oct 2026 (terms undisclosed) to put agents on the mainframe. On-prem not stated.
- Sources: https://itdaily.com/news/datacenter/rocket-software-deploys-managed-ai-agents-on-mainframes/ ; https://vmblog.com/?p=87283 ; https://dealroom.co/news/162095-rocket-software-buys-geniez-ai-to-put-agents-on-the-mainframe/

### Kyndryl, Broadcom
- Kyndryl announced Agentic AI Framework and agentic mainframe services for z/OS on 24 Nov 2025, with Kyndryl Bridge integration and watsonx Assistant for Z. https://www.nasdaq.com/press-release/kyndryl-launches-agentic-ai-framework-and-services-mainframe-2025-11-24
- Broadcom: Mainframe AIOps solution brief and a Futurum piece saying Broadcom builds AI with customers on their own on-prem data; I could not confirm a shipped gen-AI operator assistant. https://docs.broadcom.com/doc/MF-AIOps-SB ; https://futurumgroup.com/insights/innovative-mainframe-solutions-a-deep-dive-into-broadcoms-initiatives

### General AIOps
- PagerDuty: SRE Agent runs diagnostics, suggests remediation, executes after approval; self-hosted PD Automation Runner in early access (Sept 2026, per a third-party summary), starting with Kubernetes. https://www.admin-magazine.com/index.php/News/PagerDuty-Launches-End-to-End-AI-Agent-Suite ; https://www.plushcap.com/companies/pagerduty/blog/summaries/2026/09 ; https://www.pagerduty.com/de/blog/ai/sre-agent-enhancements-faster-triage-greater-access-controls-deeper-system-connectivity/
- Dynatrace Davis CoPilot: RAG, NL to DQL, agentic workflows in preview; docs warn answers can be inaccurate. https://docs.dynatrace.com/docs/discover-dynatrace/platform/davis-ai/copilot/copilot-overview
- Datadog Bits AI SRE: pricing moved to AI credits around June 2026 (third-party trackers; confirm on Datadog's pricing page). https://pricingsaas.com/companies/datadog/diffs/2026W24 ; https://betterstack.com/community/comparisons/bits-ai-sre-alternatives/
- ServiceNow Now Assist for ITOM: model providers listed as Now LLM, Azure OpenAI, Gemini, Claude on AWS; some features unavailable for self-hosted. https://www.servicenow.com/docs/r/u7nZu9GEUxWr9UkuDmbe6w/L5n_WNtwdY86_VBTJ0Zu7A
- Splunk AI Assistant for SPL: on-prem Splunk uses a "cloud connected" mode with Splunk-managed cloud AI, so not air-gapped. https://www.splunk.com/en_us/blog/artificial-intelligence/introducing-splunk-ai-assistant-for-spl-through-a-cloud-connected-solution-on-prem-ai-without-the-gpu-hassle
- BigPanda AI Incident Assistant: assembles SMEs by historical incident context (expert routing); runbook execution on roadmap. https://www.bigpanda.io/our-product/ai-copilot ; https://www.silicon.co.uk/press-release/bigpanda-launches-agentic-it-operations-to-bring-intelligent-automation-to-the-200-billion-itops-market
- HPE OpsRamp / GreenLake Intelligence: human-in-the-loop agentic ops across full-stack infrastructure. https://www.hpe.com/us/en/newsroom/press-release/2025/06/hpe-reimagines-hybrid-it-operations-with-greenlake-intelligence.html
- Moogsoft: no data retrieved (search returned nothing).

### Knowledge-capture and expert tools
- Starmind: expert finder in Teams/Slack plus "Retain" knowledge suite; deployment and offboarding fit unverified; custom pricing. https://www.starmind.com/how-starmind-works
- Sensay: "AI Offboarding" launched Nov 2025: structured AI voice interviews, handover brief, searchable transcript, chatbot in Slack/Teams. Its Q4 2026 retiring-SME product is a company-stated plan, unverified. https://www.barchart.com/story/news/36018738/sensay-launches-worlds-first-ai-offboarding-platform-for-knowledge-transfer
- KNOWRON: only a third-party directory describes it (German, founded 2020, retiring-worker feature); check knowron.com. https://www.datanyze.com/companies/knowron/556753924
- Augmentir (Augie): documents expert procedures for frontline workers (manufacturing). https://www.augmentir.com/tag/augie/page/2
- Rockwell Maintenance Copilot: workers' expertise + manufacturing data + manuals; reported 33 percent downtime reduction at Singapore plant (Microsoft-hosted case study). https://news.microsoft.com/source/features/digital-transformation/rockwell-automation-pairs-ai-with-decades-of-shop-floor-know-how-so-workers-can-solve-glitches-faster/
- Guru: citations and audit trails; enterprise pricing custom. https://www.getguru.com/pricing
- Glean: on-prem reported with Dell (Sacra) but another source disputes; ~$50+/user/mo estimate is third-party. https://sacra.com/research/glean/ ; https://www.premai.io/blog/12-best-glean-alternatives-for-private-enterprise-ai-search-2026/
- Stack Internal (ex Stack Overflow for Teams): OverflowAI is a paid Enterprise add-on; MCP server; on-prem not confirmed. https://stackoverflow.blog/releases/internal/
- Bloomfire / Tettra / Shelf: https://www.docsie.io/vs/bloomfire-vs-tettra/ ; https://www.g2.com/compare/shelf-shelf-vs-tettra-vs-guru
- Ascendo AI: listing-only evidence. https://www.getapp.com/all-software/a/ascendo-ai/
- iFactory: vendor blog only. https://ifactoryapp.com/blog/ai-copilot-manufacturing-operations-maintenance-assistant
- Dynamics 365 Guides: Copilot "expert knowledge" announced at Ignite 2023; a podcast summary (secondary) reports end of availability 31 Dec 2026. https://microsoft.com/en-us/dynamics-365/blog/product/dynamics-365-guides ; https://www.m365.fm/dynamics-365-guides-simply-explained/
- Onyx (open source): self-hosted RAG with citations, Ollama/vLLM, claimed air-gapped use (hosting-vendor pages, not Onyx docs). https://jimmysong.io/ai/onyx

### NL-to-command tools
- Warp: asks permission before each command; allow/deny lists; ZDR and BYO-LLM on Enterprise. https://docs.warp.dev/features/warp-ai/agent-mode
- GitHub Copilot CLI: BYOK/local models (Ollama, vLLM, Foundry Local) and offline mode since April 2026. https://github.blog/changelog/2026-04-07-copilot-cli-now-supports-byok-and-local-models/ ; https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models
- Kiro CLI (released 18 Nov 2025, successor to Amazon Q Developer CLI): per-tool trust controls. https://dev.classmethod.jp/en/articles/kiro-cli-macos-install-guide/ (permission docs are from a dev docs host, verify).
- Microsoft AI Shell (Copilot in Azure agent): NL to Azure CLI/PowerShell; needs Azure login. https://learn.microsoft.com/en-us/azure/copilot/ai-shell-overview

## 4. Gaps none of them fill (our differentiators)

1. **Named-veteran knowledge as a first-class, cited source.** NonStop vendors (Lionel, Iris) ground in manuals/tickets/telemetry; knowledge-capture tools (Sensay, Starmind) are generic and not tied to operational answers. Nobody found cites "according to <named veteran>, doc X" next to a manual citation for NonStop.
2. **Veteran warning patterns turned into early-warning rules over events/metrics.** Vendors do statistical anomaly detection (ManAIge, Prognosis, ETI-NET). None found encodes human experts' "when you see A then B, trouble in N hours" heuristics with attribution.
3. **Strict context-gating (node / OS version / subsystem).** No vendor in our research documents refusing to apply guidance for system A to system B. Mark as an absence of public evidence, not proof.
4. **NL-to-NonStop command with explicit operator approval, grounded in citations.** Generic CLIs (Warp, Copilot CLI, Kiro) do approval but know nothing about TACL/SCF/PATHCOM; ManAIge mentions authorized autonomous fixes; uLinga MCP exposes tools but has no approval flow described.
5. **Fully local/air-gapped by design.** Most gen-AI ops tools are SaaS or cloud-connected (Splunk, Datadog, ServiceNow, iManAIge). Exceptions: Copilot CLI with local models, Onyx, IBM/BMC containers (completeness of air-gap unverified). None are NonStop-specific and local.
6. **Operator-side delivery.** CAIL's 6530 terminal is where operators already sit; none of the competitors is delivered inside the terminal/console workflow (to confirm with CAIL).

## 5. Threats (who could copy us fast)

- **IR (Iris)**: owns telemetry and customers; adding a document/knowledge layer and an approval-gated action layer is a plausible next step. Biggest risk. Watch for on-prem LLM and citation support in the next Prognosis release.
- **XYPRO (Lionel)**: already has the "verified answers from manuals plus specialists" thesis; going customer-facing is explicitly planned.
- **Idelji (ManAIge)**: already has predictive warnings and authorized remediation; could add an LLM front end.
- **Infrasoft (uLinga Nexus MCP)**: lowers the cost of any agent talking to NonStop; any generic assistant (including Claude/Copilot clients) can use it. Treat as ecosystem plumbing and a partnership/integration option.
- **IBM / BMC / Rocket**: could extend their ops agents to NonStop if demand appears; Rocket's Geniez purchase (Oct 2026) shows rapid consolidation.
- **HPE**: could bundle an assistant into NonStop or GreenLake (no evidence yet).
- **Open-source DIY**: Onyx or similar plus Ollama plus MCP could approximate the Q&A pillar in-house for a bank's own team; our moat is the veteran knowledge graph, context-gating and NonStop command grounding, not generic RAG.

## 6. Positioning lines for the pitch

1. "Every answer shows its source: a manual page or a named veteran. If it can't cite it, it won't say it."
2. "Your best NonStop operators are retiring. We turn what they know into warnings and answers the whole team can use, with their names on them."
3. "It never applies node A's fix to node B: every instruction is checked against the system, OS version and subsystem it was written for."
4. "Plain English in, a command out, and nothing runs until an operator approves it."
5. "It runs entirely on your hardware, with no cloud and no data leaving the data center, which is what a bank or telecom on NonStop requires."

## 7. Items I could not verify (do not claim in the pitch without checking)

- On-prem/air-gap status for Iris, Lionel, ManAIge, BMC AMI Assistant, Rocket EVA, Kyndryl, Dynatrace Managed, Stack Internal, Starmind, Sensay, KNOWRON, Augmentir.
- Whether Iris cites sources or uses approval gating (release is silent).
- Any shipped Broadcom gen-AI mainframe assistant; any comforte, Gravic/Shadowbase, NuWave, Insider Technologies (Reflect/Sentinel), TCM/Lusis Payments, IR Transact (separate AI), Euronet or ACI BASE24-operations AI product (searches found nothing; ACI's 2026 AI statements concern engineering productivity, fraud and routing, per earnings-call coverage https://www.webull.com/news/15706516416709632).
- Moogsoft/Dell: not retrieved. Capacity: not found.
- Exact pricing: nearly all vendors do not publish; third-party figures (Glean, Guru, Datadog, Bloomfire, Tettra) are estimates.
- Glean on-prem (sources conflict); PagerDuty self-hosted runner GA status; Dynamics 365 Guides end-of-availability (secondary source); Sensay Q4 2026 roadmap; KNOWRON details (third-party directory only).
- All productivity or accuracy claims (Lionel, ManAIge, Sensay, Rockwell, iFactory) are vendor statements with no independent verification.
