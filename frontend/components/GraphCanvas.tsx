"use client";

import { Crosshair, Expand, Maximize2, Pause, Play, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphSnapshot } from "@/lib/admin";

/** Interactive, live view of the knowledge graph (vis-network, same library as docs/knowledge_graph.html).
 *  Drag nodes, zoom, click for details, double-click to isolate a neighbourhood. Updates in place when /graph changes,
 *  so newly signed notes and auto-created links appear without resetting the layout. */

type Kind = "system" | "event" | "object" | "metric" | "command" | "site" | "version" | "person" | "emerging" | "note" | "doc" | "other";

const STYLE: Record<Kind, { color: string; shape: string; size: number; label: string }> = {
  system: { color: "#1b56b2", shape: "dot", size: 26, label: "Subsystem" },
  event: { color: "#e5484d", shape: "dot", size: 15, label: "Event" },
  object: { color: "#38a8f0", shape: "dot", size: 15, label: "Object" },
  metric: { color: "#0e9aa7", shape: "dot", size: 13, label: "Metric" },
  command: { color: "#2fa05b", shape: "diamond", size: 13, label: "Command" },
  site: { color: "#d9480f", shape: "hexagon", size: 20, label: "Node" },
  version: { color: "#94a3b8", shape: "hexagon", size: 12, label: "Series" },
  person: { color: "#6a3fc4", shape: "star", size: 24, label: "Veteran" },
  emerging: { color: "#0e9aa7", shape: "triangle", size: 14, label: "Emerging Veteran" },
  note: { color: "#e08a00", shape: "dot", size: 16, label: "Veteran note" },
  doc: { color: "#a9bbd3", shape: "box", size: 10, label: "Manual section" },
  other: { color: "#9ca3af", shape: "dot", size: 10, label: "Other" },
};
const REL_COLOR: Record<string, string> = { contradicts: "#e5484d", disagrees_with: "#ea580c", expert_in: "#6a3fc4", precedes: "#b45309" };

type GNode = { id: string; kind: Kind; label: string; detail: Record<string, string> };

function kindOf(id: string): Kind {
  if (id.startsWith("doc:")) return "doc";
  if (/^[a-z]+:h\d+$/.test(id)) return "note";
  return "other";
}

/** Nodes = entities + veteran notes + people + manual sections that appear in links. Pure; used for diffing. */
function buildGraph(data: GraphSnapshot) {
  const owners = new Map(data.notes.map((n) => [n.id.split(":")[0], n.owner_name]));
  const people = new Map((data.people ?? []).map((p) => [p.id, p]));
  const nodes = new Map<string, GNode>();
  for (const e of data.entities) {
    const k = (Object.keys(STYLE).includes(e.kind) ? e.kind : "other") as Kind;
    nodes.set(e.id, { id: e.id, kind: k, label: e.name, detail: { Kind: STYLE[k].label, Id: e.id, Aliases: e.aliases.join(", ") || "none" } });
  }
  for (const n of data.notes) {
    nodes.set(n.id, {
      id: n.id, kind: "note", label: `${n.owner_name.split(" ")[0]} · ${n.id.split(":")[1]}`,
      detail: { Kind: "Veteran note", Owner: n.owner_name, Scope: n.scope, Status: n.status + (n.needs_review ? " (needs review)" : ""), Advice: n.call_text },
    });
  }
  for (const l of data.links) {
    for (const id of [l.src, l.dst]) {
      if (nodes.has(id)) continue;
      if (l.rel === "expert_in" && id === l.src) {
        const p = people.get(id);
        const kind: Kind = p?.level === "emerging" ? "emerging" : "person";
        nodes.set(id, { id, kind, label: p?.name ?? owners.get(id) ?? id, detail: { Kind: STYLE[kind].label, Id: id, Role: p?.role ?? "" } });
      } else {
        const k = kindOf(id);
        const label = k === "doc" ? id.replace(/^doc:/, "").replace(/-/g, " ").slice(0, 38) : id;
        nodes.set(id, { id, kind: k, label, detail: { Kind: STYLE[k].label, Id: id } });
      }
    }
  }
  const edges = data.links.map((l) => ({
    id: `${l.src}|${l.rel}|${l.dst}`, from: l.src, to: l.dst, label: l.rel, rel: l.rel,
    auto: !!l.created_by && l.created_by !== "seed", citation: l.source_id,
  }));
  return { nodes, edges };
}

