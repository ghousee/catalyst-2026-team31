"use client";

import { RefreshCw, ServerCrash } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CHAT_IS_MOCK } from "@/lib/api";
import { useConsole } from "@/lib/store";
import { AccuracyBadge } from "./AccuracyBadge";
import { Badge } from "./Badge";
import { DemoMenu } from "./DemoMenu";
import { NodeBadge } from "./NodeBadge";
import { NodeSwitcher } from "./NodeSwitcher";
import { ThemeToggle } from "./ThemeToggle";

const PAGES = [
  { href: "/", label: "Console" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/documents", label: "Documents" },
];

export function TopBar() {
  const { session, sessionError, retrySession } = useConsole();
  const path = usePathname();
  const prod = session?.node_display.toUpperCase().includes("PROD");
  return (
    <header
      className={`flex h-12 shrink-0 items-center gap-4 border-b-[3px] bg-panel px-4 ${session ? (prod ? "border-prod" : "border-dr") : "border-line"}`}
    >
      <h1 className="text-[15px] font-semibold tracking-tight">NonStop Copilot</h1>
      <nav aria-label="Pages" className="flex items-center gap-1 text-[13px]">
        {PAGES.map((p) => (
          <Link
            key={p.href}
            href={p.href}
            aria-current={path === p.href ? "page" : undefined}
            className={`border-b-2 px-1 py-1 ${path === p.href ? "border-accent font-semibold text-fg" : "border-transparent text-muted hover:text-fg"}`}
          >
            {p.label}
          </Link>
        ))}
      </nav>
      <div className="h-6 w-px bg-line" aria-hidden="true" />
      {session ? (
        <div className="flex items-center gap-3" aria-label="Session context">
          <span className="label !font-normal">Node</span>
          <NodeBadge display={session.node_display} large />
          <dl className="flex items-center gap-4 text-[12.5px]">
            <div className="flex gap-1.5">
              <dt className="text-muted">Series</dt>
              <dd className="font-mono font-semibold">{session.series.replace("rvu:", "")}-series</dd>
            </div>
            <div className="flex gap-1.5">
              <dt className="text-muted">User</dt>
              <dd className="font-mono font-semibold">{session.user}</dd>
            </div>
          </dl>
        </div>
      ) : sessionError ? (
        <div role="alert" className="flex items-center gap-2 text-[13px] text-crit">
          <ServerCrash size={16} aria-hidden="true" />
          Session unavailable: {sessionError}
          <button type="button" className="btn" onClick={retrySession}>
            <RefreshCw size={13} aria-hidden="true" /> Retry
          </button>
        </div>
      ) : (
        <span className="text-[13px] text-muted">Connecting to session…</span>
      )}
      <div className="ml-auto flex items-center gap-3">
        {CHAT_IS_MOCK && (
          <Badge
            tone="warn"
            title="Chat answers are scripted demo data, not the real backend. To connect: run the API (uvicorn) and copy frontend/.env.local.example to .env.local, then restart npm run dev."
          >
            DEMO DATA · not connected to backend
          </Badge>
        )}
        <AccuracyBadge />
        <NodeSwitcher />
        <DemoMenu />
        <ThemeToggle />
      </div>
    </header>
  );
}
