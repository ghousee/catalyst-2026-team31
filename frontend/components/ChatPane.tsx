"use client";

import { ArrowUp, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { environmentName, SERIES_OPTIONS, SUBSYSTEM_OPTIONS } from "@/lib/format";
import { useConsole, type ChatMsg } from "@/lib/store";
import { AnswerCard } from "./AnswerCard";
import { ClarifyCard } from "./ClarifyCard";
import { ObservationCard } from "./ObservationCard";
import { ProposalCard } from "./ProposalCard";
import { ReferCard } from "./ReferCard";

export const SAMPLE_QUESTIONS = [
  "why is the audit trail filling?",
  "the disk is acting up",
  "is Pathway healthy?",
  "why did the nightly reconciliation hang?",
];

function Message({ m }: { m: ChatMsg }) {
  switch (m.kind) {
    case "user":
      return (
        <div className="flex justify-end">
          <p className="max-w-[85%] rounded-lg bg-accent/15 px-3 py-2 text-[13.5px]">{m.text}</p>
        </div>
      );
    case "answer":
      return <AnswerCard msg={m} />;
    case "clarify":
      return <ClarifyCard msg={m} />;
    case "refer":
      return <ReferCard data={m.data} />;
    case "observation":
      return <ObservationCard msg={m} />;
    case "proposals":
      return (
        <div className="space-y-2">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">{m.title}</h4>
          {m.proposals.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </div>
      );
    case "system":
      return <p className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[12.5px] text-warn">{m.text}</p>;
    case "error":
      return (
        <p role="alert" className="rounded border border-crit/50 bg-crit/10 px-3 py-2 text-[12.5px] text-crit">
          {m.text}
        </p>
      );
  }
}

function OverrideLine() {
  const { override, setOverride, session } = useConsole();
  const parts: string[] = [];
  if (override.site) parts.push(environmentName(session?.nodes_available.find((n) => n.id === override.site)?.display ?? override.site));
  if (override.version) parts.push(SERIES_OPTIONS.find((o) => o.id === override.version)?.label ?? override.version);
  if (override.system) parts.push(SUBSYSTEM_OPTIONS.find((o) => o.id === override.system)?.label ?? override.system);
  const active = parts.length > 0;
  return (
    <p className="flex h-5 items-center gap-2 text-[11.5px] text-muted">
      {active ? (
        <>
          <span className="font-semibold text-warn">Context override: {parts.join(" · ")}</span>
          <button type="button" className="inline-flex items-center gap-0.5 underline" onClick={() => setOverride({})} aria-label="Clear context override">
            <X size={11} aria-hidden="true" /> clear
          </button>
        </>
      ) : (
        <span>Context: {environmentName(session?.node_display)}</span>
      )}
    </p>
  );
}

export function ChatPane() {
  const { messages, busy, ask, session } = useConsole();
  const [text, setText] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages.length, busy]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    setText("");
    void ask(q);
  };

  return (
    <section aria-label="Copilot chat" className="flex min-h-0 flex-1 flex-col">
      <div ref={logRef} className="scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3" role="log" aria-live="polite" tabIndex={0}>
        {messages.length === 0 && (
          <div className="py-6 text-center">
            <p className="text-[13.5px] font-medium">Ask about {environmentName(session?.node_display)}</p>
            <p className="mt-1 text-[12.5px] text-muted">
              Answers are scoped to your session and cite a manual, a veteran or live output. Commands only run after you approve them.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {SAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" className="btn" disabled={busy || !session} onClick={() => void ask(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <Message key={m.id} m={m} />
        ))}
        {busy && (
          <p className="animate-pulse text-[12.5px] text-muted" role="status">
            Resolving context and checking sources…
          </p>
        )}
      </div>
      <form onSubmit={submit} className="border-t border-line bg-panel px-4 pb-3 pt-2">
        <OverrideLine />
        <div className="mt-1 flex gap-2">
          <input
            className="field flex-1"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask a question, e.g. why is the audit trail filling?"
            aria-label="Question for the copilot"
            autoComplete="off"
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !text.trim() || !session} aria-label="Send question">
            <ArrowUp size={15} aria-hidden="true" />
            Ask
          </button>
        </div>
      </form>
    </section>
  );
}
