"use client";

import { useState } from "react";
import { useConsole } from "@/lib/store";
import { ConfirmDialog } from "./ConfirmDialog";
import { NodeBadge } from "./NodeBadge";

export function NodeSwitcher() {
  const { session, switchNode } = useConsole();
  const [target, setTarget] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!session) return null;
  const targetDisplay = session.nodes_available.find((n) => n.id === target)?.display ?? "";

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
        Switch node
        <select
          className="field py-1"
          value={session.node}
          onChange={(e) => {
            setError(null);
            setTarget(e.target.value);
          }}
          aria-label="Switch node"
        >
          {session.nodes_available.map((n) => (
            <option key={n.id} value={n.id}>
              {n.display}
            </option>
          ))}
        </select>
      </label>
      <ConfirmDialog
        open={!!target && target !== session.node}
        title={`Switch session to ${targetDisplay}?`}
        confirmLabel={`Switch to ${targetDisplay}`}
        busy={busy}
        error={error}
        onConfirm={confirm}
        onCancel={() => setTarget(null)}
      >
        <p>
          You are on <NodeBadge display={session.node_display} />. Switching to <NodeBadge display={targetDisplay} /> changes{" "}
          <strong className="text-fg">every answer, command target and alert</strong>. Knowledge scoped to {session.node_display} will no longer
          apply, and open command proposals will be blocked.
        </p>
      </ConfirmDialog>
    </>
  );
}
