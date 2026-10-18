"use client";

import { Activity, Inbox, Radio } from "lucide-react";
import { useState } from "react";
import { API_URL } from "@/lib/api";
import { usePolling } from "@/lib/hooks";

/** GET /integrations (backend/integrations): one row per monitoring-tool connector. */
interface Connector {
  tool: string;
  mode: string;
  target: string;
  every_s: number;
  last_poll: string | null;
  received: number;
  last_error: string | null;
  running: boolean;
}

// Demo stand-ins: these raise alarms *through* the real connectors (Prognosis REST poll, MOMI export folder).
const SAMPLES: Record<string, Array<{ id: string; label: string }>> = {
  "IR Prognosis": [
    { id: "audit", label: "TMF 185 on \\PROD" },
    { id: "cpu", label: "CPU 101 down" },
    { id: "pathway", label: "Pathway 1034" },
    { id: "dr_audit", label: "TMF 185 on \\DR" },
    { id: "any", label: "Any manual message" },
  ],
  "BlackWood MOMI": [
    { id: "disk", label: "DISK 5032 mirror down" },
    { id: "frozen", label: "Pathway 1061 frozen" },
    { id: "path", label: "DISK 5015 path error" },
  ],
};

async function getJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

const ago = (ts: string | null) => {
  if (!ts) return "not yet";
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)} min ago`;
};

export function IntegrationsPanel() {
  const { data, error } = usePolling(() => getJson<Connector[]>("/integrations"), 3000, "integrations");
  const [sent, setSent] = useState<string | null>(null);

  const raise = async (tool: string, sample: string, label: string) => {
    try {
      await getJson(tool === "IR Prognosis" ? "/demo/prognosis/problem" : "/demo/momi/alarm", { sample });
      setSent(`${label} sent to ${tool}. It arrives on the next ${tool === "IR Prognosis" ? "poll" : "folder read"}.`);
    } catch {
      setSent(`Could not reach the ${tool} stand-in.`);
    }
  };

  return (
    <div className="space-y-3">
      {error && <p role="alert" className="text-sm text-crit">Connectors unavailable: {error}</p>}
      {(data ?? []).map((c) => {
        const ok = c.running && !c.last_error;
        const Icon = c.tool === "IR Prognosis" ? Radio : Inbox;
        return (
          <section key={c.tool} aria-label={c.tool} className="rounded-xl border border-line bg-panel p-3">
            <div className="flex items-center gap-2">
              <Icon size={16} aria-hidden="true" className="text-accent" />
              <h4 className="text-[13.5px] font-semibold">{c.tool}</h4>
              <span className={`ml-auto inline-flex items-center gap-1.5 text-xs font-semibold ${ok ? "text-ok" : "text-crit"}`}>
                <span className={ok ? "live-dot" : "inline-block h-2 w-2 rounded-full bg-crit"} aria-hidden="true" />
                {ok ? "Connected" : c.running ? "Error" : "Off"}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted">
              {c.mode} every {c.every_s}s · last read {ago(c.last_poll)} · <span className="num">{c.received}</span> alarms received
            </p>
            <p className="mt-0.5 truncate font-mono text-[11px] text-muted" title={c.target}>{c.target}</p>
            {c.last_error && <p className="mt-1 text-xs text-crit">{c.last_error}</p>}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(SAMPLES[c.tool] ?? []).map((s) => (
                <button key={s.id} type="button" className="btn h-7 px-2 text-[11.5px]" onClick={() => void raise(c.tool, s.id, s.label)}>
                  <Activity size={12} aria-hidden="true" />
                  {s.label}
                </button>
              ))}
            </div>
          </section>
        );
      })}
      {sent && <p role="status" className="text-xs text-muted">{sent}</p>}
      <p className="text-[11.5px] leading-4 text-muted">
        Demo stand-ins send sample alarms through the real connectors. Pointing the Prognosis URL at a customer&rsquo;s
        Prognosis Web UI, or the MOMI folder at their export location, needs no code change.
      </p>
    </div>
  );
}
