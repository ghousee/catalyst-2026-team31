import type { Lane } from "@/lib/types";
import { Badge, type Tone } from "./Badge";

const LANES: Record<Lane, { icon: string; label: string; tone: Tone; hint: string }> = {
  doc: { icon: "📘", label: "Doc", tone: "info", hint: "From documentation" },
  veteran: { icon: "👤", label: "Veteran", tone: "warn", hint: "From a veteran operator" },
  live: { icon: "🖥", label: "Live", tone: "ok", hint: "Observed from a command run" },
};

export function LaneBadge({ lane }: { lane: Lane }) {
  const l = LANES[lane];
  return (
    <Badge tone={l.tone} title={l.hint}>
      <span aria-hidden="true">{l.icon}</span>
      {l.label}
    </Badge>
  );
}
