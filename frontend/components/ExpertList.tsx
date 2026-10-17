"use client";

import { Check, Send } from "lucide-react";
import { useState } from "react";
import { useConsole } from "@/lib/store";
import type { Expert } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";

function ExpertRow({ expert, question }: { expert: Expert; question: string }) {
  const { referExpert } = useConsole();
  const [state, setState] = useState<{ status: "idle" | "sending" | "sent" | "error"; id?: string }>({ status: "idle" });

  const ask = async () => {
    setState({ status: "sending" });
    try {
      const id = await referExpert(expert, question);
      setState({ status: "sent", id });
    } catch {
      setState({ status: "error" });
    }
  };

  return (
    <li className="flex items-center gap-2.5 rounded border border-line bg-panel2 px-2.5 py-2">
      <Avatar name={expert.name} muted={!expert.active} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium">{expert.name}</span>
          <Badge tone={expert.active ? "ok" : "muted"}>{expert.active ? "ACTIVE" : "INACTIVE"}</Badge>
        </div>
        <p className="truncate text-[12px] text-muted" title={expert.reason}>
          {expert.reason}
        </p>
      </div>
      {state.status === "sent" ? (
        <span className="inline-flex items-center gap-1 text-[12px] text-ok" role="status">
          <Check size={13} aria-hidden="true" /> Sent · {state.id}
        </span>
      ) : (
        <button
          type="button"
          className="btn btn-primary shrink-0"
          disabled={!expert.active || state.status === "sending"}
          onClick={ask}
          title={expert.active ? undefined : `${expert.name} is not currently available`}
        >
          <Send size={12} aria-hidden="true" />
          {state.status === "sending" ? "Sending…" : state.status === "error" ? "Retry" : `Ask ${expert.name.split(" ")[0]}`}
        </button>
      )}
    </li>
  );
}

export function ExpertList({ experts, question }: { experts: Expert[]; question: string }) {
  return (
    <ul className="space-y-1.5">
      {experts.map((e) => (
        <ExpertRow key={e.id} expert={e} question={question} />
      ))}
    </ul>
  );
}
