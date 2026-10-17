import { TriangleAlert } from "lucide-react";
import type { DryRun } from "@/lib/types";

export function DryRunView({ dry }: { dry: DryRun }) {
  return (
    <section aria-label="Dry run result" className="space-y-2 rounded border border-line bg-panel2 p-3">
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">Dry run (simulator, nothing executed)</h4>
      <div>
        <p className="text-[11px] text-muted">Expected output</p>
        <pre className="mt-1 overflow-x-auto rounded bg-[#05080a] p-2 font-mono text-[12px] text-[#7ee2a1]">{dry.expected_output}</pre>
      </div>
      <div>
        <p className="text-[11px] text-muted">Blast radius</p>
        {dry.blast_radius.length === 0 ? (
          <p className="text-[12px]">None. Read-only.</p>
        ) : (
          <ul className="mt-1 space-y-1">
            {dry.blast_radius.map((b) => (
              <li key={b.entity} className="text-[12.5px]">
                <span className="font-semibold">{b.entity}</span> <span className="text-muted">→</span> {b.effect}
              </li>
            ))}
          </ul>
        )}
      </div>
      {dry.warnings.length > 0 && (
        <ul className="space-y-1">
          {dry.warnings.map((w) => (
            <li key={w} className="flex items-start gap-1.5 text-[12.5px] font-medium text-warn">
              <TriangleAlert size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              {w}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
