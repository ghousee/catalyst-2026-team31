import type { Lane } from "@/lib/types";
import { Badge, type Tone } from "./Badge";

const LANES: Record<Lane, { label: string; tone: Tone; hint: string }> = {
  doc: { label: "Doc", tone: "info", hint: "From documentation" },
  veteran: { label: "Veteran", tone: "warn", hint: "From a veteran operator" },
  live: { label: "Live", tone: "ok", hint: "Observed from a command run" },
};

export function LaneBadge({ lane }: { lane: Lane }) {
  const l = LANES[lane];
  return (
    <Badge tone={l.tone} title={l.hint}>
      {l.label}
    </Badge>
  );
}
