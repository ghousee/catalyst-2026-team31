"use client";

import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { useConsole } from "@/lib/store";
import { Sparkline } from "./Sparkline";

// The contract does not return thresholds, so the UI carries its own (see vault/code/frontend.md).
const METRICS = [
  { metric: "audit-capacity-pct", label: "Audit trail capacity", unit: "%", threshold: 80 },
  { metric: "cpu-busy-time", label: "CPU busy", unit: "%", threshold: 85 },
  { metric: "request-qtime", label: "Request queue time", unit: " ms", threshold: 40 },
];

export function HealthPanel() {
  const { session } = useConsole();
  const node = session?.node ?? "";
  const { data, error, loading } = usePolling(() => (node ? api.getMetrics(node, "60m") : Promise.resolve(null)), 4000, node);

  return (
    <section aria-label="System health" className="border-b border-line px-4 py-2.5">
      <div className="mb-1.5 flex items-center justify-between">
        <h2 className="label !text-fg">Health · last 60 min</h2>
        {error && <span className="text-[11px] text-crit">Metrics unavailable, retrying…</span>}
      </div>
      <ul className="grid grid-cols-3 gap-3">
        {METRICS.map((m) => {
          const pts = data?.series.find((s) => s.metric === m.metric)?.points.map((p) => p[1]) ?? [];
          const cur = pts.length ? pts[pts.length - 1] : null;
          const over = cur !== null && cur >= m.threshold;
          const near = cur !== null && cur >= m.threshold * 0.85;
          const color = over ? "rgb(var(--crit))" : near ? "rgb(var(--warn))" : "rgb(var(--ok))";
          return (
            <li key={m.metric} className="min-w-0 rounded border border-line bg-panel px-2.5 py-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-[11.5px] text-muted" title={m.metric}>
                  {m.label}
                </span>
                <span className="whitespace-nowrap font-mono text-[13px] font-semibold" style={{ color }}>
                  {cur === null ? (loading ? "…" : "n/a") : `${Math.round(cur)}${m.unit}`}
                </span>
              </div>
              <div className="h-10">{pts.length > 1 && <Sparkline values={pts} threshold={m.threshold} color={color} />}</div>
              <p className="text-[10.5px] text-muted">
                limit {m.threshold}
                {m.unit.trim()} · {over ? "OVER LIMIT" : near ? "approaching" : "normal"}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
