# frontend

Task-based CAIL operations workspace in `frontend/` (Next.js App Router + Tailwind). A Google Drive-inspired
sidebar opens Overview, Systems, Investigations, AI Assistant, Knowledge and Training Simulator. The terminal-first
layout was removed; command output remains simulated evidence inside the assistant workflow.
Contract: [[api contract]] (v2 section authoritative). Run instructions: `frontend/README.md`.
Static public demo export uses `frontend/next.config.mjs`; `.github/workflows/deploy-frontend.yml` deploys it to
GitHub Pages at `https://ghousee.github.io/catalyst-2026-team31/` after a change lands on `main`.

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

## Real vs demo in OperationsWorkspace (2026-10-17, rewired)
`OperationsWorkspace.tsx` was rewired from hardcoded demo content to live data (styling untouched). **Bernard: pull main before further changes to it.**
- **Real:** Overview cards (nodes from `/session`, subsystems from `/graph`, healthy indicators = `/metrics` latest < `METRICS` limit); System health charts (simulator metrics);
  Systems page (node x subsystem from `/graph`, notes in scope, manual sections from `/documents`, live metrics only for the session node where the graph's `met:` parent matches); Knowledge page (`/documents` + `/knowledge?status=approved`, links to `/knowledge` and `/documents`);
  Knowledge graph page (`components/KnowledgeGraphPage.tsx`, `/graph` polled every 10 s, SplitPane panes, `useGraph` shared with Systems/Overview); Assistant, commands, simulator.
- **Demo:** alerts. `api.getAlerts` is always the mock while `USE_MOCKS` (`ALERTS_ARE_MOCK` in `lib/api.ts`; no endpoint group yet). Active alerts card, AI operational summary (top alert), Needs attention rows, Investigations badge and page are labelled "demo".
- Header label is computed from `liveGroups()` (`NEXT_PUBLIC_REAL_ENDPOINTS`): "Live: knowledge · graph · ... — Demo: alerts ...".
- `lib/admin.ts` `admin.graph()` + `GraphSnapshot` type. `ClarifyCard` hides the button row when `options` is empty.

## Learning map (2026-10-17)
`components/LearningPage.tsx` (nav item right after "Knowledge graph" in `OperationsWorkspace.tsx`), client `lib/learning.ts` (real API, no mocks).
Operator picker (default `USER_ID`), 4 tiles, per-subsystem table with a coverage bar, never-touched list, recent questions, veterans learned from; `SplitPane` panels,
polls every 15 s. Header says it shows encounters, not what the operator knows. Backend: [[api]] "Learning map".

## Teach panel (2026-10-17)
- `components/TeachChat.tsx` (top-left of `/knowledge`, SplitPane `knowledge-left` above the manual form): pick who teaches, chat via `admin.teach` (`POST /knowledge/teach`), assistant follow-ups inline,
  then an editable draft (4 texts + node/subsystem/kind) -> Save draft (`admin.addNote`, entered_by = owner) -> shows in Pending sign-off -> existing Approve & sign (links + suggested sections).

## Knowledge graph view (2026-10-17)
`components/GraphCanvas.tsx` (vis-network 9.1.9 + vis-data 7.1.9, pinned): live view of GET /graph inside
`KnowledgeGraphPage` ("Graph" tab; "Tables" tab = the old tables). Opens on the curated core; manual-extracted
entities (ids `cmd:auto:<sub>:..`, `evt:auto:<sub>:..`, ~1,660) behind a checkbox + subsystem picker. Network is
created once and updated in place (`ready` flag re-syncs after the async import - without it the canvas stayed blank).
Drag, zoom, click = details panel, double-click = isolate neighbourhood, kind filters, find, auto links dashed.

## Design system (2026-10-17 light-blue redesign)
Direction: light, airy, colourful and friendly. Near-white paper with a blue tint, navy for strong elements, sky blue for fills and highlights, a few category colours. Presentation only; no data/logic changes.
- **Fonts:** Bricolage Grotesque (headings, big numbers; `font-display`), Figtree (UI), IBM Plex Mono (commands, `\PROD`, ids), all via `next/font/google` in `app/layout.tsx`.
- **Tokens** (`app/globals.css`, light and dark): `bg #F2F7FD`, `panel #FFF`, `panel2 #E9F3FC`, `line #D3E2F2`, `fg/head #0E2342`/`#0B2A64`, `muted #4C6381`, `accent #144CAA` (links), `navy #0B2A64` / `navy2 #1B56B2` (sidebar, primary buttons), `sky #38A8F0` / `skysoft #DEEFFD` (fills, tints), status `ok #0A7C54`, `warn #965C00`, `crit #C52838`. `\PROD` `#D9480F` coral-orange, `\DR` `#6A3FC4` violet (never a blue). Subsystem colours `--sub-tmf/pathway/scf/tacl/peek/measure/fup`; lanes use info (Doc), warn (Veteran), ok (Live). Never hard-code colours in components.
- **Tailwind config:** the theme is `tailwind.theme.ts`, loaded by `@config` at the top of `globals.css`; `tailwind.config.ts` re-exports it. (A running dev server caches `tailwind.config.ts`; a new file path is picked up without a restart. Restart `next dev` once, then it is fine to rename back.)
- **Shared pieces** (`components/ui.tsx`): `PageHeader` (gradient band), `StatCard` (tinted, coloured icon chip, count-up), `Panel`, `SubPill` (coloured subsystem pill), `CountUp`, `Skeleton`, `hueStyle`. CSS helpers: `.pill`, `.tint`, `.icon-chip` (set `--c`), `.card`, `.btn`, `.btn-primary` (navy gradient), `.chip`, `.field`.
- **Motion** (all CSS keyframes in `globals.css`, no GSAP; `prefers-reduced-motion` turns it all off, `CountUp` jumps to the final value): `.rise` page entrance, `.stagger` children, `.lift` card hover, `.flow-band` animated gradient (top bar, sidebar header), `.draw` sparkline wipe, `.bar-grow` coverage bars, `.live-dot` pulse (Watcher status, active alerts, nav badge), `.skeleton` shimmer while loading, `.tab` sliding underline.
- **Status** = text label + round dot (`.status-chip`), never colour alone. Lane, risk and approval labels stay in text. `.label`, `.code`, `.num` type helpers remain.
- **Assistant replies** (`ReplyText.tsx`): `` `code` `` as `<code>`, `**bold**`, citations `[1]` as small chips opening the source card, cited sources as a footnote list.
- Copy: no emoji or sparkles.

## Who is using the app (lib/me.ts, WhoAmI.tsx)
Top-bar picker, remembered in localStorage (`cail.me`). Seniors = person rows (Teach/owner default to them);
"New here?" starts a junior under any name -> their own Learning map (keyed by `toUserId(name)`). Chat, refer and
approve send `userId()` read at call time (store.tsx). Learning map: "Said they know" column (PUT /learning/{id}/self,
table `self_level`, migration 005) and "Share something you found" (POST /knowledge, owner = a senior, entered_by = the
junior; draft until that senior signs). Knowledge page: "Add a senior" (POST /persons).

## Knowledge check and Synapse deep links
- Learning map has "Check what I know" (own map only): `learning.check` / `learning.answer` in `lib/learning.ts`; a passed answer adds a `knows` link user -> note. Extra stat card "Demonstrated" and a "Checked" column (passed/tried).
- `/?page=graph&focus=<node id>` opens Synapse with that node isolated and centred (`OperationsWorkspace` reads the query on mount). Used by "See it in Synapse" in the check result and after signing on `/knowledge`.
- GraphCanvas: links with `created_by` auto (sky blue) and check (green) are thicker and in the legend; "Show latest change" isolates the newest signed note.
