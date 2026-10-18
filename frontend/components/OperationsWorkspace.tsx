"use client";

import {
  Activity,
  BellRing,
  BookOpen,
  Bot,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  GraduationCap,
  LayoutDashboard,
  Lightbulb,
  ListChecks,
  Map,
  Menu,
  Network,
  Search,
  Server,
  TriangleAlert,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { ALERTS_ARE_MOCK, api } from "@/lib/api";
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
import { NodeBadge } from "./NodeBadge";
import { Sparkline } from "./Sparkline";
import { ThemeToggle } from "./ThemeToggle";
import { CountUp, PageHeader, Panel, Skeleton, StatCard, SubPill, hueStyle, type Hue } from "./ui";
import { WhoAmI } from "./WhoAmI";
import { IntegrationsPanel } from "./IntegrationsPanel";
import { useMe } from "@/lib/me";

type PageId = "overview" | "systems" | "investigations" | "assistant" | "knowledge" | "simulator" | "graph" | "learning";

const NAV: Array<{ id: PageId; label: string; icon: typeof LayoutDashboard; hue: Hue }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, hue: "sky" },
  { id: "investigations", label: "Alerts", icon: BellRing, hue: "amber" },
  { id: "systems", label: "Systems", icon: Server, hue: "teal" },
  { id: "assistant", label: "AI Assistant", icon: Bot, hue: "indigo" },
  { id: "simulator", label: "Training Simulator", icon: GraduationCap, hue: "rose" },
  { id: "graph", label: "Synapse", icon: Network, hue: "violet" },
  { id: "learning", label: "Learning map", icon: Map, hue: "sky" },
  { id: "knowledge", label: "Knowledge", icon: BookOpen, hue: "green" },
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

const PAGE_ICON = Object.fromEntries(NAV.map((n) => [n.id, n.icon])) as Record<PageId, typeof LayoutDashboard>;

function SectionTitle({ page, title, description, aside }: { page: PageId; title: string; description?: ReactNode; aside?: ReactNode }) {
  const Icon = PAGE_ICON[page];
  return <PageHeader title={title} description={description} icon={<Icon size={18} aria-hidden="true" />} aside={aside} />;
}

/** A titled card. */
function Block({ title, aside, children, className = "" }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return <Panel title={title} aside={aside} className={className}>{children}</Panel>;
}

