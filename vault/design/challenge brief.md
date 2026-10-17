# challenge brief (CAIL, Team #31) — official text, received 2026-10-17

**Challenge statement:** "How might we use AI to help the next generation of IT operators understand, monitor, and
troubleshoot mission-critical enterprise systems through natural language, while preserving the expertise of
experienced professionals?"

## Context
- CAIL: connectivity/terminal access software for mission-critical systems incl. HPE NonStop (one of three such companies).
- NonStop: fault-tolerant transaction platform (banking/ATMs, retail payments, telecom, enterprise finance).
- Knowledge gap: at one bank ~5 of 20 experienced ops staff retired within six months. Docs exist but miss practical judgment.
- **Illustrative scenario CAIL described:** an unexpected hardware failure at a major financial institution reduces
  processing capacity; transactions slow; remaining infrastructure takes the extra load. An expert recognises the
  warning signs, which components are affected, and which diagnostic commands to run. A junior must navigate
  unfamiliar tools while the risk of wider disruption grows.
- Problems listed: complex commands; loss of expert knowledge (unusual patterns, undocumented troubleshooting);
  disconnected information (several data sources, monitoring tools, alerts); interconnected risks (one component
  affects others); high reliability requirements.
- "The opportunity is not to replace existing monitoring tools, but to make them more accessible and intelligent."

## Mission: four capabilities (one or more)
1. Natural language -> commands, human approval before execution.
2. Understand & monitor system health: explain metrics/alerts, identify unusual patterns.
3. Preserve & apply expert knowledge: docs, **historical incidents**, troubleshooting procedures, expert feedback.
4. Guide troubleshooting: diagnostic checks, **explain risks**, **relationships between components**, next steps.

## Requirements
Accuracy & reliability (grounded, **uncertainty clearly identified**) · human oversight · explainable AI ·
knowledge preservation (improves over time) · complement existing monitoring tools · security & privacy (no production,
no customer data, no real transactions) · ease of use for varying expertise. Simulated data allowed; **state assumptions
and limitations**. At least **one realistic end-to-end scenario**: operator asks -> gets guidance -> decides next step.
No live NonStop connection needed.

## Judged on
Practical usefulness, technical feasibility, accuracy, user experience, potential to improve enterprise operations.
Success = simplify operations, preserve expertise, faster troubleshooting, earlier problem detection, trust in AI
(accurate, explainable, human oversight), extend existing monitoring tools.

See [[core requirements]] for our angle and the CAIL steer from the meeting.
