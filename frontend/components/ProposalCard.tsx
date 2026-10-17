"use client";

import { FlaskConical, Play, TerminalSquare } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { USER_ID, useConsole } from "@/lib/store";
import type { DryRun, ExecuteResponse, Proposal } from "@/lib/types";
import { ApprovalControls, type Stage } from "./ApprovalControls";
import { Badge } from "./Badge";
import { CitationChip } from "./CitationChip";
import { DryRunView } from "./DryRunView";
import { GuardList } from "./GuardList";
import { NodeBadge } from "./NodeBadge";
import { RiskBadge } from "./RiskBadge";

const SECOND_APPROVER = { id: "raj", name: "Raj Patel" };

export function ProposalCard({ proposal: p }: { proposal: Proposal }) {
  const { session, onExecuted } = useConsole();
  const [dry, setDry] = useState<DryRun | null>(null);
  const [dryBusy, setDryBusy] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<ExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Node/RVU guards: server result plus a live check against the current session.
  const sessionMismatch = !!session && session.node_display !== p.node;
  const blockers: string[] = [];
  if (!p.guards.node_match || sessionMismatch)
    blockers.push(
      `Node guard: command targets ${p.node}${session ? ` but the session is on ${session.node_display}` : ""}. Re-ask on the current node.`,
    );
  if (!p.guards.rvu_ok) blockers.push("RVU guard: this command template does not apply to the node's series/RVU.");
  const blocked = blockers.length > 0;
  const done = stage === "executed";
  const needsDry = p.risk !== "read_only";

  const dryRun = async () => {
    setDryBusy(true);
    setError(null);
    try {
      setDry(await api.dryrun(p.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry run failed");
    } finally {
      setDryBusy(false);
    }
  };

  const approve = useCallback(
    async (typedNode: string | null, second: string | null) => {
      setError(null);
      setStage("approving");
      try {
        const r = await api.approve(p.id, { user_id: USER_ID, typed_node: typedNode, second_approver: second });
        setReason(r.reason);
        setStage(r.status === "approved" ? "approved" : r.status === "needs_second_approver" ? "waiting" : "rejected");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Approval failed");
        setStage("idle");
      }
    },
    [p.id],
  );

  // Simulated second approver answers after a short delay.
  useEffect(() => {
    if (stage !== "waiting") return;
    const t = setTimeout(() => void approve(null, SECOND_APPROVER.id), 3000);
    return () => clearTimeout(t);
  }, [stage, approve]);

  const execute = async () => {
    setStage("executing");
    setError(null);
    try {
      const r = await api.execute(p.id);
      setResult(r);
      setStage("executed");
      onExecuted(p, r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Execution failed");
      setStage("approved");
    }
  };

  const border = blocked ? "border-crit" : p.risk === "critical" ? "border-crit/60" : p.risk === "state_changing" ? "border-warn/60" : "border-line";

  return (
    <article aria-label={`Command proposal: ${p.command}`} className={`card space-y-2.5 border-2 p-3 ${border}`}>
      <header className="flex flex-wrap items-center gap-2">
        <TerminalSquare size={14} className="text-muted" aria-hidden="true" />
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">Proposed command</span>
        <span className="ml-auto flex items-center gap-2">
          <RiskBadge risk={p.risk} />
          <span className="text-[11px] text-muted">target</span>
          <NodeBadge display={p.node} />
        </span>
      </header>

      <pre className="overflow-x-auto rounded bg-[#05080a] px-3 py-2 font-mono text-[13.5px] text-[#7ee2a1]">{p.command}</pre>
      <p className="text-[13px]">{p.explanation}</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-muted">Source</span>
        <CitationChip sourceId={p.source_id} lane="doc" />
        <Badge tone="muted" title="Approval required for this command">
          approval: {p.approval.required.replace("_", " ")}
        </Badge>
      </div>

      <GuardList nodeOk={p.guards.node_match && !sessionMismatch} rvuOk={p.guards.rvu_ok} blockers={blockers} />

      {dry && <DryRunView dry={dry} />}

      {done && result ? (
        <div role="status" className="flex flex-wrap items-center gap-2 rounded border border-ok/40 bg-ok/10 p-2 text-[12.5px] text-ok">
          <Play size={13} aria-hidden="true" />
          Executed (simulated) at {fmtTime(result.ts)}. Output is in the terminal pane.
          <CitationChip sourceId={result.source_id} lane="live" />
        </div>
      ) : (
        <div className="flex flex-wrap items-start gap-2 border-t border-line pt-2.5">
          <button type="button" className="btn" disabled={blocked || dryBusy} onClick={dryRun}>
            <FlaskConical size={13} aria-hidden="true" />
            {dryBusy ? "Running…" : dry ? "Re-run dry run" : "Dry run"}
          </button>
          <ApprovalControls
            proposal={p}
            stage={stage}
            disabled={blocked}
            reason={reason}
            needsDry={needsDry && !dry}
            approverName={SECOND_APPROVER.name}
            onApprove={approve}
            onCancel={() => setStage("idle")}
            onExecute={execute}
          />
        </div>
      )}
      {error && (
        <p role="alert" className="text-[12.5px] text-crit">
          {error}
        </p>
      )}
    </article>
  );
}
