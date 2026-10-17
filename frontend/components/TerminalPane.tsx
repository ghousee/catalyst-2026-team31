"use client";

import { useEffect, useRef } from "react";
import { useConsole, type TermLine } from "@/lib/store";

const KIND: Record<TermLine["kind"], string> = {
  banner: "text-[#fbbf24] font-bold",
  sys: "text-[#d6a13a]",
  prompt: "text-[#4ade80]",
  cmd: "text-[#86efac] font-bold",
  out: "text-[#4ade80]/85",
};

export function TerminalPane() {
  const { terminal, session } = useConsole();
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [terminal.length]);

  const prompt = session ? `${session.node_display}.${session.user} ${terminal.filter((t) => t.kind === "cmd").length + 1}>` : "…>";

  return (
    <section aria-label="Terminal (read-only)" className="flex min-h-0 flex-col bg-[#05080a]">
      <header className="flex items-center justify-between border-b border-[#1c2a22] px-3 py-1.5 font-mono text-[11px] text-[#7a8f82]">
        <span>CAIL 6530 · {session?.node_display ?? "disconnected"}</span>
        <span className="rounded border border-[#2a3a30] px-1.5 py-0.5">READ-ONLY</span>
      </header>
      <div className="scroll min-h-0 flex-1 overflow-y-auto p-3 font-mono text-[12.5px] leading-[1.4]" role="log" aria-live="polite" aria-label="Terminal output" tabIndex={0}>
        {terminal.length === 0 && <p className="text-[#7a8f82]">Connecting to session…</p>}
        {terminal.map((l) => (
          <pre key={l.id} className={`whitespace-pre-wrap break-words ${KIND[l.kind]}`}>
            {l.text || " "}
          </pre>
        ))}
        {session && (
          <pre className="mt-1 text-[#4ade80]">
            {prompt} <span className="cursor inline-block h-[1em] w-[0.6em] translate-y-[2px] bg-[#4ade80]" aria-hidden="true" />
          </pre>
        )}
        <div ref={endRef} />
      </div>
      <footer className="border-t border-[#1c2a22] px-3 py-1.5 font-mono text-[11px] text-[#7a8f82]">
        Input disabled. Commands appear here only after you approve them in the copilot.
      </footer>
    </section>
  );
}
