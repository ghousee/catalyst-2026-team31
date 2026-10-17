"use client";

import { Search } from "lucide-react";
import { useState, type ReactNode } from "react";
import { admin, type GraphSnapshot } from "@/lib/admin";
import { usePolling } from "@/lib/hooks";
import { GraphCanvas } from "./GraphCanvas";
import { SplitPane } from "./SplitPane";

/** Live graph snapshot (GET /graph), refreshed every 10 s. Shared with the Systems page. */
export const useGraph = () => usePolling(() => admin.graph(), 10000, "graph");

const KIND_LABEL: Record<string, string> = {
  note_signed: "Note signed",
  note_drafted: "Note drafted",
  links_auto: "Auto links",
  links_human: "Human links",
  document_loaded: "Manual loaded",
};

const breakdown = (o: Record<string, number>) => Object.entries(o).map(([k, v]) => `${v} ${k}`).join(" · ") || "none";
const sum = (o: Record<string, number>) => Object.values(o).reduce((a, b) => a + b, 0);

function Tile({ label, value, note }: { label: string; value: number | string; note: string }) {
  return (
    <article className="rounded-2xl border border-line bg-panel p-4 shadow-sm">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-2 text-xs leading-4 text-muted">{note}</p>
    </article>
  );
}

function Panel({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
      <div className="shrink-0 border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {sub && <p className="text-xs text-muted">{sub}</p>}
      </div>
      <div className="scroll min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

const TH = "px-4 py-2 font-medium";
const Head = ({ cols }: { cols: string[] }) => (
  <thead className="sticky top-0 bg-panel2 text-xs text-muted"><tr>{cols.map((c) => <th key={c} className={TH}>{c}</th>)}</tr></thead>
);

function Origin({ by }: { by: string | null }) {
  const who = by ?? "seed";
  const cls = who === "seed" ? "bg-panel2 text-muted" : "bg-accent/10 text-accent";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>{who === "seed" ? "seed" : `${who} (new)`}</span>;
}

export function KnowledgeGraphPage() {
  const { data, error, loading } = useGraph();
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const has = (...parts: (string | null)[]) => !needle || parts.join(" ").toLowerCase().includes(needle);

  return (
    <div className="flex h-full flex-col">
      <header className="mb-4">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-accent">Live data from the database</p>
        <h2 className="text-2xl font-semibold tracking-tight text-fg">Knowledge graph</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          What the assistant actually knows. Refreshes every 10 s: sign a note or upload a manual and watch the counts, links and recent changes move.
        </p>
      </header>
      {error && <p role="alert" className="mb-3 rounded-xl border border-crit/30 bg-crit/8 p-3 text-sm text-crit">Graph unavailable: {error}</p>}
      {!data && loading && <p className="text-sm text-muted">Loading graph...</p>}
      {data && <Body data={data} q={q} setQ={setQ} has={has} />}
    </div>
  );
}

function Body({ data, q, setQ, has }: { data: GraphSnapshot; q: string; setQ: (v: string) => void; has: (...p: (string | null)[]) => boolean }) {
  const c = data.counts;
  const ents = data.entities.filter((e) => has(e.id, e.kind, e.name, e.aliases.join(" ")));
  const links = data.links.filter((l) => has(l.src, l.rel, l.dst, l.source_id, l.created_by ?? "seed"));
  const [view, setView] = useState<"graph" | "tables">("graph");
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Tile label="Entities" value={sum(c.entities)} note={breakdown(c.entities)} />
        <Tile label="Links" value={sum(c.links)} note={breakdown(c.links)} />
        <Tile label="People" value={c.persons} note="veterans who own notes" />
        <Tile label="Expert notes" value={c.notes.approved} note={`approved · ${c.notes.draft} draft · ${c.notes.needs_review} needs review · ${c.notes.retired} retired`} />
        <Tile label="Manual sections" value={c.doc_sections} note={`in ${c.documents} documents`} />
      </div>
      <div className="mt-3 flex gap-1" role="tablist" aria-label="Graph view">
        {(["graph", "tables"] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={view === t} onClick={() => setView(t)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${view === t ? "bg-accent/10 text-accent" : "text-muted hover:text-fg"}`}>
            {t === "graph" ? "Graph" : "Tables"}
          </button>
        ))}
      </div>
      {view === "graph" && <div className="mt-2 h-[78vh] min-h-[560px]"><GraphCanvas data={data} /></div>}
      {view === "tables" && <>
      <label className="relative mt-3 block max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} aria-hidden="true" />
        <input className="field h-10 w-full rounded-xl bg-panel pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter entities and links" aria-label="Filter entities and links" />
      </label>

      <div className="mt-3 flex h-[78vh] min-h-[560px]">
        <SplitPane direction="horizontal" id="graph-main" label="entities and the other tables" initial={0.4} minFirst={260} minSecond={320}>
          <Panel title={`Entities (${ents.length})`} sub="Kind, name, aliases, number of links">
            <table className="w-full text-left text-sm">
              <Head cols={["Kind", "Name", "Aliases", "Links"]} />
              <tbody className="divide-y divide-line">
                {ents.map((e) => (
                  <tr key={e.id} className="align-top hover:bg-panel2/40">
                    <td className="px-4 py-2 text-muted">{e.kind}</td>
                    <td className="px-4 py-2"><p className="font-medium">{e.name}</p><p className="font-mono text-[11px] text-muted">{e.id}</p></td>
                    <td className="px-4 py-2 text-xs text-muted">{e.aliases.join(", ") || "none"}</td>
                    <td className="px-4 py-2 tabular-nums">{e.links}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <SplitPane direction="vertical" id="graph-right" label="links and the lower tables" initial={0.4} minFirst={120} minSecond={160}>
            <Panel title={`Links (${links.length} of ${data.links_total})`} sub="Newly created links come first; each cites its source">
              <table className="w-full text-left text-sm">
                <Head cols={["From", "Relation", "To", "Citation", "Origin"]} />
                <tbody className="divide-y divide-line">
                  {links.map((l) => (
                    <tr key={`${l.src}|${l.rel}|${l.dst}`} className="align-top hover:bg-panel2/40">
                      <td className="px-4 py-2 font-mono text-[11px]">{l.src}</td>
                      <td className="px-4 py-2">{l.rel}</td>
                      <td className="px-4 py-2 font-mono text-[11px]">{l.dst}</td>
                      <td className="px-4 py-2 font-mono text-[11px] text-muted">{l.source_id ?? "none"}</td>
                      <td className="px-4 py-2"><Origin by={l.created_by} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <SplitPane direction="vertical" id="graph-bottom" label="expert notes and recent changes" initial={0.55} minFirst={120} minSecond={120}>
              <Panel title={`Expert notes (${data.notes.length})`} sub="Owner, scope, status, review flag">
                <table className="w-full text-left text-sm">
                  <Head cols={["Note", "Owner", "Scope", "Status", "Review"]} />
                  <tbody className="divide-y divide-line">
                    {data.notes.map((n) => (
                      <tr key={n.id} className="align-top hover:bg-panel2/40">
                        <td className="px-4 py-2 font-mono text-[11px]">{n.id}</td>
                        <td className="px-4 py-2">{n.owner_name}</td>
                        <td className="px-4 py-2 text-muted">{n.scope}</td>
                        <td className="px-4 py-2">{n.status}</td>
                        <td className="px-4 py-2">{n.needs_review ? <span className="status-chip status-warning">Needs review</span> : <span className="text-muted">Up to date</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <Panel title="Recent changes" sub="Newest first; links are dated by the note that created them">
                {data.recent.length === 0 && <p className="p-4 text-sm text-muted">No changes yet.</p>}
                <ul className="divide-y divide-line text-sm">
                  {data.recent.map((r, i) => (
                    <li key={`${r.ts}-${i}`} className="flex flex-wrap gap-x-3 px-4 py-2">
                      <span className="w-24 shrink-0 text-xs text-muted">{r.ts}</span>
                      <span className="w-28 shrink-0 text-xs font-medium">{KIND_LABEL[r.type] ?? r.type}</span>
                      <span className="min-w-0 flex-1">{r.text}</span>
                    </li>
                  ))}
                </ul>
              </Panel>
            </SplitPane>
          </SplitPane>
        </SplitPane>
      </div>
      </>}
    </>
  );
}
