"use client";

import {
  BellRing,
  BookOpen,
  Bot,
  ChevronRight,
  CircleHelp,
  GraduationCap,
  LayoutDashboard,
  Map,
  Menu,
  Network,
  Search,
  Server,
  TriangleAlert,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { ALERTS_ARE_MOCK, GROUPS, api, liveGroups } from "@/lib/api";
import { admin, subName } from "@/lib/admin";
import { fmtTime } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { ConsoleProvider, useConsole } from "@/lib/store";
import type { MetricsResponse, ScenarioName } from "@/lib/types";
import { AlertsPanel } from "./AlertsPanel";
import { ChatPane } from "./ChatPane";
import { KnowledgeGraphPage, useGraph } from "./KnowledgeGraphPage";
import { LearningPage } from "./LearningPage";
import { NodeSwitcher } from "./NodeSwitcher";
import { SourceDialog } from "./SourceDialog";
import { Sparkline } from "./Sparkline";
import { ThemeToggle } from "./ThemeToggle";

type PageId = "overview" | "systems" | "investigations" | "assistant" | "knowledge" | "simulator" | "graph" | "learning";

const NAV: Array<{ id: PageId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "systems", label: "Systems", icon: Server },
  { id: "investigations", label: "Investigations", icon: BellRing },
  { id: "assistant", label: "AI Assistant", icon: Bot },
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "simulator", label: "Training Simulator", icon: GraduationCap },
  { id: "graph", label: "Knowledge graph", icon: Network },
  { id: "learning", label: "Learning map", icon: Map },
];

const METRICS = [
  { id: "audit-capacity-pct", label: "Audit trail", unit: "%", threshold: 80 },
  { id: "cpu-busy-time", label: "CPU busy", unit: "%", threshold: 85 },
  { id: "request-qtime", label: "Queue time", unit: " ms", threshold: 40 },
];

const latest = (data: MetricsResponse | null, id: string) => data?.series.find((x) => x.metric === id)?.points.at(-1)?.[1];

/** Latest simulator metrics for the session node (polled every 4 s). */
function useNodeMetrics() {
  const { session } = useConsole();
  const node = session?.node ?? "";
  return usePolling(() => (node ? api.getMetrics(node, "60m") : Promise.resolve(null)), 4000, node);
}

function SectionTitle({ title, description }: { title: string; description?: string }) {
  return (
    <header className="mb-5">
      <h2 className="text-xl font-semibold tracking-tight text-fg">{title}</h2>
      {description && <p className="mt-1 max-w-3xl text-[13px] text-muted">{description}</p>}
    </header>
  );
}

