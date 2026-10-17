"use client";

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
  const currentName = environmentName(session.node_display);
  const currentIsProduction = session.node_display.toUpperCase().includes("PROD");
  const targetIsProduction = targetDisplay.toUpperCase().includes("PROD");

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
        title={`Switch to ${targetName}?`}
        confirmLabel={`Switch to ${targetName}`}
        busy={busy}
        error={error}
        onConfirm={confirm}
        onCancel={() => setTarget(null)}
      >
        <p className="leading-6">
          You are viewing{" "}
          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${currentIsProduction ? "border-warn/25 bg-warn/10 text-warn" : "border-accent/25 bg-accent/10 text-accent"}`}>{currentName}</span>.
          {" "}Switching to{" "}
          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${targetIsProduction ? "border-warn/25 bg-warn/10 text-warn" : "border-accent/25 bg-accent/10 text-accent"}`}>{targetName}</span>
          {" "}changes <strong className="font-semibold text-fg">every answer, command target, and alert</strong>. Knowledge scoped to {currentName} will no longer apply, and open command proposals will be blocked.
        </p>
      </ConfirmDialog>
    </>
  );
}
