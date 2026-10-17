import { TriangleAlert } from "lucide-react";
import type { Claim, Source } from "@/lib/types";
import { ClaimList } from "./ClaimList";

// Both sides of a conflict, side by side in one box, so the operator is never shown only one of them.
export function ConflictBox({ claims, sources }: { claims: Claim[]; sources?: Source[] }) {
  const name = (id: string) => {
    const s = sources?.find((x) => x.id === id);
    return s?.kind === "heuristic" ? (s.owner_name ?? s.owner) : s?.kind === "doc" ? s.title : id.startsWith("doc:") ? "the manual" : id;
  };
  const disagree = claims.filter((c) => c.conflict_with);
  const contradicts = claims.filter((c) => c.contradicts && !c.conflict_with);
  return (
    <>
      {disagree.length > 0 && (
        <Box title="Veterans disagree" who={[...new Set(disagree.map((c) => name(c.source_id)))].join(" vs ")}>
          <ClaimList claims={disagree} sources={sources} />
        </Box>
      )}
      {contradicts.length > 0 && (
        <Box
          title="Veteran contradicts the manual"
          who={contradicts.map((c) => `${name(c.source_id)} vs ${name(c.contradicts!)}`).join("; ")}
        >
          <ClaimList claims={contradicts} sources={sources} />
        </Box>
      )}
    </>
  );
}

function Box({ title, who, children }: { title: string; who: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={title} className="space-y-2 border-l-2 border-warn bg-warn/5 py-1.5 pl-3 pr-2">
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-warn">
        <TriangleAlert size={13} aria-hidden="true" /> {title}: {who}
      </p>
      {children}
    </div>
  );
}
