"use client";

import { Crosshair } from "lucide-react";
import { useState } from "react";
import { useDismiss } from "@/lib/hooks";
import { SERIES_OPTIONS, SUBSYSTEM_OPTIONS } from "@/lib/format";
import { useConsole } from "@/lib/store";
import type { ContextOverride } from "@/lib/types";

export function ContextChip({ display, confidence }: { display: string; confidence?: number }) {
  const { session, override, setOverride } = useConsole();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<ContextOverride>({});
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));

  const toggle = () => {
    if (!open) setDraft({ ...override });
    setOpen(!open);
  };
  const set = (k: keyof ContextOverride) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setDraft((d) => ({ ...d, [k]: e.target.value || null }));

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="inline-flex items-center gap-1.5 rounded border border-line bg-panel px-2 py-0.5 text-[12px] text-fg hover:border-accent"
        title="Change the context used for your next question"
      >
        <Crosshair size={12} aria-hidden="true" />
        <span>Assuming {display}</span>
        {confidence !== undefined && <span className="text-muted">· {Math.round(confidence * 100)}%</span>}
        <span className="text-muted underline">change</span>
      </button>
      {open && (
        <div role="dialog" aria-label="Change context" className="card absolute left-0 top-full z-20 mt-1 w-[280px] space-y-2 p-3 shadow-xl">
          <p className="text-[12px] text-muted">Applies to your next question. A node different from the session is flagged.</p>
          <label className="block text-[12px]">
            Node
            <select className="field mt-1 w-full" value={draft.site ?? ""} onChange={set("site")}>
              <option value="">Session ({session?.node_display ?? "…"})</option>
              {session?.nodes_available.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.display}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-[12px]">
            Series
            <select className="field mt-1 w-full" value={draft.version ?? ""} onChange={set("version")}>
              <option value="">Session ({session?.series.replace("rvu:", "")}-series)</option>
              {SERIES_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-[12px]">
            Subsystem
            <select className="field mt-1 w-full" value={draft.system ?? ""} onChange={set("system")}>
              <option value="">Auto-detect</option>
              {SUBSYSTEM_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setOverride(draft);
                setOpen(false);
              }}
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
