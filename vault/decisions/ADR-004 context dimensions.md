# ADR-004 context dimensions

**Date:** 2026-10-17 · **Status:** proposed (pending team review of [[system design]])

**Context:** the kit's fingerprint (system/version/site) was written for plants. NonStop context is
node (`\PROD`/`\DR`), series/RVU (L/J/H), subsystem (TMF, Pathway, SCF STORAGE…), personality (Guardian/OSS).

**Decision:** keep the columns, change their meaning:
`system_id` = subsystem · `version_id` = series/RVU · `site_id` = node. Docs are typically
`all_sites = true` (apply to every node); veteran heuristics are often node-scoped.
Personality is a later column if needed.

**Why:** zero schema churn, [[retrieve]] filter and [[tests]] keep working; node-scoping is exactly
the "same buttons, different system" trap CAIL described.

**Consequence:** rename columns later for readability (cosmetic). Entity ids: `sub:TMF`, `rvu:L`, `node:PROD`.
