"use client";

import { Bell, ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { useConsole } from "@/lib/store";
import { AlertCard } from "./AlertCard";
import { Badge } from "./Badge";

export function AlertsPanel() {
  const { session } = useConsole();
  const node = session?.node ?? "";
  const { data, error, loading } = usePolling(() => api.getAlerts(), 2000, node);
  const [open, setOpen] = useState(false);
  const seen = useRef(new Set<string>());

  const alerts = useMemo(() => data ?? [], [data]);
  const latest = alerts[0];

  // Expand once when a new alert arrives; the operator can collapse it afterwards.
  useEffect(() => {
    const fresh = alerts.filter((a) => !seen.current.has(a.id));
    if (fresh.length) {
      fresh.forEach((a) => seen.current.add(a.id));
      setOpen(true);
    }
  }, [alerts]);

  return (
    <section aria-label="Watcher alerts" className="border-b border-line">
      <button
        type="button"
        className="flex h-10 w-full items-center gap-2 px-4 text-left hover:bg-panel2"
        aria-expanded={open}
        aria-controls="alerts-body"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
        <Bell size={14} className={latest ? "text-warn" : "text-muted"} aria-hidden="true" />
        <span className="label !text-fg">Alerts</span>
        <Badge tone={alerts.length ? "warn" : "muted"}>{alerts.length}</Badge>
        <span className="min-w-0 flex-1 truncate text-[12.5px] text-muted">
          {error
            ? `Watcher unreachable (${error}), retrying…`
            : loading && !data
              ? "Connecting to watcher…"
              : latest
                ? latest.message
                : `No active alerts for ${session?.node_display ?? "this node"}. Watcher is running.`}
        </span>
        {latest?.lead_time_min != null && <Badge tone="warn">~{latest.lead_time_min} min</Badge>}
      </button>
      {open && (
        <div id="alerts-body" className="scroll max-h-[32vh] space-y-3 overflow-y-auto px-4 pb-3">
          {alerts.length === 0 && <p className="text-[12.5px] text-muted">Nothing to show.</p>}
          {alerts.map((a) => (
            <AlertCard key={a.id} alert={a} />
          ))}
        </div>
      )}
    </section>
  );
}
