# frontend

Operator console in `frontend/` (Next.js App Router + Tailwind). Left: simulated CAIL 6530 terminal (read-only).
Right: health sparklines, watcher alerts, chat with cited claims, command proposal/approval cards.
Contract: [[api contract]] (v2 section authoritative). Run instructions: `frontend/README.md`.

## Entry points
- `frontend/app/page.tsx` -> `components/Console.tsx` (layout, provider)
- `frontend/lib/types.ts` — types mirroring the contract, field names exact
- `frontend/lib/api.ts` — client; `NEXT_PUBLIC_USE_MOCKS` (default true) routes to `mocks/server.ts`, else `fetch` to `NEXT_PUBLIC_API_URL`
- `frontend/lib/store.tsx` — `ConsoleProvider`: session, chat messages, terminal lines, source dialog, execute -> terminal + live citation
- `frontend/components/ProposalCard.tsx` + `ApprovalControls.tsx` — dry run, approval by `approval.required`, guards, execute
- `frontend/components/AlertsPanel.tsx`, `HealthPanel.tsx` — polling (alerts 2 s, metrics 4 s) via `lib/hooks.ts` `usePolling`
- `frontend/components/SourceDialog.tsx`, `CitationChip.tsx` — doc / veteran / live source cards

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
