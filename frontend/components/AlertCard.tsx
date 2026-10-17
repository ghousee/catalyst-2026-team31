import { Clock, History, Network, TrendingUp, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import type { Alert, Expert } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Badge, type Tone } from "./Badge";
import { ClaimList } from "./ClaimList";
import { ExpertList } from "./ExpertList";
import { NodeBadge } from "./NodeBadge";
import { ProposalCard } from "./ProposalCard";

const SEV: Record<Alert["severity"], Tone> = { info: "info", warning: "warn", critical: "crit" };

/** Who raised it: a named veteran's pattern, the graph's "usually comes before" link, or a metric trend. */
function Origin({ a }: { a: Alert }) {
  if (a.owner_name) {
    return (
      <span className="inline-flex items-center gap-2 text-[12.5px]">
        <Avatar name={a.owner_name} size={24} />
        <span>
          <span className="font-semibold">{a.owner_name.split(" ")[0]}&rsquo;s pattern</span>{" "}
          <span className="font-mono text-[11px] text-muted">{a.pattern_id}</span>
        </span>
      </span>
    );
  }
  const Icon = a.kind === "trend" ? TrendingUp : Network;
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] font-medium">
      <Icon size={14} aria-hidden="true" className="text-muted" />
      {a.kind === "trend" ? "Metric trend" : "Knowledge graph: usually comes before"}
    </span>
  );
}

export function AlertCard({ alert: a }: { alert: Alert }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  const backup = a.backup_expert;
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
        <button type="button" className="btn h-7 px-2 text-[11.5px]"
          onClick={() => { setDismissed(true); void api.ackAlert(a.id).catch(() => setDismissed(false)); }}>
          Dismiss
        </button>
      </header>
      <p className="text-[14px] font-semibold leading-snug">{a.message}</p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <Origin a={a} />
        {a.lead_time_min != null && (
          <span className="inline-flex items-center gap-1 text-[12.5px] font-medium text-warn">
            <Clock size={13} aria-hidden="true" />~{a.lead_time_min} min before failure
          </span>
        )}
        {a.backtest && (
          <span className="inline-flex items-center gap-1 text-[12.5px] text-muted">
            <History size={13} aria-hidden="true" />
            Warned early in {a.backtest.hits}/{a.backtest.of} past incidents, avg {a.backtest.avg_lead_min} min
          </span>
        )}
      </div>

      <section aria-label="Evidence">
        <h4 className="label">Evidence</h4>
        <ul className="mt-1 flex flex-wrap gap-2">
          {a.evidence.map((e, i) => (
            <li key={i} className="rounded border border-line bg-panel2 px-2 py-1 font-mono text-[12px]">
              {e.event ? `${e.event} × ${e.count}` : `${e.metric} = ${e.value}${e.trend ? ` (${e.trend})` : ""}`}
            </li>
          ))}
        </ul>
      </section>

      {a.fix_claims.length > 0 && (
        <section aria-label="What to do">
          <h4 className="mb-1 label">What to do</h4>
          <ClaimList claims={a.fix_claims} />
        </section>
      )}

      {a.next_commands.length > 0 && (
        <section aria-label="Check first" className="space-y-2">
          <h4 className="label">Check first</h4>
          {a.next_commands.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </section>
      )}

      {backup && (
        <section aria-label="Who to call">
          <h4 className="mb-1 label">{a.owner_name ? `${a.owner_name.split(" ")[0]} unavailable? Call` : "Who to call"}</h4>
          <ExpertList experts={[{ reason: a.pattern_id ? `Backup for ${a.pattern_id}` : `Expert in ${a.subsystem}`, active: true, ...backup } as Expert]} />
        </section>
      )}
    </article>
  );
}
