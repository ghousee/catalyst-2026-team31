"use client";

import { RefreshCw, ServerCrash } from "lucide-react";
import { useConsole } from "@/lib/store";
import { DemoMenu } from "./DemoMenu";
import { NodeBadge } from "./NodeBadge";
import { NodeSwitcher } from "./NodeSwitcher";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  const { session, sessionError, retrySession } = useConsole();
  const prod = session?.node_display.toUpperCase().includes("PROD");
  return (
    <header
      className={`flex h-14 shrink-0 items-center gap-4 border-b-[3px] bg-panel px-4 ${session ? (prod ? "border-prod" : "border-dr") : "border-line"}`}
    >
      <h1 className="text-[15px] font-bold tracking-tight">NonStop Copilot</h1>
      <div className="h-6 w-px bg-line" aria-hidden="true" />
      {session ? (
        <div className="flex items-center gap-3" aria-label="Session context">
          <span className="text-[11px] uppercase tracking-wide text-muted">Node</span>
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
        <NodeSwitcher />
        <DemoMenu />
        <ThemeToggle />
      </div>
    </header>
  );
}
