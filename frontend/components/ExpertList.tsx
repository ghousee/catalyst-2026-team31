import { Phone } from "lucide-react";
import type { Expert } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Badge, type Tone } from "./Badge";

// Reference card only: who to talk to and why. No in-app messaging for now.
const AVAILABILITY: Record<NonNullable<Expert["availability"]>, { label: string; tone: Tone }> = {
  on_shift: { label: "ON SHIFT", tone: "ok" },
  on_call: { label: "ON CALL", tone: "info" },
  off_shift: { label: "OFF SHIFT", tone: "muted" },
  retired: { label: "RETIRED", tone: "muted" },
};

function ExpertRow({ expert }: { expert: Expert }) {
  const avail = expert.availability
    ? AVAILABILITY[expert.availability]
    : { label: expert.active ? "AVAILABLE" : "UNAVAILABLE", tone: (expert.active ? "ok" : "muted") as Tone };
  const designation = [expert.role, expert.team, expert.years != null ? `${expert.years} yrs` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="flex gap-2.5 rounded border border-line bg-panel2 px-2.5 py-2">
      <Avatar name={expert.name} muted={!expert.active} />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium">{expert.name}</span>
          <Badge tone={avail.tone}>{avail.label}</Badge>
        </div>
        {designation && <p className="text-[12px] text-fg/85">{designation}</p>}
        {expert.expertise && expert.expertise.length > 0 && (
          <ul className="flex flex-wrap gap-1" aria-label={`${expert.name} expertise`}>
            {expert.expertise.map((x) => (
              <li key={x}>
                <Badge tone="muted">{x}</Badge>
              </li>
            ))}
          </ul>
        )}
        <p className="text-[12px] text-muted">{expert.reason}</p>
        {expert.contact && (
          <p className="flex items-center gap-1.5 font-mono text-[11.5px] text-muted">
            <Phone size={11} aria-hidden="true" />
            {expert.contact}
          </p>
        )}
      </div>
    </li>
  );
}

export function ExpertList({ experts }: { experts: Expert[] }) {
  return (
    <ul className="space-y-1.5">
      {experts.map((e) => (
        <ExpertRow key={e.id} expert={e} />
      ))}
    </ul>
  );
}
