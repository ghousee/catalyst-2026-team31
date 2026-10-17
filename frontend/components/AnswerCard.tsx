import { ShieldAlert } from "lucide-react";
import { humanizeEnvironmentText } from "@/lib/format";
import type { ChatMsg } from "@/lib/store";
import { AnswerChecks } from "./AnswerChecks";
import { ClaimList } from "./ClaimList";
import { ContextChip } from "./ContextChip";
import { ExpertList } from "./ExpertList";
import { ProposalCard } from "./ProposalCard";

type AnswerMsg = Extract<ChatMsg, { kind: "answer" }>;

export function AnswerCard({ msg }: { msg: AnswerMsg }) {
  const { data, proposals, noTemplate } = msg;
  const hasVeteran = data.claims.some((c) => c.lane === "veteran");
  const observedClaims = data.claims.filter((c) => c.lane !== "veteran");
  const veteranClaims = data.claims.filter((c) => c.lane === "veteran");
  return (
    <div className="space-y-2.5">
      <ContextChip display={data.context.display} confidence={data.context.confidence} />
      <section aria-label="Answer" className="card space-y-3 p-3">
        {observedClaims.length > 0 && (
          <div>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Confirmed and documented evidence</h4>
            <ClaimList claims={observedClaims} sources={data.sources} />
          </div>
        )}
        {veteranClaims.length > 0 && (
          <div className="border-t border-line pt-3">
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Expert guidance · context scoped</h4>
            <ClaimList claims={veteranClaims} sources={data.sources} />
          </div>
        )}
        <div className="rounded-lg border border-warn/30 bg-warn/8 px-3 py-2 text-[12.5px]">
          <span className="font-semibold text-warn">Still unknown: </span>
          <span className="text-muted">The root cause remains unconfirmed until the proposed live diagnostic is reviewed.</span>
        </div>
        {data.dropped_claims > 0 && (
          <p className="flex items-center gap-1.5 text-[12px] text-warn">
            <ShieldAlert size={13} aria-hidden="true" />
            {data.dropped_claims} {data.dropped_claims === 1 ? "claim" : "claims"} dropped (unverified)
          </p>
        )}
        {!hasVeteran && (
          <p className="rounded border border-line bg-panel2 px-2.5 py-1.5 text-[12.5px] text-muted">
            Documentation only. No captured veteran knowledge applies to {humanizeEnvironmentText(data.context.display)}.
          </p>
        )}
        {data.quality && <AnswerChecks q={data.quality} />}
      </section>
      {data.experts.length > 0 && (
        <section aria-label="Experts" className="space-y-1.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            {hasVeteran ? "Who knows this" : "Not covered by veterans here? Who knows this"}
          </h4>
          <ExpertList experts={data.experts} />
        </section>
      )}
      {proposals === null && (
        <p className="animate-pulse text-[12px] text-muted" role="status">
          Looking up a catalog command…
        </p>
      )}
      {proposals?.map((p) => <ProposalCard key={p.id} proposal={p} />)}
      {proposals && proposals.length === 0 && noTemplate && (
        <p className="text-[12px] text-muted">No catalog command matches this question, so none is proposed.</p>
      )}
    </div>
  );
}
