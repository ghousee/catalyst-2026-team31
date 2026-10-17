import { CircleAlert } from "lucide-react";
import type { Claim, Source } from "@/lib/types";
import { CitationChip } from "./CitationChip";
import { LaneBadge } from "./LaneBadge";

export function ClaimList({ claims, sources }: { claims: Claim[]; sources?: Source[] }) {
  return (
    <ul className="space-y-2.5">
      {claims.map((c, i) => (
        <li key={`${c.source_id}-${i}`} className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
          <span className="pt-0.5">
            <LaneBadge lane={c.lane} />
          </span>
          <div className="min-w-0">
            <p className="text-[13.5px] leading-snug">{c.text}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <CitationChip sourceId={c.source_id} lane={c.lane} sources={sources} />
              {c.verbatim ? (
                <span className="text-[11px] text-muted" title="The veteran's own words, not rephrased">
                  verbatim
                </span>
              ) : c.verified ? (
                <span className="text-[11px] text-muted" title={`Verifier score ${c.score}`}>
                  verified · {Math.round(c.score * 100)}%
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-warn">
                  <CircleAlert size={11} aria-hidden="true" /> unverified
                </span>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
