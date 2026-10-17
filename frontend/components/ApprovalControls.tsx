"use client";

import { CircleCheck, Hourglass, Play, ShieldCheck } from "lucide-react";
import { useId, useState } from "react";
import type { Proposal } from "@/lib/types";

export type Stage = "idle" | "approving" | "waiting" | "approved" | "executing" | "executed" | "rejected";

interface Props {
  proposal: Proposal;
  stage: Stage;
  disabled: boolean;
  reason: string;
  needsDry: boolean;
  approverName: string;
  onApprove: (typedNode: string | null, second: string | null) => void;
  onCancel: () => void;
  onExecute: () => void;
}

export function ApprovalControls({ proposal: p, stage, disabled, reason, needsDry, approverName, onApprove, onCancel, onExecute }: Props) {
  const [typed, setTyped] = useState("");
  const inputId = useId();
  const kind = p.approval.required;

  if (stage === "waiting")
    return (
      <div role="status" className="flex flex-1 flex-wrap items-center gap-2 rounded border border-warn/50 bg-warn/10 p-2 text-[12.5px] text-warn">
        <Hourglass size={14} className="animate-pulse" aria-hidden="true" />
        Waiting for second approver: {approverName} (on-call veteran, simulated)…
        <button type="button" className="btn ml-auto" onClick={onCancel}>
          Cancel
        </button>
      </div>
    );

  if (stage === "approved" || stage === "executing")
    return (
      <div className="flex flex-1 flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-[12.5px] font-medium text-ok" role="status">
          <CircleCheck size={14} aria-hidden="true" /> Approved
        </span>
        <button type="button" className="btn btn-primary" disabled={stage === "executing"} onClick={onExecute}>
          <Play size={13} aria-hidden="true" />
          {stage === "executing" ? "Running simulation…" : "Run simulated check"}
        </button>
      </div>
    );

  const busy = stage === "approving";
  const typedOk = typed === p.node;
  const blockedByDry = needsDry;

  return (
    <div className="flex flex-1 flex-wrap items-start gap-2">
      {kind === "type_node" && (
        <div className="flex flex-col">
          <label htmlFor={inputId} className="text-[11px] text-muted">
            Type <span className="font-mono font-bold text-fg">{p.node}</span> to enable approval
          </label>
          <input
            id={inputId}
            className="field w-40 font-mono"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            disabled={disabled}
            aria-invalid={typed.length > 0 && !typedOk}
          />
        </div>
      )}
      <button
        type="button"
        className={`btn ${p.risk === "critical" ? "btn-danger" : "btn-primary"} ${kind === "type_node" ? "mt-[18px]" : ""}`}
        disabled={disabled || busy || blockedByDry || (kind === "type_node" && !typedOk)}
        onClick={() => onApprove(kind === "type_node" ? typed : null, null)}
      >
        <ShieldCheck size={13} aria-hidden="true" />
        {busy ? "Checking…" : kind === "second_approver" ? "Request second approver" : "Approve for simulation"}
      </button>
      {blockedByDry && !disabled && <span className="self-center text-[12px] text-muted">Run a dry run before approving.</span>}
      {stage === "rejected" && (
        <p role="alert" className="basis-full text-[12.5px] font-medium text-crit">
          Rejected: {reason || "approval refused"}
        </p>
      )}
    </div>
  );
}
