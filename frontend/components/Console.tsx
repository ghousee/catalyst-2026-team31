"use client";

import { ConsoleProvider } from "@/lib/store";
import { AlertsPanel } from "./AlertsPanel";
import { ChatPane } from "./ChatPane";
import { HealthPanel } from "./HealthPanel";
import { SourceDialog } from "./SourceDialog";
import { TerminalPane } from "./TerminalPane";
import { TopBar } from "./TopBar";

export function Console() {
  return (
    <ConsoleProvider>
      <div className="flex h-screen min-w-[1200px] flex-col">
        <TopBar />
        <main className="grid min-h-0 flex-1 grid-cols-[2fr_3fr]">
          <TerminalPane />
          <div className="flex min-h-0 min-w-0 flex-col border-l border-line bg-bg">
            <HealthPanel />
            <AlertsPanel />
            <ChatPane />
          </div>
        </main>
      </div>
      <SourceDialog />
    </ConsoleProvider>
  );
}
