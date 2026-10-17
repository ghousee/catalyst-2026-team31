# core requirements

From Ghouse (2026-10-16/17), on top of CAIL's brief. These are non-negotiable for [[system design]].

1. **Warning signals from veterans.** Experienced operators recognise early signs of a coming failure
   (e.g. a pattern of EMS events/metrics before a CPU or disk problem). Capture those as trigger
   patterns and fire them proactively for the new operator — before the failure.
2. **Veteran knowledge must be saved and used.** Every response a new operator gets should draw on
   captured expert knowledge where it applies, not just the manuals.
3. **Citations on everything, with two kinds of source:**
   - **which documentation** (manual, section, version it applies to), and
   - **which veteran** said it (name, when, how it was captured — interview/incident/referral answer).
   A claim with no source is dropped. Expert claims are visibly attributed ("per <name>, captured <date>").
4. **Context first** (CAIL's #1 concern): never apply system A's instructions to system B.
5. **Human approval** before any command executes (simulated execution only).

Maps to: heuristic table (owner, provenance) in [[schema]]; doc vs veteran lanes in [[api contract]];
watcher triggers (`is_trigger`, `precedes` edges).

## Update 2026-10-17 (Ghouse, after meeting CAIL)
6. **The goal is training speed:** get a junior IT operator to senior level as fast as possible. Answers must teach
   the reasoning (why / when not), not just the fix; practice on replayed incidents ("Drill mode") and progress
   tracking are core, not extras.
7. **Integrate with existing monitoring tools** CAIL's customers use (IR Prognosis; "momoi" - product to confirm,
   possibly Idelji MOMI). Warnings come from those tools' events/metrics as a REAL-TIME stream: tools push to us
   (webhook / syslog / SNMP trap / Kafka) or we poll their local API, inside the customer network; one adapter per
   tool -> one normalised event -> watcher. The demo replays a recorded feed through the same pipeline.
   Research: docs/INTEGRATIONS.md.
