import { Clock, History, TriangleAlert } from "lucide-react";
import { fmtTime } from "@/lib/format";
import type { Alert } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Badge, type Tone } from "./Badge";
import { ClaimList } from "./ClaimList";
import { ExpertList } from "./ExpertList";
import { NodeBadge } from "./NodeBadge";
import { ProposalCard } from "./ProposalCard";

const SEV: Record<Alert["severity"], Tone> = { info: "info", warning: "warn", critical: "crit" };

export function AlertCard({ alert: a }: { alert: Alert }) {
  const firstName = a.owner_name.split(" ")[0];
  return (
    <article aria-label={`Alert: ${a.message}`} className="card space-y-3 border-warn/50 p-3">
      <header className="flex flex-wrap items-center gap-2">
        <Badge tone={SEV[a.severity]}>
          <TriangleAlert size={12} aria-hidden="true" />
          {a.severity.toUpperCase()}
        </Badge>
        <NodeBadge display={a.node} />
        <Badge>{a.subsystem}</Badge>
        <span className="ml-auto text-[11px] text-muted">{fmtTime(a.ts)}</span>
      </header>
      <p className="text-[14px] font-semibold leading-snug">{a.message}</p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <span className="inline-flex items-center gap-2 text-[12.5px]">
          <Avatar name={a.owner_name} size={24} />
          <span>
            <span className="font-semibold">{firstName}&rsquo;s pattern</span>{" "}
            <span className="font-mono text-[11px] text-muted">{a.pattern_id}</span>
          </span>
        </span>
        <span className="inline-flex items-center gap-1 text-[12.5px] font-medium text-warn">
          <Clock size={13} aria-hidden="true" />~{a.lead_time_min} min before failure
        </span>
        <span className="inline-flex items-center gap-1 text-[12.5px] text-muted">
          <History size={13} aria-hidden="true" />
          Warned early in {a.backtest.hits}/{a.backtest.of} past incidents, avg {a.backtest.avg_lead_min} min
        </span>
      </div>

      <section aria-label="Evidence">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">Evidence</h4>
        <ul className="mt-1 flex flex-wrap gap-2">
          {a.evidence.map((e, i) => (
            <li key={i} className="rounded border border-line bg-panel2 px-2 py-1 font-mono text-[12px]">
              {e.event ? `${e.event} × ${e.count}` : `${e.metric} = ${e.value}${e.trend ? ` (${e.trend})` : ""}`}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Suggested fix">
        <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Suggested fix</h4>
        <ClaimList claims={a.fix_claims} />
      </section>

      {a.next_commands.length > 0 && (
        <section aria-label="Next commands" className="space-y-2">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">Next commands</h4>
          {a.next_commands.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </section>
      )}

      <section aria-label="Backup expert">
        <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
          {firstName} is unavailable? Backup expert
        </h4>
        <ExpertList
          experts={[{ reason: `Backup for ${a.pattern_id}`, active: true, ...a.backup_expert }]}
        />
      </section>
    </article>
  );
}
