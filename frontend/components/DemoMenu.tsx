"use client";

import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { api, USE_MOCKS } from "@/lib/api";
import { useDismiss } from "@/lib/hooks";
import type { ScenarioName } from "@/lib/types";

const SCENARIOS: Array<{ id: ScenarioName; label: string }> = [
  { id: "audit_trail_fill", label: "Audit trail filling (hero)" },
  { id: "disk_revive_stall", label: "Disk mirror revive stalled" },
  { id: "pathway_no_server", label: "Pathway: NO SERVER AVAILABLE" },
  { id: "cpu_down", label: "CPU down + takeover" },
];

export function DemoMenu() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));

  const run = async (s: ScenarioName) => {
    setStatus("Starting…");
    try {
      const r = await api.runScenario({ scenario: s, speed: 10 });
      setStatus(`${s}: ${r.status}`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed to start scenario");
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button type="button" className="btn" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(!open)}>
        <FlaskConical size={14} aria-hidden="true" />
        Demo
      </button>
      {open && (
        <div role="menu" aria-label="Demo controls" className="card absolute right-0 top-full z-30 mt-1 w-72 space-y-1 p-2 shadow-xl">
          <p className="px-2 py-1 label">
            Run scenario · {USE_MOCKS ? "mock" : "live API"}
          </p>
          {SCENARIOS.map((s) => (
            <button key={s.id} type="button" role="menuitem" className="btn w-full justify-start" onClick={() => void run(s.id)}>
              {s.label}
            </button>
          ))}
          <p className="px-2 pt-1 text-[11.5px] text-muted" role="status">
            {status ?? "Speed x10. In mock mode only the hero scenario changes the alert and metrics."}
          </p>
        </div>
      )}
    </div>
  );
}
