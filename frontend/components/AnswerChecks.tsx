import { Check, TriangleAlert } from "lucide-react";
import type { Quality } from "@/lib/types";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const level = (c: number) => (c >= 0.85 ? "high" : c >= 0.6 ? "medium" : "low");

export function AnswerChecks({ q }: { q: Quality }) {
  if (q.mode === "assistant") {
    const n = q.sources_by_lane.doc + q.sources_by_lane.veteran;
    return (
      <p aria-label="Answer checks" className={`flex items-start gap-1.5 text-[11.5px] ${n ? "text-muted" : "text-warn"}`}
         title={Object.entries(q.stages_ms).map(([k, v]) => `${k} ${v} ms`).join(" · ")}>
        {n ? <Check size={13} className="mt-px shrink-0" aria-hidden="true" /> : <TriangleAlert size={13} className="mt-px shrink-0" aria-hidden="true" />}
        <span>
          {n ? `${n} source${n === 1 ? "" : "s"} cited (${q.sources_by_lane.doc} manual · ${q.sources_by_lane.veteran} veteran)` : "no sources cited"}
          {" · "}{(q.latency_ms / 1000).toFixed(1)} s
        </span>
      </p>
    );
  }
  const warn = q.dropped > 0 || q.support_min < 0.6 || !q.gate.sufficient;
  const Icon = warn ? TriangleAlert : Check;
  const parts = [
    `${q.claims_verified}/${q.claims_total} claims verified${q.dropped > 0 ? ` (${q.dropped} dropped)` : ""}`,
    q.claims_verified > 0 ? `support avg ${pct(q.support_avg)}, min ${pct(q.support_min)}` : null,
    `context ${level(q.context_confidence)}`,
    `${q.sources_by_lane.doc} doc · ${q.sources_by_lane.veteran} veteran`,
    `gate ${q.gate.sufficient ? "passed" : "failed"}`,
    `${(q.latency_ms / 1000).toFixed(1)} s`,
  ].filter(Boolean);
  return (
    <p
      aria-label="Answer checks"
      className={`flex items-start gap-1.5 text-[11.5px] ${warn ? "text-warn" : "text-muted"}`}
      title={Object.entries(q.stages_ms).map(([k, v]) => `${k} ${v} ms`).join(" · ")}
    >
      <Icon size={13} className="mt-px shrink-0" aria-hidden="true" />
      <span>{parts.join(" · ")}</span>
    </p>
  );
}
