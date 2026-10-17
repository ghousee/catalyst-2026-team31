import { CircleCheck, OctagonX } from "lucide-react";

export function GuardList({ nodeOk, rvuOk, blockers }: { nodeOk: boolean; rvuOk: boolean; blockers: string[] }) {
  const items = [
    { label: "node_match", pass: nodeOk },
    { label: "rvu_ok", pass: rvuOk },
  ];
  return (
    <>
      <ul className="flex flex-wrap gap-2" aria-label="Guard results">
        {items.map((g) => (
          <li
            key={g.label}
            className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] ${
              g.pass ? "border-ok/40 text-ok" : "border-crit/70 bg-crit/15 font-bold text-crit"
            }`}
          >
            {g.pass ? <CircleCheck size={11} aria-hidden="true" /> : <OctagonX size={11} aria-hidden="true" />}
            {g.label}: {g.pass ? "pass" : "FAIL"}
          </li>
        ))}
      </ul>
      {blockers.length > 0 && (
        <div role="alert" className="mt-2 rounded-md border-2 border-crit bg-crit/15 p-3 text-crit">
          <p className="flex items-center gap-2 text-[14px] font-bold">
            <OctagonX size={18} aria-hidden="true" /> BLOCKED. This command cannot be run.
          </p>
          <ul className="mt-1 list-disc pl-6 text-[13px]">
            {blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
