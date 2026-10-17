# NonStop Copilot — frontend

Next.js (App Router, TypeScript, Tailwind) operator console: simulated CAIL 6530 terminal on the left,
copilot (health, alerts, chat, command approval) on the right. Dark theme by default, light toggle in the top bar.

## Run (Windows / PowerShell)

```powershell
cd frontend
npm install
npm run dev            # http://localhost:3000, mock mode (no backend needed)
npm run lint
npm run build
```

## Mock vs real API

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_USE_MOCKS` | `true` | `false` sends real HTTP calls to the backend |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI base URL |

Real API in PowerShell (no inline env syntax in 5.1):

```powershell
$env:NEXT_PUBLIC_USE_MOCKS = "false"
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

Or copy `.env.example` to `.env.local` and edit it. Restart `npm run dev` after changing env.

## Demo script (mock mode)

1. Page loads on `\PROD`. After ~5 s the alert from Maria's pattern (`maria:h7`) appears (Demo menu, "Audit trail filling", triggers it immediately and raises the audit metric).
2. Ask "why is the audit trail filling?" -> answer with doc + veteran claims, one claim dropped, proposed `TMFCOM STATUS AUDITTRAIL, DETAIL`.
3. Approve, Execute -> output in the terminal, a live citation appears, next step `STATUS TRANSACTION` is proposed, then critical `ABORT TRANSACTION \PROD(1).3.45678` (dry run required, second approver, simulated).
4. Switch node to `\DR` (confirm dialog), ask the same question -> doc-only answer and Raj Patel as expert. Old proposals become blocked by the node guard.
5. "the disk is acting up" -> clarify card. "why did the nightly reconciliation hang?" -> refer card.

See `vault/code/frontend.md` for the code map and contract gaps.