/** A titled block separated by a rule instead of a box. */
function Block({ title, aside, children, className = "" }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <div className="mb-3 flex items-baseline justify-between gap-3 border-b border-line pb-2">
        <h3 className="text-[13px] font-semibold">{title}</h3>
        {aside && <div className="text-xs text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

type Tone = "neutral" | "ok" | "warn" | "crit";
const TONE_TEXT: Record<Tone, string> = { neutral: "text-fg", ok: "text-ok", warn: "text-warn", crit: "text-crit" };

/** Compact stat strip: label, value, one short note. */
function StatStrip({ items }: { items: Array<{ label: string; value: string; note: string; tone?: Tone }> }) {
  return (
    <dl className="grid grid-cols-2 gap-y-4 border-y border-line py-3 lg:grid-cols-4 lg:gap-y-0 lg:divide-x lg:divide-line">
      {items.map((i) => (
        <div key={i.label} className="min-w-0 lg:px-5 lg:first:pl-0">
          <dt className="text-xs text-muted">{i.label}</dt>
          <dd className={`num mt-0.5 text-xl font-medium leading-tight ${TONE_TEXT[i.tone ?? "neutral"]}`}>{i.value}</dd>
          <dd className="mt-0.5 truncate text-[11.5px] text-muted" title={i.note}>{i.note}</dd>
        </div>
      ))}
    </dl>
  );
}

function HealthCharts({ metrics: { data, error, loading } }: { metrics: ReturnType<typeof useNodeMetrics> }) {
  const { session } = useConsole();

  return (
    <Block title="System health" aside={<>{session?.node_display ?? "selected node"} · simulator feed</>}>
      {error && <p role="alert" className="mb-3 text-xs text-crit">Metrics unavailable. Retrying automatically.</p>}
      <div className="grid gap-4 md:grid-cols-3 md:divide-x md:divide-line">
        {METRICS.map((metric) => {
          const values = data?.series.find((series) => series.metric === metric.id)?.points.map((point) => point[1]) ?? [];
          const current = values.at(-1);
          const over = current !== undefined && current >= metric.threshold;
          const near = current !== undefined && current >= metric.threshold * 0.75;
          const color = over ? "rgb(var(--crit))" : near ? "rgb(var(--warn))" : "rgb(var(--ok))";
          return (
            <article key={metric.id} className="md:px-5 md:first:pl-0 md:last:pr-0">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-xs text-muted">{metric.label}</p>
                <span className={`status-chip ${over ? "status-critical" : near ? "status-warning" : "status-healthy"}`}>{over ? "Critical" : near ? "Watch" : "Normal"}</span>
              </div>
              <p className="num mt-0.5 text-xl font-medium" style={{ color }}>
                {current === undefined ? (loading ? "..." : "n/a") : `${Math.round(current)}${metric.unit}`}
              </p>
              <div className="mt-2 h-12">{values.length > 1 && <Sparkline values={values} threshold={metric.threshold} color={color} />}</div>
              <p className="num mt-1 text-[11px] text-muted">limit {metric.threshold}{metric.unit.trim()}</p>
            </article>
          );
        })}
      </div>
    </Block>
  );
}

const SEVERITY_CHIP = { critical: ["status-critical", "Critical"], warning: ["status-warning", "Warning"], info: ["status-healthy", "Info"] } as const;

const TH = "px-4 py-2 font-medium first:pl-0 last:pr-0";
const TD = "px-4 py-2.5 first:pl-0 last:pr-0";

function OverviewPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { session } = useConsole();
  const { data: alerts } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const metrics = useNodeMetrics();
  const graph = useGraph();
  const list = alerts ?? [];
  const top = list[0];
  const demo = ALERTS_ARE_MOCK ? " (demo feed)" : "";
  const withData = METRICS.filter((m) => latest(metrics.data, m.id) !== undefined);
  const healthy = withData.filter((m) => (latest(metrics.data, m.id) as number) < m.threshold).length;
  const subsystems = graph.data?.counts.entities.system;

  return (
    <div>
      <SectionTitle title="Overview" />
      <StatStrip items={[
        { label: "Nodes monitored", value: session ? String(session.nodes_available.length) : "...", note: session ? session.nodes_available.map((n) => n.display).join(", ") : "Connecting" },
        { label: "Subsystems in graph", value: subsystems === undefined ? "..." : String(subsystems), note: graph.error ? "Graph unavailable" : "Live knowledge graph" },
        { label: "Indicators under limit", value: withData.length ? `${healthy} of ${withData.length}` : "n/a", note: `${session?.node_display ?? "node"}, simulator metrics`, tone: withData.length && healthy < withData.length ? "warn" : "neutral" },
        { label: `Active alerts${demo}`, value: String(list.length), note: ALERTS_ARE_MOCK ? "Scripted demo alerts; watcher not built yet" : "From the watcher", tone: list.length ? "crit" : "neutral" },
      ]} />

      <div className="mt-7 grid gap-8 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.75fr)]">
        <HealthCharts metrics={metrics} />
        <Block title="Summary" aside={ALERTS_ARE_MOCK ? "watcher, demo alerts" : "watcher"}>
          {top ? (
            <>
              <p className="text-sm leading-6">{top.message}</p>
              <p className="mt-2 text-xs leading-5 text-muted">Owner {top.owner_name} · lead time {top.lead_time_min} min · <span className="num">{top.node}</span> · {subName(top.subsystem)}</p>
            </>
          ) : (
            <p className="text-sm leading-6">No active warnings.</p>
          )}
          <button type="button" className="btn btn-primary mt-4" onClick={() => onNavigate("assistant")}>Investigate <ChevronRight size={14} aria-hidden="true" /></button>
        </Block>
      </div>

      <Block className="mt-8" title={`Needs attention${demo}`} aside={<button type="button" className="font-medium text-accent hover:underline" onClick={() => onNavigate("investigations")}>View investigations</button>}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs text-muted"><tr><th className={TH}>System</th><th className={TH}>Health</th><th className={TH}>Observation</th><th className={TH}>Source</th><th className={TH}>Updated</th></tr></thead>
            <tbody className="divide-y divide-line border-t border-line">
              {list.length === 0 && <tr><td colSpan={5} className="py-3 text-muted">No active warnings.</td></tr>}
              {list.map((a) => {
                const [cls, label] = SEVERITY_CHIP[a.severity];
                return (
                  <tr key={a.id} className="hover:bg-panel2/50"><td className={`${TD} num font-medium`}>{a.node} · {subName(a.subsystem)}</td><td className={TD}><span className={`status-chip ${cls}`}>{label}</span></td><td className={TD}>{a.message}</td><td className={`${TD} text-muted`}>{ALERTS_ARE_MOCK ? "Watcher (demo alert)" : "Watcher"}</td><td className={`${TD} num text-muted`}>{fmtTime(a.ts)}</td></tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Block>
    </div>
  );
}

function SystemsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { session } = useConsole();
  const [query, setQuery] = useState("");
  const graph = useGraph();
  const docs = usePolling(() => admin.documents(), 30000, "docs");
  const metrics = useNodeMetrics();
  const g = graph.data;
  const nodes = g?.entities.filter((e) => e.kind === "site") ?? [];
  const subs = g?.entities.filter((e) => e.kind === "system") ?? [];
  const all = nodes.flatMap((n) => subs.map((s) => {
    const short = n.id.replace(/^node:/, "");
    const notes = (g?.notes ?? []).filter((x) => x.status === "approved" && x.scope.startsWith(`${subName(s.id)} / `) && (x.scope.endsWith("all nodes") || x.scope.endsWith(` / ${short}`))).length;
    const sections = (docs.data ?? []).filter((d) => d.subsystem === s.id).reduce((t, d) => t + d.chunks, 0);
    const live = n.id === session?.node
      ? (g?.entities ?? []).filter((m) => m.kind === "metric" && m.parent_id === s.id && latest(metrics.data, m.id.replace(/^met:/, "")) !== undefined)
          .map((m) => { const id = m.id.replace(/^met:/, ""); const def = METRICS.find((x) => x.id === id); return `${def?.label ?? id}: ${Math.round(latest(metrics.data, id) as number)}${def?.unit ?? ""}`; })
      : [];
    return { key: `${n.id}|${s.id}`, node: "\\" + short, sub: s.name, notes, sections, live: live.join(", ") || "no live feed yet" };
  }));
  const rows = all.filter((r) => Object.values(r).join(" ").toLowerCase().includes(query.toLowerCase()));
  return (
    <div>
      <SectionTitle title="Systems" description="Nodes and subsystems from the knowledge graph, with the veteran notes and manual sections in scope." />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <label className="relative min-w-[260px] flex-1 sm:max-w-md"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" size={15} aria-hidden="true" /><input className="field h-9 w-full pl-8" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems" aria-label="Search systems" /></label>
        <span className="num text-xs text-muted">{rows.length} rows</span>
      </div>
      {graph.error && <p role="alert" className="mb-3 text-sm text-crit">Graph unavailable: {graph.error}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs text-muted"><tr>{["Node", "Subsystem", "Veteran notes", "Manual sections", "Live metrics", ""].map((head, i) => <th key={i} className={TH}>{head}</th>)}</tr></thead>
          <tbody className="divide-y divide-line border-y border-line">{rows.map((r) => <tr key={r.key} className="hover:bg-panel2/50"><td className={`${TD} num font-medium`}>{r.node}</td><td className={TD}>{r.sub}</td><td className={`${TD} num text-muted`}>{r.notes}</td><td className={`${TD} num text-muted`}>{r.sections}</td><td className={`${TD} text-muted`}>{r.live}</td><td className={`${TD} text-right`}><button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("assistant")}>Investigate</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function InvestigationsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  return (
    <div>
      <SectionTitle title="Investigations" description="Alerts as evidence-backed investigations. Observations, hypotheses and unknowns stay separate." />
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
        <Block title="Active watcher alerts"><AlertsPanel /></Block>
        <aside>
          <Block title="Ground rules">
            <ul className="space-y-2.5 text-sm">
              <li><strong className="font-medium">Confirmed facts.</strong> <span className="text-muted">Linked to source records.</span></li>
              <li><strong className="font-medium">Possible explanations.</strong> <span className="text-muted">Marked as unverified.</span></li>
              <li><strong className="font-medium">Next steps.</strong> <span className="text-muted">Allowlisted and human reviewed.</span></li>
            </ul>
          </Block>
          <button type="button" className="btn btn-primary mt-4" onClick={() => onNavigate("assistant")}>Open assistant</button>
        </aside>
      </div>
    </div>
  );
}

function AssistantPage() {
  const { session } = useConsole();
  const { data: alerts } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const top = alerts?.[0];
  return (
    <div className="flex h-full min-h-[680px] flex-col">
      <header className="mb-4">
        <h2 className="text-xl font-semibold tracking-tight text-fg">Assistant</h2>
        <p className="mt-1 text-[13px] text-muted">Advisory only. Facts carry a source <span className="num text-accent">[n]</span>; uncertainty is stated; commands need review and guards.</p>
      </header>
      <div className="grid min-h-0 flex-1 gap-8 xl:grid-cols-[minmax(0,1.5fr)_280px]">
        <section className="flex min-h-[570px] flex-col overflow-hidden rounded border border-line bg-panel"><ChatPane /></section>
        <aside className="space-y-6">
          <Block title="Context">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-muted">System</dt><dd className="num font-medium">{session?.node_display ?? "..."}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Top alert{ALERTS_ARE_MOCK ? " (demo)" : ""}</dt><dd className="font-medium">{top ? `${subName(top.subsystem)} · ${top.severity}` : "None"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Evidence window</dt><dd className="font-medium">last 60 min</dd></div>
            </dl>
          </Block>
          <p className="border-l-2 border-warn pl-3 text-xs leading-5 text-muted"><strong className="font-medium text-warn">No production execution.</strong> All command output here is simulated and kept only as investigation evidence.</p>
        </aside>
      </div>
    </div>
  );
}

function KnowledgePage() {
  const [filter, setFilter] = useState<"all" | "manuals" | "expert">("all");
  const docs = usePolling(() => admin.documents(), 15000, "kdocs");
  const notes = usePolling(() => admin.notes("approved"), 15000, "knotes");
  const entries = [
    ...(docs.data ?? []).map((d) => ({ id: `doc:${d.key}`, name: d.title, detail: `${d.edition ?? "no edition"} • ${d.chunks} sections`, type: "Manual", scope: `${subName(d.subsystem)}, all nodes`, status: "Approved", review: d.removed ? `${d.removed} sections removed` : `Loaded ${d.last_loaded ?? "n/a"}`, warn: d.removed > 0 })),
    ...(notes.data ?? []).map((n) => ({ id: n.id, name: `${n.owner_name} expert note (${n.id})`, detail: n.call_text, type: "Expert note", scope: `${subName(n.subsystem)}, ${n.node === "ALL" ? "all nodes" : "\\" + n.node}`, status: "Approved", review: n.needs_review ? "Needs review" : `Signed ${n.signed_at || "n/a"}`, warn: n.needs_review })),
  ];
  const visible = entries.filter((entry) => filter === "all" || (filter === "manuals" ? entry.type === "Manual" : entry.type === "Expert note"));
  const err = docs.error ?? notes.error;
  return (
    <div>
      <SectionTitle title="Knowledge" description="Manuals and signed expert notes the assistant answers from. Live from the database." />
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line">
        <div role="tablist" aria-label="Knowledge filter" className="flex gap-5">
          {(["all", "manuals", "expert"] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={filter === item} className={`-mb-px border-b-2 py-2 text-sm font-medium ${filter === item ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg"}`} onClick={() => setFilter(item)}>{item === "all" ? "All" : item === "manuals" ? "Manuals & runbooks" : "Expert notes"}</button>)}
        </div>
        <span className="mb-1 ml-auto flex gap-2"><a className="btn" href="/knowledge">Add knowledge / sign-off</a><a className="btn" href="/documents">Add document</a></span>
      </div>
      {err && <p role="alert" className="mb-3 text-sm text-crit">Knowledge unavailable: {err}</p>}
      <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="text-xs text-muted"><tr><th className={TH}>Name</th><th className={TH}>Type</th><th className={TH}>Applicable scope</th><th className={TH}>Status</th><th className={TH}>Review</th></tr></thead><tbody className="divide-y divide-line border-y border-line">{visible.map((entry) => <tr key={entry.id} className="hover:bg-panel2/50"><td className={`${TD} max-w-md`}><p className="font-medium">{entry.name}</p><p className="mt-0.5 truncate text-xs text-muted">{entry.detail}</p></td><td className={`${TD} text-muted`}>{entry.type}</td><td className={`${TD} text-muted`}>{entry.scope}</td><td className={TD}><span className="status-chip status-healthy">{entry.status}</span></td><td className={TD}>{entry.warn ? <span className="status-chip status-warning">{entry.review}</span> : <span className="text-muted">{entry.review}</span>}</td></tr>)}</tbody></table></div>
      <p className="mt-3 text-xs text-muted">New notes stay drafts until their owner signs them on the Add knowledge page; only signed notes appear here and in answers.</p>
    </div>
  );
}

const SCENARIOS: Array<{ id: ScenarioName; title: string; description: string; difficulty: string; duration: string }> = [
  { id: "audit_trail_fill", title: "Audit trail filling", description: "Investigate rising capacity and identify the transaction pinning an audit file.", difficulty: "Beginner", duration: "8 min" },
  { id: "disk_revive_stall", title: "Disk mirror revive stalled", description: "Distinguish a drive failure from a path or CLIM issue using safe checks.", difficulty: "Intermediate", duration: "12 min" },
  { id: "pathway_no_server", title: "Pathway: no server available", description: "Connect application availability to server-class process state.", difficulty: "Intermediate", duration: "10 min" },
  { id: "cpu_down", title: "CPU down and takeover", description: "Review takeover evidence without confusing correlation with root cause.", difficulty: "Advanced", duration: "15 min" },
];

function SimulatorPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const [running, setRunning] = useState<ScenarioName | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const start = async (scenario: ScenarioName) => {
    setRunning(scenario); setStatus("Preparing synthetic evidence...");
    try { const result = await api.runScenario({ scenario, speed: 10 }); setStatus(`Scenario ${result.status}. Open the AI Assistant to begin.`); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Scenario failed to start"); setRunning(null); }
  };
  return (
    <div>
      <SectionTitle title="Training simulator" description="Practise evidence-based investigation without touching production." />
      <p className="mb-4 border-l-2 border-accent pl-3 text-xs leading-5 text-muted"><strong className="font-medium text-fg">Training data only.</strong> Every event, command, person and outcome here is fictional demo data.</p>
      <ul className="divide-y divide-line border-y border-line">{SCENARIOS.map((scenario, index) => <li key={scenario.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3"><span className="num w-6 text-xs text-muted">{index + 1}</span><div className="min-w-[240px] flex-1"><h3 className="text-sm font-semibold">{scenario.title}</h3><p className="mt-0.5 text-[13px] text-muted">{scenario.description}</p></div><span className="num text-xs text-muted">{scenario.difficulty} · {scenario.duration}</span><button type="button" className="btn" disabled={running === scenario.id} onClick={() => void start(scenario.id)}>{running === scenario.id ? "Running" : "Start"}</button></li>)}</ul>
      {status && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-l-2 border-ok pl-3 text-sm" role="status"><span>{status}</span>{running && <button type="button" className="btn" onClick={() => onNavigate("assistant")}>Open AI Assistant</button>}</div>}
    </div>
  );
}

function WorkspaceShell() {
  const { session, sessionError } = useConsole();
  const [page, setPage] = useState<PageId>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const { data: alerts } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const alertCount = alerts?.length ?? 0;
  const liveNow = liveGroups();
  const live = ["knowledge", "graph", ...liveNow].join(" · ");
  const demo = [...(ALERTS_ARE_MOCK ? ["alerts"] : []), ...GROUPS.filter((g) => !liveNow.includes(g))].join(" · ");
  const navigate = (next: PageId) => { setPage(next); setMobileOpen(false); };
  const current = NAV.find((item) => item.id === page)?.label ?? "Overview";

  return (
    <div className="flex h-screen min-w-0 bg-bg text-fg">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-56 flex-col border-r border-line bg-panel transition-transform lg:static lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-12 items-center gap-2 border-b border-line px-4"><p className="font-semibold tracking-tight">CAIL</p><p className="text-xs text-muted">Operations Assistant</p><button type="button" className="ml-auto p-1 text-muted lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button></div>
        <nav className="flex-1 py-3" aria-label="Primary navigation">{NAV.map((item) => { const Icon = item.icon; const active = page === item.id; return <button key={item.id} type="button" aria-current={active ? "page" : undefined} className={`flex w-full items-center gap-2.5 border-l-2 px-4 py-2 text-left text-[13px] ${active ? "border-accent font-semibold text-fg" : "border-transparent text-muted hover:text-fg"}`} onClick={() => navigate(item.id)}><Icon size={15} aria-hidden="true" className={active ? "text-accent" : ""} />{item.label}{item.id === "investigations" && alertCount > 0 && <span className="num ml-auto text-xs font-semibold text-crit">{alertCount}<span className="sr-only"> {ALERTS_ARE_MOCK ? "demo " : ""}alerts</span></span>}</button>; })}</nav>
        <div className="border-t border-line px-4 py-3 text-[11.5px] leading-4 text-muted"><p><strong className="font-medium text-fg">Advisory mode.</strong> No production execution or credentials.</p><p className="mt-2">CAIL Catalyst 2026 prototype</p></div>
      </aside>
      {mobileOpen && <button className="fixed inset-0 z-30 bg-black/30 lg:hidden" aria-label="Close navigation backdrop" onClick={() => setMobileOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-panel px-4 sm:px-6">
          <button type="button" className="btn px-2 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={17} /></button>
          <div className="hidden min-w-0 flex-1 sm:block"><label className="relative block max-w-md"><Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="field h-8 w-full pl-8" placeholder="Search systems, investigations, knowledge" aria-label="Global search" /></label></div>
          <div className="ml-auto flex items-center gap-3"><span className="hidden text-xs text-warn md:inline">Demo mode</span><NodeSwitcher /><ThemeToggle /><button type="button" className="btn h-8 w-8 px-0" aria-label="Help"><CircleHelp size={15} /></button></div>
        </header>
        <div className="flex h-7 shrink-0 items-center gap-2 border-b border-line bg-panel2 px-4 text-[11.5px] text-muted sm:px-6"><span className="font-medium text-fg">Synthetic data</span><span className="hidden sm:inline">· no production infrastructure connected · suggestions are advisory</span><span className="num ml-auto hidden text-[11px] lg:inline">live: {live}{demo ? ` | demo: ${demo}` : ""}</span></div>
        <main className="scroll min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto min-h-full max-w-[1500px] p-4 sm:p-6 lg:px-8 lg:py-6">
            {sessionError && <div role="alert" className="mb-4 border-l-2 border-crit pl-3 text-sm text-crit"><TriangleAlert className="mr-2 inline" size={15} aria-hidden="true" />Session unavailable: {sessionError}</div>}
            {!session && !sessionError && <p className="text-sm text-muted">Connecting to the simulated session...</p>}
            <div className="mb-4 flex items-center gap-2 text-xs text-muted lg:hidden"><span>CAIL</span><ChevronRight size={12} /><span>{current}</span></div>
            {page === "overview" && <OverviewPage onNavigate={navigate} />}
            {page === "systems" && <SystemsPage onNavigate={navigate} />}
            {page === "investigations" && <InvestigationsPage onNavigate={navigate} />}
            {page === "assistant" && <AssistantPage />}
            {page === "knowledge" && <KnowledgePage />}
            {page === "simulator" && <SimulatorPage onNavigate={navigate} />}
            {page === "graph" && <KnowledgeGraphPage />}
            {page === "learning" && <LearningPage />}
          </div>
        </main>
      </div>
      <SourceDialog />
    </div>
  );
}

export function OperationsWorkspace() {
  return <ConsoleProvider><WorkspaceShell /></ConsoleProvider>;
}
