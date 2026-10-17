import { UserSearch } from "lucide-react";
import type { ChatRefer } from "@/lib/types";
import { ContextChip } from "./ContextChip";
import { ExpertList } from "./ExpertList";

export function ReferCard({ data }: { data: ChatRefer }) {
  return (
    <div className="space-y-2.5">
      <ContextChip display={data.context.display} confidence={data.context.confidence} />
      <section aria-label="Referral" className="card space-y-2.5 border-warn/50 p-3">
        <p className="flex items-start gap-2 text-[13.5px] font-medium">
          <UserSearch size={16} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
          <span>
            I can’t answer this reliably. <span className="font-normal text-muted">{data.reason}</span>
          </span>
        </p>
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted">Who to talk to</h4>
        <ExpertList experts={data.experts} />
      </section>
    </div>
  );
}