export function GraphCanvas({ data }: { data: GraphSnapshot }) {
  const box = useRef<HTMLDivElement>(null);
  // vis objects live in refs: created once, then updated in place on every poll
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vis = useRef<{ net: any; nodes: any; edges: any } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [physics, setPhysics] = useState(true);
  const [hidden, setHidden] = useState<Set<Kind>>(new Set(["version"]));
  const [focusIds, setFocusIds] = useState<Set<string> | null>(null);
  const [q, setQ] = useState("");
  const [labels, setLabels] = useState(false);
  // manual-extracted entities (ids "cmd:auto:..", "evt:auto:..") are ~1,700 nodes: hidden by default, optionally per subsystem
  const [showAuto, setShowAuto] = useState(false);
  const [autoSub, setAutoSub] = useState("sub:TMF"); // relation labels on links (off by default: they clutter)
  const [ready, setReady] = useState(false); // vis-network loads asynchronously; re-sync once it exists
  const graph = useMemo(() => buildGraph(data), [data]);
  const graphRef = useRef(graph);
  graphRef.current = graph;

  const isAuto = (id: string) => id.includes(":auto:");
  const autoOk = (n: GNode) => !isAuto(n.id) || (showAuto && (autoSub === "all" || n.id.startsWith(`${n.id.split(":")[0]}:auto:${autoSub.replace("sub:", "").toLowerCase()}:`)));
  const visible = (n: GNode) => !hidden.has(n.kind) && autoOk(n) && (!focusIds || focusIds.has(n.id));
  const autoCount = useMemo(() => [...graph.nodes.keys()].filter(isAuto).length, [graph]);
  const subs = useMemo(() => data.entities.filter((e) => e.kind === "system").map((e) => ({ id: e.id, name: e.name })), [data]);

  // create the network once
  useEffect(() => {
    let alive = true;
    void import("vis-network/standalone").then(({ Network, DataSet }) => {
      if (!alive || !box.current || vis.current) return;
      const fg = getComputedStyle(document.documentElement).getPropertyValue("--fg").trim().split(/\s+/).join(",");
      const nodes = new DataSet([]);
      const edges = new DataSet([]);
      const net = new Network(box.current, { nodes, edges }, {
        autoResize: true,
        physics: { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: -60, springLength: 110 }, stabilization: { iterations: 200 } },
        interaction: { hover: true, navigationButtons: true, keyboard: true, tooltipDelay: 150 },
        nodes: { font: { color: `rgb(${fg})`, size: 12, face: "inherit" }, borderWidth: 1 },
        edges: { arrows: { to: { enabled: true, scaleFactor: 0.5 } }, font: { size: 9, color: `rgb(${fg})`, strokeWidth: 0, align: "middle" },
                 smooth: { enabled: true, type: "continuous", roundness: 0.4 }, width: 1 },
      });
      net.once("stabilizationIterationsDone", () => net.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } }));
      net.on("click", (p: { nodes: string[] }) => setSelected(p.nodes[0] ?? null));
      net.on("doubleClick", (p: { nodes: string[] }) => {
        if (!p.nodes[0]) { setFocusIds(null); return; }
        const id = p.nodes[0];
        const ids = new Set([id, ...graphRef.current.edges.filter((e) => e.from === id || e.to === id).flatMap((e) => [e.from, e.to])]);
        setFocusIds(ids);
      });
      vis.current = { net, nodes, edges };
      setReady(true);
    });
    return () => {
      alive = false;
      vis.current?.net.destroy();
      vis.current = null;
    };
  }, []);

  // sync data + filters into the DataSets (add / update / remove; layout is kept)
  useEffect(() => {
    const v = vis.current;
    if (!v) return;
    const ns = [...graph.nodes.values()].filter(visible).map((n) => ({
      id: n.id, label: n.label, shape: STYLE[n.kind].shape, size: STYLE[n.kind].size,
      color: { background: STYLE[n.kind].color, border: STYLE[n.kind].color, highlight: { background: STYLE[n.kind].color, border: "#111827" } },
      font: n.kind === "doc" ? { color: "#111827", size: 10 } : undefined,
      title: `${STYLE[n.kind].label}: ${n.label}`,
    }));
    const ids = new Set(ns.map((n) => n.id));
    const es = graph.edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e) => ({
      id: e.id, from: e.from, to: e.to, label: labels ? e.label : undefined, dashes: e.auto,
      color: { color: REL_COLOR[e.rel] ?? "#9ca3af", highlight: "#111827" }, width: e.auto ? 2 : 1,
      title: `${e.rel}${e.citation ? ` · cites ${e.citation}` : ""}${e.auto ? " · auto-created" : ""}`,
    }));
    // a manual-section node whose links all go to hidden nodes would float alone: hide it too
    const linked = new Set(es.flatMap((e) => [e.from, e.to]));
    const nsShown = ns.filter((n) => !n.id.startsWith("doc:") || linked.has(n.id));
    const drop = (set: { getIds: () => string[]; remove: (ids: string[]) => void }, keep: Set<string>) =>
      set.remove(set.getIds().filter((i: string) => !keep.has(i)));
    drop(v.edges, new Set(es.map((e) => e.id)));
    drop(v.nodes, new Set(nsShown.map((n) => n.id)));
    v.nodes.update(nsShown);
    v.edges.update(es);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, hidden, focusIds, ready, labels, showAuto, autoSub]);

  useEffect(() => {
    vis.current?.net.setOptions({ physics: { enabled: physics } });
  }, [physics]);

  const find = () => {
    const needle = q.trim().toLowerCase();
    if (!needle || !vis.current) return;
    const hit = [...graph.nodes.values()].find((n) => visible(n) && (n.label.toLowerCase().includes(needle) || n.id.toLowerCase().includes(needle)));
    if (!hit) return;
    vis.current.net.selectNodes([hit.id]);
    vis.current.net.focus(hit.id, { scale: 1.3, animation: { duration: 500 } });
    setSelected(hit.id);
  };

  const sel = selected ? graph.nodes.get(selected) : null;
  const out = selected ? graph.edges.filter((e) => e.from === selected) : [];
  const inc = selected ? graph.edges.filter((e) => e.to === selected) : [];
  const jump = (id: string) => {
    setSelected(id);
    vis.current?.net.selectNodes([id]);
    vis.current?.net.focus(id, { scale: 1.2, animation: { duration: 400 } });
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <label className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" size={14} aria-hidden="true" />
          <input className="field h-8 w-56 rounded bg-panel pl-8" placeholder="Find a node (e.g. TMF 185, Maria)" value={q}
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} aria-label="Find a node" />
        </label>
        <button type="button" className="btn" onClick={find}><Crosshair size={13} aria-hidden="true" /> Find</button>
        <button type="button" className="btn" onClick={() => vis.current?.net.fit({ animation: { duration: 400 } })}><Maximize2 size={13} aria-hidden="true" /> Fit</button>
        <button type="button" className="btn" onClick={() => setPhysics((p) => !p)} aria-pressed={!physics}>
          {physics ? <Pause size={13} aria-hidden="true" /> : <Play size={13} aria-hidden="true" />} {physics ? "Freeze layout" : "Resume layout"}
        </button>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={showAuto} onChange={(e) => setShowAuto(e.target.checked)} />
          Commands &amp; messages from the manuals ({autoCount})
        </label>
        {showAuto && (
          <select className="field h-8 rounded bg-panel px-2" value={autoSub} onChange={(e) => setAutoSub(e.target.value)} aria-label="Subsystem for manual-extracted nodes">
            {subs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            <option value="all">All subsystems (slow)</option>
          </select>
        )}
        <button type="button" className="btn" onClick={() => setLabels((l) => !l)} aria-pressed={labels}>
          {labels ? "Hide link labels" : "Show link labels"}
        </button>
        {focusIds && <button type="button" className="btn" onClick={() => setFocusIds(null)}><Expand size={13} aria-hidden="true" /> Show whole graph</button>}
        <span className="ml-auto text-muted">Drag to move · scroll to zoom · click for details · double-click to isolate</span>
      </div>
      <div className="flex flex-wrap gap-1.5 text-[11px]" role="group" aria-label="Show or hide node kinds">
        {(Object.keys(STYLE) as Kind[]).filter((k) => k !== "other").map((k) => (
          <button key={k} type="button" aria-pressed={!hidden.has(k)}
            onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}
            className={`flex items-center gap-1 rounded border px-2 py-0.5 ${hidden.has(k) ? "border-line text-muted line-through" : "border-line bg-panel"}`}>
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STYLE[k].color }} aria-hidden="true" />{STYLE[k].label}
          </button>
        ))}
        <span className="flex items-center gap-1 px-2 text-muted"><span className="inline-block w-5 border-t-2 border-dashed border-muted" aria-hidden="true" />auto-created link</span>
        <span className="flex items-center gap-1 px-2 text-muted"><span className="inline-block w-5 border-t-2" style={{ borderColor: REL_COLOR.contradicts }} aria-hidden="true" />contradicts</span>
      </div>
      <div className="flex min-h-0 flex-1 gap-2">
        <div ref={box} className="min-h-0 flex-1 rounded-xl border border-line bg-panel shadow-soft" aria-label="Synapse knowledge graph canvas" role="img" />
        <aside className="scroll w-72 shrink-0 overflow-auto rounded-xl border border-line bg-panel shadow-soft p-3 text-sm" aria-label="Selected node details">
          {!sel && <p className="text-muted">Click a node to see what it is and how it connects. Double-click to show only its neighbours.</p>}
          {sel && (
            <div className="space-y-3">
              <div>
                <p className="label" style={{ color: STYLE[sel.kind].color }}>{STYLE[sel.kind].label}</p>
                <p className="font-semibold">{sel.label}</p>
              </div>
              <dl className="space-y-1.5 text-xs">
                {Object.entries(sel.detail).map(([k, v]) => (
                  <div key={k}><dt className="text-muted">{k}</dt><dd className="break-words">{v}</dd></div>
                ))}
              </dl>
              {[["Links out", out, "to"], ["Links in", inc, "from"]].map(([title, list, end]) => (
                (list as typeof out).length > 0 && (
                  <div key={title as string}>
                    <p className="mb-1 label">{title as string} ({(list as typeof out).length})</p>
                    <ul className="space-y-1 text-xs">
                      {(list as typeof out).map((e) => {
                        const other = end === "to" ? e.to : e.from;
                        return (
                          <li key={e.id}>
                            <span className="text-muted">{e.rel}{e.auto ? " (auto)" : ""} </span>
                            <button type="button" className="text-left text-accent hover:underline" onClick={() => jump(other)}>
                              {graph.nodes.get(other)?.label ?? other}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
