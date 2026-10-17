# frontend/CLAUDE.md — rules for anyone (or any agent) working on the UI

Read the root `CLAUDE.md` first, then `vault/code/frontend.md` and `docs/API_CONTRACT.md`.
The UI is the NonStop operator console: terminal pane, copilot chat with cited answers, alerts, health.

## Hard rules
1. **Keep it simple.** Smallest change that works. No new frameworks, state libraries or UI kits.
   Ask Ghouse before adding any npm dependency (GSAP is pre-approved; respect `prefers-reduced-motion`).
2. **Stay in `frontend/`.** Never edit `backend/`, `sql/`, `kg/`, `eval/`, `scripts/`, `data/`, `.claude/`,
   `docker-compose.yml`, or `docs/API_CONTRACT.md`. You may update `vault/code/frontend.md` and `frontend/README.md`.
3. **The API contract is fixed.** `lib/types.ts` mirrors `docs/API_CONTRACT.md`. Don't rename or remove fields or
   change shapes. If the UI needs something new, write it down under "Contract gaps" in `vault/code/frontend.md`
   and ask Ghouse; the backend is built against these types.
4. **Don't break the mock/real switch** in `lib/api.ts` (`NEXT_PUBLIC_USE_MOCKS`, `NEXT_PUBLIC_REAL_ENDPOINTS`).
   The demo must run with no backend. Mocks in `mocks/` must keep matching `lib/types.ts`.
5. **Never run `npm run build` / `next build`** while a dev server may be running (it breaks `.next/`).
   Check your work with `npx tsc --noEmit` and `npm run lint`.

## UX that must not regress (these are the product)
- The node (`\PROD` / `\DR`) is always prominent; switching node needs a confirm.
- Every claim shows its lane in text (Doc / Veteran / Live) and a citation chip that opens the source card.
- Veteran source cards show who, role, years, how and when captured, scope, and "contradicts …" when present.
- Referrals are reference only: who to talk to, role, availability, contact. No send-message button.
- Command cards: risk badge in text; failed guard blocks the buttons; critical commands need a second approver;
  state-changing commands need the node typed.
- The "Answer checks" strip and the "Test-set accuracy" badge stay (numbers come from the backend / one constants file).
- Fictional veterans stay labelled as fictional/demo data.
- Accessibility: colour is never the only signal, icon buttons have aria-labels, visible keyboard focus.

## Demo script that must keep working (mock mode)
1. Maria's alert shows on load. 2. "why is the audit trail filling?" → doc + veteran claims, proposed
`TMFCOM STATUS AUDITTRAIL, DETAIL` → approve → execute → output in terminal. 3. Follow-ups to the critical
`ABORT TRANSACTION` (dry run, second approver). 4. Switch to `\DR`, same question → different answer, no Maria
`\PROD` note. 5. "the disk is acting up" → clarify. 6. "why did the nightly reconciliation hang?" → refer card.
Click through this before every PR.

## Git
- Work on branch `feat/ui` (or `feat/ui-<topic>`). Never push to `main`; never force-push. Open a PR to `main`.
- Bring in backend changes often: `git fetch origin; git merge origin/main`. Expect conflicts in `lib/types.ts`,
  `lib/api.ts`, `mocks/` and `components/AnswerCard.tsx`; keep both sides' fields.
- Small commits, clear messages, no "Co-Authored-By: Claude" lines.
- Never commit `.env.local`, `node_modules/`, `.next/`, or any company data.
