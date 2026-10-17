"use client";

import { CircleHelp } from "lucide-react";
import { useConsole, type ChatMsg } from "@/lib/store";

type ClarifyMsg = Extract<ChatMsg, { kind: "clarify" }>;

export function ClarifyCard({ msg }: { msg: ClarifyMsg }) {
  const { pickClarify, busy } = useConsole();
  return (
    <section aria-label="Clarifying question" className="card space-y-2.5 border-info/50 p-3">
      <p className="flex items-start gap-2 text-[13.5px] font-medium">
        <CircleHelp size={16} className="mt-0.5 shrink-0 text-info" aria-hidden="true" />
        {msg.data.question}
      </p>
      <div className="flex flex-wrap gap-2">
        {msg.data.options.map((o) => (
          <button
            key={o.label}
            type="button"
            className={`btn ${msg.resolved === o.label ? "btn-primary" : ""}`}
            disabled={msg.resolved !== null || busy}
            aria-pressed={msg.resolved === o.label}
            onClick={() => pickClarify(msg.id, msg.question, o)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {msg.resolved && <p className="text-[12px] text-muted">Context set to “{msg.resolved}”. Asking again.</p>}
    </section>
  );
}
