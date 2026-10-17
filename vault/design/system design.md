# system design

Full doc: `docs/SYSTEM_DESIGN.md` (draft, awaiting team review). This note = the parts you need while coding.

**Product:** NonStop operator copilot beside the CAIL 6530 session. Four engines:
Ask (§9) · Command copilot (§6) · Watcher (§7) · Capture (§8). Everything runs on a simulator (§13).

**Context = node + series/RVU + subsystem** (from the emulator session, not the prompt).
Schema mapping: `site_id`→node, `version_id`→series/RVU, `system_id`→subsystem. See [[ADR-004 context dimensions]].

**Citation lanes:** 📘 doc · 👤 veteran · 🖥 live command output · ⚪ refer. See [[core requirements]].

**Never an LLM:** risk classification, node guard, RVU guard, trigger matching. LLM = glue text + template slot filling.

**Command risk:** 🟢 read-only · 🟠 state-changing (approve + type node) · 🔴 critical (second approver).
Classify by the full parsed command (`STATUS *, STOP` is not read-only).

**Hero scenario:** `\PROD` audit trail filling at quarter-end; Maria's trigger; `\DR` context trap.

Code notes will link here as modules land: simulator, commands, watcher.
