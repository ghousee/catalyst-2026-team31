# frontend

Task-based CAIL operations workspace in `frontend/` (Next.js App Router + Tailwind). A Google Drive-inspired
sidebar opens Overview, Systems, Investigations, AI Assistant, Knowledge and Training Simulator. The terminal-first
layout was removed; command output remains simulated evidence inside the assistant workflow.
Contract: [[api contract]] (v2 section authoritative). Run instructions: `frontend/README.md`.

## Entry points
- `frontend/app/page.tsx` -> `components/Console.tsx` -> `components/OperationsWorkspace.tsx` (responsive shell, pages, provider)
- `frontend/lib/types.ts` — types mirroring the contract, field names exact
- `frontend/lib/api.ts` — client; `NEXT_PUBLIC_USE_MOCKS` (default true) routes to `mocks/server.ts`, else `fetch` to `NEXT_PUBLIC_API_URL`
- `frontend/lib/store.tsx` — `ConsoleProvider`: session, chat messages, terminal lines, source dialog, execute -> terminal + live citation
- `frontend/components/ProposalCard.tsx` + `ApprovalControls.tsx` — dry run, approval by `approval.required`, guards, execute
- `frontend/components/AlertsPanel.tsx`, `HealthPanel.tsx` — polling (alerts 2 s, metrics 4 s) via `lib/hooks.ts` `usePolling`
- `frontend/components/SourceDialog.tsx`, `CitationChip.tsx` — doc / veteran / live source cards

## Real backend + answer checks (2026-10-17)
- `lib/api.ts`: `NEXT_PUBLIC_REAL_ENDPOINTS=session,chat,sources` sends only those groups to [[api]]; the rest stays mocked (`.env.local.example`). Mocked propose tracks the mock's node, not the real session's.
- Subsystem override ids now match the graph (`sub:SCF-STORAGE`, `sub:PEEK`; were `sub:STORAGE`, `sub:CPU`) in `lib/format.ts` and mocks.
- `quality?` on answer/refer (`lib/types.ts` `Quality`) -> one-line strip `components/AnswerChecks.tsx` at the bottom of the answer card (warn tone if dropped > 0, support min < 60% or gate failed). Mock answers carry a fake `quality`.
- Header badge `components/AccuracyBadge.tsx` reads `lib/pilotStats.ts` (pilot-set numbers; update after the next eval run).

## How mocks map to the contract
- `mocks/fixtures.ts` — sources (doc, maria:h7, maria:h11 `contradicts`, raj:h3, lena:h4), command catalog (cmd-17 audit trail, cmd-18 STATUS TRANSACTION, cmd-19 ABORT, cmd-20 SCF, cmd-21 PATHCOM, cmd-22 PEEK, cmd-23 STATUS TMF, cmd-24 TACL).
- `mocks/server.ts` — stateful in-browser backend: session node, executed runs, approvals, scenario clock. Responses are the contract shapes. Keyword routing in `topicOf`.
- Hero flow: `\PROD` audit question -> doc+veteran(+live after a run) claims; `\DR` -> doc-only + Raj; "disk" -> `clarify`; unknown -> `refer`.
- Approval rules in mock: second_approver needs a 2nd `approve` with `second_approver` set; node guard re-checked on approve (rejected if session node changed); approval is single-use.

## Gotchas
- Mock state is module-level and resets on page reload.
- Only the hero scenario changes alerts/metrics in the mock.
- Metric thresholds are hard-coded in `HealthPanel.tsx` (contract has none).
- After execute the UI calls `/commands/propose` with question "what next after this output?" to get the follow-up command; mock keys on that phrase and on the last run.
- Second approver is simulated client-side (auto-approves after 3 s with `second_approver: "raj"`).
- Dark theme default; theme stored in `localStorage` (try/catch), applied before paint in `app/layout.tsx`.
- Light theme is now the default; dark theme remains available and is stored in `localStorage`.
- Global demo/synthetic-data banners make the no-production boundary visible on every page.

## Contract gaps (not edited in docs/API_CONTRACT.md)
1. No source lookup: `proposal.source_id`, alert `fix_claims[].source_id` have no `sources[]`. UI assumes `GET /sources/{id}` -> a `Source`.
2. Alert has no `sources`; alert chips fall back to the lookup above.
3. No thresholds in `/metrics`; no units.
4. No way to feed live command output into `/chat` (so "live" claims in answers); the UI builds its own live citation from `/execute`.
5. No "what next" endpoint after execute; UI re-uses `/commands/propose`.
6. `/commands/{id}/approve` for `second_approver`: no flow for polling/waiting; `needs_second_approver` then client re-posts with `second_approver` (assumed).
7. `/commands/propose` ids: unclear if stable across calls; alert `next_commands` and chat proposals may share ids.
8. `refer` request `context` is nullable in UI when no answer context exists; `/refer` response has no thread/status polling.
9. Doc source `applies_to` etc. only in v2; v1 `heuristic.provenance` and v2 `captured_via/captured_at` overlap.
10. `/chat` `answer` has `experts` but no flag saying "veteran lane empty because of scope"; UI infers "documentation only" from claims.
11. `/feedback` is not wired in the UI yet.
12. Errors: no error body schema; UI shows raw text.

## Referrals (changed 2026-10-17, Ghouse)
Refer/expert UI is **reference only**: `components/ExpertList.tsx` shows name, availability badge, role ·
team · years, expertise tags, why-this-person, contact. No "Ask" button; `api.refer` / `referExpert` in
`lib/store.tsx` are unused until the capture loop is built. Expert fields: `lib/types.ts` `Expert`.

## Verbatim / conflict fields (2026-10-17, additive in `lib/types.ts`)
- `Claim.verbatim?` (veteran's own words; ClaimList shows "verbatim" instead of a score), `Claim.conflict_with?` (other veteran's source id),
  `Claim.contradicts?` (doc id the note contradicts), `HeuristicSource.not_when?` (SourceDialog "Does not apply when" box).
- `components/ConflictBox.tsx`: groups flagged claims into "Veterans disagree: A vs B" / "Veteran contradicts the manual: A vs <manual>";
  `AnswerCard` renders flagged claims there and the rest in `ClaimList`.
- Edition line in `AnswerCard`: if a doc source's `applies_to` lacks `<series>-series` (series from `context.version`), shows
  "Manual citations come from older H/J-series editions; L-series behaviour not verified."
- Mocks unchanged (fields optional). Checked with `tsc --noEmit` + `lint` only.

## Knowledge + documents screens (2026-10-17)
- `/knowledge` (`components/KnowledgePage.tsx`) and `/documents` (`DocumentsPage.tsx`): plain screens that call the real API directly via `lib/admin.ts` (no mocks; errors shown in a red bar).
  Knowledge: add form | pending sign-off (Approve & sign -> auto links + suggested sections with agrees/contradicts/skip) | approved list with the needs-review flag.
  Documents: upload form, last diff summary, documents list, notes needing re-check.
- `components/SplitPane.tsx`: tiny draggable divider (pointer events, arrow keys, size saved in localStorage, `role="separator"`); used only on these two pages.
  The console is NOT resizable here (feat/ui-redesign owns Console.tsx); `Console.tsx` is untouched.
- `TopBar.tsx` got nav links (Console / Knowledge / Documents). `ClaimList.tsx` and `SourceDialog.tsx` show the needs-review warning (`needs_review?` in `lib/types.ts`).
- Command cards stay mocked (the command workflow lives on the teammate's branch).
