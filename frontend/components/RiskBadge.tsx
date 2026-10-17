import { OctagonAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import type { Risk } from "@/lib/types";
import { Badge } from "./Badge";

export function RiskBadge({ risk }: { risk: Risk }) {
  if (risk === "read_only")
    return (
      <Badge tone="ok" title="Reads state only">
        <ShieldCheck size={12} aria-hidden="true" />
        READ ONLY
      </Badge>
    );
  if (risk === "state_changing")
    return (
      <Badge tone="warn" title="Changes system state">
        <TriangleAlert size={12} aria-hidden="true" />
        STATE CHANGING
      </Badge>
    );
  return (
    <Badge tone="crit" title="Critical: hard or impossible to undo">
      <OctagonAlert size={12} aria-hidden="true" />
      CRITICAL
    </Badge>
  );
}
