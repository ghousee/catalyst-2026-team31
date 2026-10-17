import { ShieldAlert } from "lucide-react";
import type { ChatMsg } from "@/lib/store";
import { ClaimList } from "./ClaimList";
import { ContextChip } from "./ContextChip";
import { ExpertList } from "./ExpertList";
import { ProposalCard } from "./ProposalCard";

type AnswerMsg = Extract<ChatMsg, { kind: "answer" }>;

export function AnswerCard({ msg }: { msg: AnswerMsg }) {
  const { data, proposals, noTemplate } = msg;
  const hasVeteran = data.claims.some((c) => c.lane === "veteran");
  return (
    <div className="space-y-2.5">
      <ContextChip display={data.context.display} confidence={data.context.confidence} />
      <section aria-label="Answer" className="card space-y-3 p-3">
        <ClaimList claims={data.claims} sources={data.sources} />
        {data.dropped_claims > 0 && (
          <p className="flex items-center gap-1.5 text-[12px] text-warn">
            <ShieldAlert size={13} aria-hidden="true" />
            {data.dropped_claims} {data.dropped_claims === 1 ? "claim" : "claims"} dropped (unverified)
          </p>
        )}
        {!hasVeteran && (
          <p className="rounded border border-line bg-panel2 px-2.5 py-1.5 text-[12.5px] text-muted">
            Documentation only. No captured veteran knowledge applies to {data.context.display}.
          </p>
        )}
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
