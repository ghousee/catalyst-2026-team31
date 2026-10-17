"use client";

import { useConsole } from "@/lib/store";
import type { Source } from "@/lib/types";

const label = (s?: Source) =>
  !s ? "source" : s.kind === "doc" ? `${s.section ?? s.title}` : s.kind === "heuristic" ? `${s.owner_name ?? s.owner} (veteran note)` : s.id;

/** The assistant's natural answer; [n] markers open the cited source. Cited sources are listed underneath. */
export function ReplyText({ reply, cites, sources }: { reply: string; cites: Record<string, string>; sources: Source[] }) {
  const { openSource } = useConsole();
  const byId = new Map(sources.map((s) => [s.id, s]));
  const parts = reply.split(/(\[\d+(?:,\s*\d+)*\])/g);
  return (
    <div className="space-y-2">
      <div className="whitespace-pre-wrap text-[14px] leading-relaxed">
        {parts.map((p, i) => {
          const m = p.match(/^\[(.+)\]$/);
          if (!m) return <span key={i}>{p}</span>;
          return (
            <span key={i}>
              {m[1].split(/,\s*/).map((n) => {
                const id = cites[n];
                return id ? (
                  <button key={n} type="button" onClick={() => openSource(id, sources)} title={label(byId.get(id))}
                    aria-label={`Open source ${n}: ${label(byId.get(id))}`}
                    className="mx-0.5 rounded bg-accent/10 px-1 align-super text-[10.5px] font-semibold text-accent hover:bg-accent/20">
                    {n}
                  </button>
                ) : null;
              })}
            </span>
          );
        })}
      </div>
      {Object.keys(cites).length > 0 && (
        <ol className="space-y-0.5 border-t border-line pt-2 text-[12px] text-muted" aria-label="Cited sources">
          {Object.entries(cites).sort((a, b) => Number(a[0]) - Number(b[0])).map(([n, id]) => {
            const s = byId.get(id);
            return (
              <li key={n}>
                <button type="button" className="text-left hover:text-fg hover:underline" onClick={() => openSource(id, sources)}>
                  [{n}] {s?.kind === "heuristic" ? "Veteran · " : "Manual · "}{label(s)}
                  {s?.kind === "doc" && s.applies_to ? ` — ${s.applies_to}` : ""}
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