/** Watcher status: pulses while it is answering. */
function WatcherStatus({ error }: { error: string | null }) {
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${error ? "border-crit/40 bg-crit/10 text-crit" : "border-ok/35 bg-ok/10 text-ok"}`}>
      <span className="live-dot" aria-hidden="true" />
      {error ? "Watcher unreachable" : "Watcher running"}
    </span>
  );
}

function HealthCharts({ metrics: { data, error, loading } }: { metrics: ReturnType<typeof useNodeMetrics> }) {
  const { session } = useConsole();

  return (
    <Block title="System health" aside={<>{session?.node_display ?? "selected node"} · simulator feed</>}>
      {error && <p role="alert" className="mb-3 text-xs text-crit">Metrics unavailable. Retrying automatically.</p>}
      <div className="stagger grid gap-3 md:grid-cols-3">
        {METRICS.map((metric) => {
          const values = data?.series.find((series) => series.metric === metric.id)?.points.map((point) => point[1]) ?? [];
          const current = values.at(-1);
          const over = current !== undefined && current >= metric.threshold;
          const near = current !== undefined && current >= metric.threshold * 0.75;
          const color = over ? "rgb(var(--crit))" : near ? "rgb(var(--warn))" : "rgb(var(--ok))";
          const hue: Hue = over ? "crit" : near ? "amber" : "green";
          return (
            <article key={metric.id} className="tint lift flex min-w-0 flex-col rounded-xl border p-3" style={hueStyle(hue)}>
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-xs font-semibold text-muted">{metric.label}</p>
                <span className={`status-chip ${over ? "status-critical" : near ? "status-warning" : "status-healthy"}`}>{over ? "Critical" : near ? "Watch" : "Normal"}</span>
              </div>
              <p className="mt-0.5 font-display text-3xl font-semibold leading-tight" style={{ color }}>
                {current === undefined ? (loading ? <Skeleton className="h-7 w-16" /> : "n/a") : <CountUp value={Math.round(current)} suffix={metric.unit} />}
              </p>
              <div className="mt-2 h-20">{values.length > 1 && <Sparkline values={values} threshold={metric.threshold} color={color} />}</div>
              <p className="num mt-1 text-[11px] text-muted">limit {metric.threshold}{metric.unit.trim()}</p>
            </article>
          );
        })}
      </div>
    </Block>
  );
}

const SEVERITY_CHIP = { critical: ["status-critical", "Critical"], warning: ["status-warning", "Warning"], info: ["status-healthy", "Info"] } as const;

const TH = "px-4 py-2.5 font-semibold";
const TD = "px-4 py-2.5";
const THEAD = "bg-skysoft/60 text-xs text-muted";
const ROW = "transition-colors hover:bg-skysoft/50";

function OverviewPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { session } = useConsole();
  const firstName = useMe().name.split(" ")[0];
  const { data: alerts, error: watchError } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
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
      <SectionTitle page="overview" title={`Good day, ${firstName}`} description="Early warnings, system health and who to call, for the node you are on." aside={<WatcherStatus error={watchError} />} />
      <dl className="stagger grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard hue="sky" icon={<Server size={18} aria-hidden="true" />} label="Nodes monitored"
          value={session ? <CountUp value={session.nodes_available.length} /> : <Skeleton className="h-8 w-10" />}
          note={session ? session.nodes_available.map((n) => n.display).join(", ") : "Connecting"} />
        <StatCard hue="teal" icon={<Network size={18} aria-hidden="true" />} label="Subsystems in graph"
          value={subsystems === undefined ? <Skeleton className="h-8 w-10" /> : <CountUp value={subsystems} />}
          note={graph.error ? "Graph unavailable" : "Live in Synapse"} />
        <StatCard hue={withData.length && healthy < withData.length ? "amber" : "green"} icon={<Activity size={18} aria-hidden="true" />} label="Indicators under limit"
          value={withData.length ? <span><CountUp value={healthy} /> <span className="text-lg font-medium text-muted">of {withData.length}</span></span> : "n/a"}
          note={`${session?.node_display ?? "node"}, simulator metrics`} />
        <StatCard hue={list.length ? "rose" : "sky"} alert={list.length > 0} icon={<BellRing size={18} aria-hidden="true" />} label={`Active alerts${demo}`}
          value={<CountUp value={list.length} />}
          note={ALERTS_ARE_MOCK ? "Scripted demo alerts; watcher not built yet" : "From the watcher"} />
      </dl>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.75fr)]">
        <HealthCharts metrics={metrics} />
        <Block title="Summary" aside={ALERTS_ARE_MOCK ? "watcher, demo alerts" : "watcher"}>
          {top ? (
            <>
              <div className="mb-2 flex flex-wrap items-center gap-2"><NodeBadge display={top.node} /><SubPill name={subName(top.subsystem)} /></div>
              <p className="text-sm font-medium leading-6">{top.message}</p>
              <p className="mt-2 text-xs leading-5 text-muted">{top.owner_name ? `Owner ${top.owner_name}` : ""}{top.owner_name && top.lead_time_min != null ? " · " : ""}{top.lead_time_min != null ? `lead time ${top.lead_time_min} min` : ""}</p>
            </>
          ) : (
            <p className="flex items-center gap-2 text-sm leading-6"><CircleCheck size={18} className="text-ok" aria-hidden="true" />No active warnings.</p>
          )}
          <button type="button" className="btn btn-primary mt-4" onClick={() => onNavigate("assistant")}>Investigate <ChevronRight size={14} aria-hidden="true" /></button>
        </Block>
      </div>

      <Panel className="mt-5" flush title={`Needs attention${demo}`} aside={<button type="button" className="font-semibold text-accent hover:underline" onClick={() => onNavigate("investigations")}>View alerts</button>}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className={THEAD}><tr><th className={TH}>System</th><th className={TH}>Health</th><th className={TH}>Observation</th><th className={TH}>Source</th><th className={TH}>Updated</th></tr></thead>
            <tbody className="divide-y divide-line">
              {list.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-muted">No active warnings.</td></tr>}
              {list.map((a) => {
                const [cls, label] = SEVERITY_CHIP[a.severity];
                return (
                  <tr key={a.id} className={ROW}><td className={TD}><span className="flex flex-wrap items-center gap-1.5"><NodeBadge display={a.node} /><SubPill name={subName(a.subsystem)} /></span></td><td className={TD}><span className={`status-chip ${cls}`}>{label}</span></td><td className={TD}>{a.message}</td><td className={`${TD} text-muted`}>{ALERTS_ARE_MOCK ? "Watcher (demo alert)" : "Watcher"}</td><td className={`${TD} num text-muted`}>{fmtTime(a.ts)}</td></tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
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
      <SectionTitle page="systems" title="Systems" description="Nodes and subsystems from Synapse (the knowledge graph), with the veteran notes and manual sections in scope." />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <label className="relative min-w-[260px] flex-1 sm:max-w-md"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" size={15} aria-hidden="true" /><input className="field h-9 w-full pl-8" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems" aria-label="Search systems" /></label>
        <span className="num text-xs text-muted">{rows.length} rows</span>
      </div>
      {graph.error && <p role="alert" className="mb-3 text-sm text-crit">Graph unavailable: {graph.error}</p>}
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className={THEAD}><tr>{["Node", "Subsystem", "Veteran notes", "Manual sections", "Live metrics", ""].map((head, i) => <th key={i} className={TH}>{head}</th>)}</tr></thead>
          <tbody className="divide-y divide-line">{rows.map((r) => <tr key={r.key} className={ROW}><td className={TD}><NodeBadge display={r.node} /></td><td className={TD}><SubPill name={r.sub} /></td><td className={`${TD} num text-muted`}>{r.notes}</td><td className={`${TD} num text-muted`}>{r.sections}</td><td className={`${TD} text-muted`}>{r.live}</td><td className={`${TD} text-right`}><button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("assistant")}>Investigate</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function InvestigationsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const RULES: Array<{ hue: Hue; icon: typeof CircleCheck; title: string; text: string }> = [
    { hue: "green", icon: CircleCheck, title: "Confirmed facts.", text: "Linked to source records." },
    { hue: "amber", icon: Lightbulb, title: "Possible explanations.", text: "Marked as unverified." },
    { hue: "sky", icon: ListChecks, title: "Next steps.", text: "Allowlisted and human reviewed." },
  ];
  return (
    <div>
      <SectionTitle page="investigations" title="Alerts" description="Early warnings from the watcher, with the evidence, what to do and who to call. Open to everyone; only veterans approve commands." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
        <Block title="Active watcher alerts"><AlertsPanel /></Block>
        <aside className="stagger space-y-4">
          <Block title="Connected monitoring tools"><IntegrationsPanel /></Block>
          <Block title="Ground rules">
            <ul className="space-y-3 text-sm">
              {RULES.map((r) => (
                <li key={r.title} className="flex items-start gap-3" style={hueStyle(r.hue)}>
                  <span className="icon-chip !h-8 !w-8 !rounded-lg"><r.icon size={16} aria-hidden="true" /></span>
                  <p className="pt-1"><strong className="font-semibold">{r.title}</strong> <span className="text-muted">{r.text}</span></p>
                </li>
              ))}
            </ul>
          </Block>
          <button type="button" className="btn btn-primary" onClick={() => onNavigate("assistant")}>Open assistant</button>
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
      <SectionTitle page="assistant" title="Assistant" description={<>Advisory only. Facts carry a source <span className="num rounded-md bg-skysoft px-1 font-semibold text-accent">[n]</span>; uncertainty is stated; commands need review and guards.</>} />
      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_280px]">
        <section className="card flex min-h-[570px] flex-col overflow-hidden rounded-2xl"><ChatPane /></section>
        <aside className="stagger space-y-4">
          <Block title="Context">
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between gap-3"><dt className="text-muted">System</dt><dd><NodeBadge display={session?.node_display ?? "..."} /></dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="text-muted">Top alert{ALERTS_ARE_MOCK ? " (demo)" : ""}</dt><dd className="flex items-center gap-1.5 font-medium">{top ? <><SubPill name={subName(top.subsystem)} /><span>{top.severity}</span></> : "None"}</dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="text-muted">Evidence window</dt><dd className="font-medium">last 60 min</dd></div>
            </dl>
          </Block>
          <p className="rounded-xl border border-warn/30 bg-warn/10 p-3 text-xs leading-5 text-muted"><strong className="font-semibold text-warn">No production execution.</strong> All command output here is simulated and kept only as investigation evidence.</p>
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
      <SectionTitle page="knowledge" title="Knowledge" description="Manuals and signed expert notes the assistant answers from. Live from the database." />
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line">
        <div role="tablist" aria-label="Knowledge filter" className="flex gap-5">
          {(["all", "manuals", "expert"] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={filter === item} className={`tab -mb-px py-2 text-sm font-semibold transition-colors ${filter === item ? "text-head" : "text-muted hover:text-fg"}`} onClick={() => setFilter(item)}>{item === "all" ? "All" : item === "manuals" ? "Manuals & runbooks" : "Expert notes"}</button>)}
        </div>
        <span className="mb-1 ml-auto flex gap-2"><a className="btn" href="/knowledge">Add knowledge / sign-off</a><a className="btn" href="/documents">Add document</a></span>
      </div>
      {err && <p role="alert" className="mb-3 text-sm text-crit">Knowledge unavailable: {err}</p>}
      <div className="card overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className={THEAD}><tr><th className={TH}>Name</th><th className={TH}>Type</th><th className={TH}>Applicable scope</th><th className={TH}>Status</th><th className={TH}>Review</th></tr></thead><tbody className="divide-y divide-line">{visible.map((entry) => <tr key={entry.id} className={ROW}><td className={`${TD} max-w-md`}><p className="font-medium">{entry.name}</p><p className="mt-0.5 truncate text-xs text-muted">{entry.detail}</p></td><td className={TD}><span className="pill" style={hueStyle(entry.type === "Manual" ? "sky" : "amber")}>{entry.type}</span></td><td className={`${TD} text-muted`}>{entry.scope}</td><td className={TD}><span className="status-chip status-healthy">{entry.status}</span></td><td className={TD}>{entry.warn ? <span className="status-chip status-warning">{entry.review}</span> : <span className="text-muted">{entry.review}</span>}</td></tr>)}</tbody></table></div>
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

const LEVEL_HUE: Record<string, Hue> = { Beginner: "green", Intermediate: "sky", Advanced: "rose" };

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
      <SectionTitle page="simulator" title="Training simulator" description="Practise evidence-based investigation without touching production." />
      <p className="mb-4 rounded-xl border border-sky/30 bg-skysoft p-3 text-xs leading-5 text-muted"><strong className="font-semibold text-head">Training data only.</strong> Every event, command, person and outcome here is fictional demo data.</p>
      <ul className="stagger grid gap-4 md:grid-cols-2">{SCENARIOS.map((scenario, index) => (
        <li key={scenario.id} className="tint lift flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl border p-4 shadow-soft" style={hueStyle(LEVEL_HUE[scenario.difficulty] ?? "sky")}>
          <span className="icon-chip num text-sm font-bold">{index + 1}</span>
          <div className="min-w-[200px] flex-1"><h3 className="text-[15px] font-semibold text-head">{scenario.title}</h3><p className="mt-0.5 text-[13px] text-muted">{scenario.description}</p><p className="mt-2 flex items-center gap-2"><span className="pill">{scenario.difficulty}</span><span className="num text-xs text-muted">{scenario.duration}</span></p></div>
          <button type="button" className="btn btn-primary" disabled={running === scenario.id} onClick={() => void start(scenario.id)}>{running === scenario.id ? "Running" : "Start"}</button>
        </li>
      ))}</ul>
      {status && <div className="rise mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok/30 bg-ok/10 p-3 text-sm" role="status"><span className="flex items-center gap-2"><span className="live-dot text-ok" aria-hidden="true" />{status}</span>{running && <button type="button" className="btn" onClick={() => onNavigate("assistant")}>Open AI Assistant</button>}</div>}
    </div>
  );
}

function WorkspaceShell() {
  const { session, sessionError } = useConsole();
  const [page, setPage] = useState<PageId>("overview");
  const [focus, setFocus] = useState<string | undefined>(undefined);
  // deep link: /?page=graph&focus=<node id>
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const p = q.get("page");
    if (p && NAV.some((n) => n.id === p)) setPage(p as PageId);
    setFocus(q.get("focus") ?? undefined);
  }, []);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const { data: alerts, error: watchError } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const alertCount = alerts?.length ?? 0;
  const navigate = (next: PageId) => { setPage(next); setFocus(undefined); setMobileOpen(false); };
  const current = NAV.find((item) => item.id === page)?.label ?? "Overview";

  return (
    <div className="flex h-screen min-w-0 bg-bg text-fg">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col bg-gradient-to-b from-navy via-navy to-navy2 text-white shadow-lift transition-transform lg:static lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="relative flex h-[60px] items-center gap-3 px-4">
          {/* eslint-disable-next-line @next/next/no-img-element -- small static logo, no optimisation needed */}
          <img src="/logo.png" alt="" aria-hidden="true" width={40} height={40} className="h-10 w-10 shrink-0 rounded-full bg-white p-0.5 shadow-soft" />
          <div className="leading-tight"><p className="font-display text-lg font-bold tracking-tight">CAIL</p><p className="text-[11.5px] text-white/75">Operations Assistant</p></div>
          <button type="button" className="ml-auto rounded-md p-1 text-white/80 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
          <span aria-hidden="true" className="flow-band absolute inset-x-0 bottom-0 h-[3px]" />
        </div>
        <nav className="stagger flex-1 space-y-0.5 px-3 py-4" aria-label="Primary navigation">{NAV.map((item) => {
          const Icon = item.icon; const active = page === item.id;
          return (
            <button key={item.id} type="button" aria-current={active ? "page" : undefined} style={hueStyle(item.hue)}
              className={`group flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-[13.5px] transition-all duration-200 ${active ? "bg-white/18 font-semibold text-white shadow-soft" : "text-white/80 hover:translate-x-0.5 hover:bg-white/10 hover:text-white"}`}
              onClick={() => navigate(item.id)}>
              <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${active ? "bg-white" : "bg-[rgb(var(--c)/0.3)]"}`} style={{ color: active ? `rgb(var(--navy))` : "color-mix(in srgb, rgb(var(--c)) 40%, white)" }}><Icon size={15} aria-hidden="true" /></span>
              {item.label}
              {item.id === "investigations" && alertCount > 0 && <span className="num ml-auto inline-flex items-center gap-1.5 rounded-full bg-crit px-2 py-0.5 text-xs font-bold text-white"><span className="live-dot !h-1.5 !w-1.5 text-white" aria-hidden="true" />{alertCount}<span className="sr-only"> {ALERTS_ARE_MOCK ? "demo " : ""}alerts</span></span>}
            </button>
          );
        })}</nav>
        <div className="m-3 rounded-xl bg-white/10 p-3 text-[11.5px] leading-4 text-white/80">
          <p className="mb-2 flex items-center gap-2 font-semibold text-white"><span className={`live-dot ${watchError ? "text-[#ff9aa2]" : "text-[#5ce0a8]"}`} aria-hidden="true" />{watchError ? "Watcher unreachable" : "Watcher running"}</p>
          <p><strong className="font-semibold text-white">Advisory mode.</strong> No production execution or credentials.</p>
          <p className="mt-2 text-white/65">CAIL Catalyst 2026 prototype</p>
        </div>
      </aside>
      {mobileOpen && <button className="fixed inset-0 z-30 bg-navy/40 lg:hidden" aria-label="Close navigation backdrop" onClick={() => setMobileOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative z-40 flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-panel/95 px-4 backdrop-blur sm:px-6">
          <span aria-hidden="true" className="flow-band absolute inset-x-0 top-0 h-[3px]" />
          <button type="button" className="btn px-2 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={17} /></button>
          <div className="hidden min-w-0 flex-1 sm:block"><label className="relative block max-w-md"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="field h-9 w-full rounded-full bg-skysoft/60 pl-9" placeholder="Search systems, alerts, knowledge" aria-label="Global search" /></label></div>
          <div className="ml-auto flex items-center gap-3"><WhoAmI onNewJunior={() => navigate("learning")} /><NodeSwitcher /><ThemeToggle /><button type="button" className="btn h-8 w-8 px-0" aria-label="Help"><CircleHelp size={15} /></button></div>
        </header>
        <main className="scroll sparkle-bg min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto min-h-full max-w-[1500px] p-4 sm:p-6 lg:px-8 lg:py-6">
            {sessionError && <div role="alert" className="mb-4 rounded-xl border border-crit/30 bg-crit/10 p-3 text-sm text-crit"><TriangleAlert className="mr-2 inline" size={15} aria-hidden="true" />Session unavailable: {sessionError}</div>}
            {!session && !sessionError && <p className="text-sm text-muted">Connecting to the simulated session...</p>}
            <div className="mb-4 flex items-center gap-2 text-xs text-muted lg:hidden"><span>CAIL</span><ChevronRight size={12} /><span>{current}</span></div>
            <div key={page} className="rise h-full">
              {page === "overview" && <OverviewPage onNavigate={navigate} />}
              {page === "systems" && <SystemsPage onNavigate={navigate} />}
              {page === "investigations" && <InvestigationsPage onNavigate={navigate} />}
              {page === "assistant" && <AssistantPage />}
              {page === "knowledge" && <KnowledgePage />}
              {page === "simulator" && <SimulatorPage onNavigate={navigate} />}
              {page === "graph" && <KnowledgeGraphPage focus={focus} />}
              {page === "learning" && <LearningPage />}
            </div>
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
