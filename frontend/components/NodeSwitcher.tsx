"use client";

import { ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { environmentName } from "@/lib/format";
import { useConsole } from "@/lib/store";
import { ConfirmDialog } from "./ConfirmDialog";

export function NodeSwitcher() {
  const { session, switchNode } = useConsole();
  const [target, setTarget] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!session) return null;
  const targetDisplay = session.nodes_available.find((n) => n.id === target)?.display ?? "";
  const targetName = environmentName(targetDisplay);

  const confirm = async () => {
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      await switchNode(target);
      setTarget(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not switch node");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <label className="flex items-center gap-2 text-[12px] text-muted">
        Environment
        <select
          className="field py-1"
          value={session.node}
          onChange={(e) => {
            setError(null);
            setTarget(e.target.value);
          }}
          aria-label="Switch environment"
        >
          {session.nodes_available.map((n) => (
            <option key={n.id} value={n.id}>
              {environmentName(n.display)}
            </option>
          ))}
        </select>
      </label>
      <ConfirmDialog
        open={!!target && target !== session.node}
        title="Switch environment?"
        description="This changes the operational context across the workspace."
        confirmLabel={`Switch to ${targetName}`}
        busy={busy}
        error={error}
        onConfirm={confirm}
        onCancel={() => setTarget(null)}
      >
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
          <div className="rounded-lg border border-line bg-panel2/60 p-3">
            <span className="block text-xs text-muted">Current</span>
            <strong className="mt-1 block text-fg">{environmentName(session.node_display)}</strong>
          </div>
          <ArrowRight size={17} className="text-muted" aria-hidden="true" />
          <div className="rounded-lg border border-accent/30 bg-accent/8 p-3">
            <span className="block text-xs text-muted">New environment</span>
            <strong className="mt-1 block text-accent">{targetName}</strong>
          </div>
        </div>

        <div className="mt-4">
          <h3 className="font-semibold text-fg">What changes</h3>
          <ul className="mt-2 space-y-2 text-sm leading-5">
            <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" /><span>Answers, alerts, and diagnostic targets use <strong className="font-semibold text-fg">{targetName}</strong>.</span></li>
            <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" /><span>Knowledge scoped only to {environmentName(session.node_display)} will no longer be applied.</span></li>
            <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" /><span>Open command proposals from the current environment will be blocked.</span></li>
          </ul>
        </div>

        <div className="mt-4 flex gap-2 rounded-lg border border-ok/25 bg-ok/8 p-3 text-sm text-fg">
          <ShieldCheck size={17} className="mt-0.5 shrink-0 text-ok" aria-hidden="true" />
          <p><strong className="font-semibold">No command will run.</strong> The switch only changes investigation context.</p>
        </div>
      </ConfirmDialog>
    </>
  );
}
