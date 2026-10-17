"use client";

import type { ReactNode } from "react";
import { useConsole } from "@/lib/store";
import type { Source } from "@/lib/types";

const label = (s?: Source) =>
  !s ? "source" : s.kind === "doc" ? `${s.section ?? s.title}` : s.kind === "heuristic" ? `${s.owner_name ?? s.owner} (veteran note)` : s.id;

/** `code`, **bold** and [n] / [n, m] markers; everything else is plain text. */
const TOKEN = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[\d+(?:,\s*\d+)*\])/g;

/** The assistant's natural answer. [n] markers open the cited source; cited sources are listed underneath as footnotes. */
export function ReplyText({ reply, cites, sources }: { reply: string; cites: Record<string, string>; sources: Source[] }) {
  const { openSource } = useConsole();
  const byId = new Map(sources.map((s) => [s.id, s]));

  const cite = (n: string, key: string): ReactNode => {
    const id = cites[n];
    if (!id) return null;
    return (
      <button key={key} type="button" onClick={() => openSource(id, sources)} title={label(byId.get(id))}
        aria-label={`Open source ${n}: ${label(byId.get(id))}`}
        className="num mx-px rounded-[2px] text-[0.92em] font-medium text-accent hover:underline">
        [{n}]
      </button>
    );
  };

  const nodes = reply.split(TOKEN).map((p, i) => {
    if (p.startsWith("`") && p.endsWith("`") && p.length > 2) return <code key={i} className="code">{p.slice(1, -1)}</code>;
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) return <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong>;
    const m = p.match(/^\[(\d+(?:,\s*\d+)*)\]$/);
    if (m) return <span key={i}>{m[1].split(/,\s*/).map((n) => cite(n, `${i}-${n}`))}</span>;
    return <span key={i}>{p}</span>;
  });

  return (
    <div className="space-y-2.5">
      <div className="whitespace-pre-wrap text-[14px] leading-[1.65]">{nodes}</div>
      {Object.keys(cites).length > 0 && (
        <ol className="space-y-0.5 border-t border-line pt-2 text-[12px] text-muted" aria-label="Cited sources">
          {Object.entries(cites).sort((a, b) => Number(a[0]) - Number(b[0])).map(([n, id]) => {
            const s = byId.get(id);
            return (
              <li key={n}>
                <button type="button" className="grid w-full grid-cols-[2rem_1fr] text-left hover:text-fg" onClick={() => openSource(id, sources)}>
                  <span className="num text-accent">[{n}]</span>
                  <span className="hover:underline">
                    {s?.kind === "heuristic" ? "Veteran · " : "Manual · "}{label(s)}
                    {s?.kind === "doc" && s.applies_to ? ` — ${s.applies_to}` : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
