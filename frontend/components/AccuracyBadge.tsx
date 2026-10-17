import { PILOT_STATS } from "@/lib/pilotStats";

export function AccuracyBadge() {
  return (
    <div className="group relative">
      <button
        type="button"
        className="rounded border border-line px-2 py-1 text-[11.5px] text-muted hover:text-fg"
        aria-describedby="pilot-stats"
      >
        Test-set accuracy
      </button>
      <div
        id="pilot-stats"
        role="tooltip"
        className="card invisible absolute left-0 top-full z-30 mt-1 w-[300px] space-y-1.5 p-3 text-[12px] shadow-xl group-hover:visible group-focus-within:visible"
      >
        <ul className="space-y-1">
          {PILOT_STATS.rows.map((r) => (
            <li key={r.name} className="flex justify-between gap-3">
              <span className="text-muted">{r.name}</span>
              <span className="font-mono font-semibold">{r.value}</span>
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-muted">{PILOT_STATS.label}</p>
      </div>
    </div>
  );
}
