"use client";

import {
  Activity,
  BellRing,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FileCheck2,
  FlaskConical,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  Menu,
  Network,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import { useState } from "react";
import { ALERTS_ARE_MOCK, GROUPS, api, liveGroups } from "@/lib/api";
import { admin, subName } from "@/lib/admin";
import { fmtTime } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { ConsoleProvider, useConsole } from "@/lib/store";
import type { MetricsResponse, ScenarioName } from "@/lib/types";
import { AlertsPanel } from "./AlertsPanel";
import { ChatPane } from "./ChatPane";
import { KnowledgeGraphPage, useGraph } from "./KnowledgeGraphPage";
import { NodeSwitcher } from "./NodeSwitcher";
import { SourceDialog } from "./SourceDialog";
import { Sparkline } from "./Sparkline";
import { ThemeToggle } from "./ThemeToggle";

type PageId = "overview" | "systems" | "investigations" | "assistant" | "knowledge" | "simulator" | "graph";

const NAV: Array<{ id: PageId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "systems", label: "Systems", icon: Server },
  { id: "investigations", label: "Investigations", icon: BellRing },
  { id: "assistant", label: "AI Assistant", icon: Bot },
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "simulator", label: "Training Simulator", icon: GraduationCap },
  { id: "graph", label: "Knowledge graph", icon: Network },
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

function SectionTitle({ eyebrow, title, description }: { eyebrow?: string; title: string; description: string }) {
  return (
    <header className="mb-6">
      {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-accent">{eyebrow}</p>}
      <h2 className="text-2xl font-semibold tracking-tight text-fg">{title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
    </header>
  );
}

function MetricCard({ label, value, note, tone = "neutral" }: { label: string; value: string; note: string; tone?: "neutral" | "ok" | "warn" | "crit" }) {
  const iconTone = tone === "ok" ? "text-ok bg-ok/10" : tone === "warn" ? "text-warn bg-warn/10" : tone === "crit" ? "text-crit bg-crit/10" : "text-accent bg-accent/10";
  return (
    <article className="rounded-2xl border border-line bg-panel p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
        </div>
        <span className={`rounded-xl p-2 ${iconTone}`}><Activity size={18} aria-hidden="true" /></span>
      </div>
      <p className="mt-3 text-xs text-muted">{note}</p>
    </article>
  );
}

function HealthCharts({ metrics: { data, error, loading } }: { metrics: ReturnType<typeof useNodeMetrics> }) {
  const { session } = useConsole();

  return (
    <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">System health</h3>
          <p className="mt-0.5 text-xs text-muted">Live operational indicators for {session?.node_display ?? "the selected node"}</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/10 px-2.5 py-1 text-xs font-medium text-ok">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" /> Simulator feed
        </span>
      </div>
      {error && <p role="alert" className="mb-3 text-xs text-crit">Metrics unavailable. Retrying automatically.</p>}
      <div className="grid gap-4 md:grid-cols-3">
        {METRICS.map((metric) => {
          const values = data?.series.find((series) => series.metric === metric.id)?.points.map((point) => point[1]) ?? [];
          const current = values.at(-1);
          const over = current !== undefined && current >= metric.threshold;
          const near = current !== undefined && current >= metric.threshold * 0.75;
          const color = over ? "rgb(var(--crit))" : near ? "rgb(var(--warn))" : "rgb(var(--ok))";
          return (
            <article key={metric.id} className="rounded-xl border border-line bg-panel2/50 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-medium text-muted">{metric.label}</p>
                  <p className="mt-1 text-xl font-semibold" style={{ color }}>
                    {current === undefined ? (loading ? "..." : "n/a") : `${Math.round(current)}${metric.unit}`}
                  </p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${over ? "bg-crit/10 text-crit" : near ? "bg-warn/10 text-warn" : "bg-ok/10 text-ok"}`}>
                  {over ? "Critical" : near ? "Watch" : "Normal"}
                </span>
              </div>
              <div className="mt-2 h-12">{values.length > 1 && <Sparkline values={values} threshold={metric.threshold} color={color} />}</div>
              <p className="mt-1 text-[11px] text-muted">Limit {metric.threshold}{metric.unit.trim()}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

const SEVERITY_CHIP = { critical: ["status-critical", "Critical"], warning: ["status-warning", "Warning"], info: ["status-healthy", "Info"] } as const;

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
      <SectionTitle title="Operations overview" description="Understand the state of monitored systems, find what needs attention, and begin an evidence-backed investigation." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Nodes monitored" value={session ? String(session.nodes_available.length) : "..."} note={session ? session.nodes_available.map((n) => n.display).join(" and ") : "Connecting"} />
        <MetricCard label="Subsystems in knowledge graph" value={subsystems === undefined ? "..." : String(subsystems)} note={graph.error ? "Graph unavailable" : "From the live knowledge graph"} />
        <MetricCard label="Healthy indicators" value={withData.length ? `${healthy} of ${withData.length}` : "n/a"} note={`Under limit on ${session?.node_display ?? "the node"}, simulator metrics`} tone={withData.length && healthy < withData.length ? "warn" : "ok"} />
        <MetricCard label={`Active alerts${demo}`} value={String(list.length)} note={ALERTS_ARE_MOCK ? "Scripted demo alerts; the watcher is not built yet" : "From the watcher"} tone={list.length ? "crit" : "ok"} />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.75fr)]">
        <HealthCharts metrics={metrics} />
        <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="rounded-xl bg-accent/10 p-2 text-accent"><Sparkles size={18} aria-hidden="true" /></span>
            <div>
              <h3 className="font-semibold">AI operational summary</h3>
              <p className="text-xs text-muted">{ALERTS_ARE_MOCK ? "From watcher (demo alerts)" : "From watcher"}</p>
            </div>
          </div>
          {top ? (
            <>
              <p className="mt-5 text-sm leading-6">{top.message}</p>
              <p className="mt-3 text-xs leading-5 text-muted">Pattern owner: {top.owner_name} &bull; expected lead time {top.lead_time_min} min &bull; {top.node} &bull; {subName(top.subsystem)}</p>
            </>
          ) : (
            <p className="mt-5 text-sm leading-6">No active warnings.</p>
          )}
          <button type="button" className="btn btn-primary mt-4 w-full" onClick={() => onNavigate("assistant")}>Investigate with AI <ChevronRight size={14} /></button>
        </section>
      </div>

      <section className="mt-5 overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <h3 className="font-semibold">Needs attention{demo}</h3>
            <p className="text-xs text-muted">Watcher alerts, most recent first</p>
          </div>
          <button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("investigations")}>View investigations</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-panel2/70 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">System</th><th className="px-4 py-3 font-medium">Health</th><th className="px-4 py-3 font-medium">Observation</th><th className="px-4 py-3 font-medium">Source</th><th className="px-5 py-3 font-medium">Updated</th></tr></thead>
            <tbody className="divide-y divide-line">
              {list.length === 0 && <tr><td colSpan={5} className="px-5 py-4 text-muted">No active warnings.</td></tr>}
              {list.map((a) => {
                const [cls, label] = SEVERITY_CHIP[a.severity];
                return (
                  <tr key={a.id} className="hover:bg-panel2/40"><td className="px-5 py-4 font-medium">{a.node} &bull; {subName(a.subsystem)}</td><td className="px-4 py-4"><span className={`status-chip ${cls}`}>{label}</span></td><td className="px-4 py-4">{a.message}</td><td className="px-4 py-4 text-muted">{ALERTS_ARE_MOCK ? "Watcher (demo alert)" : "Watcher"}</td><td className="px-5 py-4 text-muted">{fmtTime(a.ts)}</td></tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
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
      <SectionTitle title="Systems" description="Every node and subsystem in the knowledge graph, with the veteran notes and manual sections that apply, and live metrics where the simulator provides them." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="relative min-w-[260px] flex-1 sm:max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} /><input className="field h-10 w-full rounded-xl bg-panel pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems" aria-label="Search systems" /></label>
        <span className="text-xs text-muted">{rows.length} node and subsystem rows &bull; from the knowledge graph</span>
      </div>
      {graph.error && <p role="alert" className="mb-3 text-sm text-crit">Graph unavailable: {graph.error}</p>}
      <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr>{["Node", "Subsystem", "Veteran notes in scope", "Manual sections", "Live metrics", ""].map((head) => <th key={head} className="px-5 py-3 font-medium">{head}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">{rows.map((r) => <tr key={r.key} className="hover:bg-panel2/40"><td className="px-5 py-4 font-medium">{r.node}</td><td className="px-5 py-4">{r.sub}</td><td className="px-5 py-4 text-muted">{r.notes}</td><td className="px-5 py-4 text-muted">{r.sections}</td><td className="px-5 py-4 text-muted">{r.live}</td><td className="px-5 py-4 text-right"><button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("assistant")}>Investigate</button></td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function InvestigationsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  return (
    <div>
      <SectionTitle title="Investigations" description="Review alerts as evidence-backed investigations. Observations, hypotheses, and unknowns remain visibly separate." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
        <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
          <div className="border-b border-line px-5 py-4"><h3 className="font-semibold">Active watcher alerts</h3><p className="text-xs text-muted">Correlated patterns requiring operator attention</p></div>
          <AlertsPanel />
        </section>
        <aside className="space-y-4">
          <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Investigation discipline</p>
            <ul className="mt-4 space-y-4 text-sm">
              <li className="flex gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-ok" size={17} /><span><strong className="block">Confirmed facts</strong><span className="text-muted">Directly linked to source records.</span></span></li>
              <li className="flex gap-3"><CircleHelp className="mt-0.5 shrink-0 text-warn" size={17} /><span><strong className="block">Possible explanations</strong><span className="text-muted">Clearly marked as unverified.</span></span></li>
              <li className="flex gap-3"><ShieldCheck className="mt-0.5 shrink-0 text-accent" size={17} /><span><strong className="block">Controlled next steps</strong><span className="text-muted">Allowlisted and human reviewed.</span></span></li>
            </ul>
          </section>
          <button type="button" className="btn btn-primary w-full py-2.5" onClick={() => onNavigate("assistant")}><Bot size={16} /> Open AI investigation</button>
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
      <SectionTitle eyebrow="Advisory only" title="AI troubleshooting assistant" description="Ask questions in everyday language. CAIL grounds each answer in approved knowledge and scoped operational evidence." />
      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_340px]">
        <section className="flex min-h-[570px] flex-col overflow-hidden rounded-2xl border border-line bg-panel shadow-sm"><ChatPane /></section>
        <aside className="space-y-4">
          <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
            <div className="flex items-center gap-2"><Database size={17} className="text-accent" /><h3 className="font-semibold">Investigation context</h3></div>
            <dl className="mt-4 space-y-3 text-sm"><div><dt className="text-xs text-muted">Selected system</dt><dd className="mt-0.5 font-medium">{session?.node_display ?? "..."}</dd></div><div><dt className="text-xs text-muted">Top alert{ALERTS_ARE_MOCK ? " (demo)" : ""}</dt><dd className="mt-0.5 font-medium">{top ? `${subName(top.subsystem)} • ${top.severity}` : "None"}</dd></div><div><dt className="text-xs text-muted">Evidence window</dt><dd className="mt-0.5 font-medium">Last 60 minutes</dd></div></dl>
          </section>
          <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
            <h3 className="font-semibold">How to read an answer</h3>
            <ul className="mt-4 space-y-3 text-sm text-muted"><li className="flex gap-2"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-ok" />Facts have source citations.</li><li className="flex gap-2"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-warn" />Uncertainty is stated explicitly.</li><li className="flex gap-2"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" />Commands require review and guards.</li></ul>
          </section>
          <section className="rounded-2xl border border-warn/30 bg-warn/8 p-4 text-sm"><p className="font-medium text-warn">No production execution</p><p className="mt-1 text-xs leading-5 text-muted">All command output in this prototype is simulated and retained only as investigation evidence.</p></section>
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
      <SectionTitle title="Knowledge" description="Manuals and signed expert notes the assistant answers from. This list is live from the database." />
      <div className="mb-4 flex flex-wrap items-center gap-2">{(["all", "manuals", "expert"] as const).map((item) => <button key={item} type="button" className={`rounded-full border px-4 py-2 text-sm font-medium ${filter === item ? "border-accent bg-accent/10 text-accent" : "border-line bg-panel text-muted hover:text-fg"}`} onClick={() => setFilter(item)}>{item === "all" ? "All knowledge" : item === "manuals" ? "Manuals & runbooks" : "Expert knowledge"}</button>)}
        <span className="ml-auto flex gap-2"><a className="btn" href="/knowledge">Add knowledge / sign-off</a><a className="btn" href="/documents">Add document</a></span>
      </div>
      {err && <p role="alert" className="mb-3 text-sm text-crit">Knowledge unavailable: {err}</p>}
      <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">Name</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 font-medium">Applicable scope</th><th className="px-4 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Review</th></tr></thead><tbody className="divide-y divide-line">{visible.map((entry) => <tr key={entry.id} className="hover:bg-panel2/40"><td className="max-w-md px-5 py-4"><p className="font-medium">{entry.name}</p><p className="mt-1 truncate text-xs text-muted">{entry.detail}</p></td><td className="px-4 py-4 text-muted">{entry.type}</td><td className="px-4 py-4 text-muted">{entry.scope}</td><td className="px-4 py-4"><span className="status-chip status-healthy"><FileCheck2 size={12} />{entry.status}</span></td><td className="px-5 py-4">{entry.warn ? <span className="status-chip status-warning">{entry.review}</span> : <span className="text-muted">{entry.review}</span>}</td></tr>)}</tbody></table></div>
      </section>
      <p className="mt-4 text-xs text-muted">New notes stay drafts until their owner signs them on the Add knowledge page; only signed notes appear here and in answers.</p>
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
      <SectionTitle eyebrow="Synthetic environment" title="Operator training simulator" description="Practice evidence-based investigation and safe decision-making without connecting to production infrastructure." />
      <div className="mb-5 flex items-center gap-3 rounded-2xl border border-accent/25 bg-accent/8 p-4 text-sm"><FlaskConical className="shrink-0 text-accent" size={20} /><div><p className="font-medium">Training data only</p><p className="text-xs text-muted">Every event, command, person, and outcome in this area is fictional demo data.</p></div></div>
      <div className="grid gap-4 md:grid-cols-2">{SCENARIOS.map((scenario, index) => <article key={scenario.id} className="rounded-2xl border border-line bg-panel p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><span className="rounded-xl bg-accent/10 p-2.5 text-accent"><GraduationCap size={20} /></span><span className="rounded-full bg-panel2 px-2.5 py-1 text-xs text-muted">Scenario {index + 1}</span></div><h3 className="mt-4 text-lg font-semibold">{scenario.title}</h3><p className="mt-2 min-h-10 text-sm leading-5 text-muted">{scenario.description}</p><div className="mt-4 flex items-center gap-4 text-xs text-muted"><span className="inline-flex items-center gap-1"><Gauge size={13} />{scenario.difficulty}</span><span className="inline-flex items-center gap-1"><Clock3 size={13} />{scenario.duration}</span></div><button type="button" className="btn btn-primary mt-5 w-full py-2" disabled={running === scenario.id} onClick={() => void start(scenario.id)}>{running === scenario.id ? "Scenario running" : "Start scenario"}</button></article>)}</div>
      {status && <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ok/30 bg-ok/8 p-4 text-sm" role="status"><span className="inline-flex items-center gap-2"><CheckCircle2 size={17} className="text-ok" />{status}</span>{running && <button type="button" className="btn" onClick={() => onNavigate("assistant")}>Open AI Assistant</button>}</div>}
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
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-panel transition-transform lg:static lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-16 items-center gap-3 border-b border-line px-5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-sm font-bold text-white">C</span><div><p className="font-semibold leading-tight">CAIL</p><p className="text-[11px] text-muted">Operations Assistant</p></div><button type="button" className="ml-auto p-1 text-muted lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button></div>
        <nav className="flex-1 space-y-1 p-3" aria-label="Primary navigation">{NAV.map((item) => { const Icon = item.icon; const active = page === item.id; return <button key={item.id} type="button" className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors ${active ? "bg-accent/10 text-accent" : "text-muted hover:bg-panel2 hover:text-fg"}`} onClick={() => navigate(item.id)}><Icon size={18} aria-hidden="true" />{item.label}{item.id === "investigations" && alertCount > 0 && <span className="ml-auto rounded-full bg-crit/10 px-2 py-0.5 text-[11px] text-crit">{alertCount}<span className="sr-only"> {ALERTS_ARE_MOCK ? "demo " : ""}alerts</span></span>}</button>; })}</nav>
        <div className="border-t border-line p-4"><div className="rounded-xl bg-panel2 p-3"><p className="flex items-center gap-2 text-xs font-medium"><ShieldCheck size={14} className="text-ok" />Advisory mode</p><p className="mt-1 text-[11px] leading-4 text-muted">No production execution or credentials.</p></div><p className="mt-3 text-[10px] text-muted">CAIL Catalyst 2026 prototype</p></div>
      </aside>
      {mobileOpen && <button className="fixed inset-0 z-30 bg-black/30 lg:hidden" aria-label="Close navigation backdrop" onClick={() => setMobileOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-panel px-4 sm:px-6">
          <button type="button" className="btn px-2 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={17} /></button>
          <div className="hidden min-w-0 flex-1 sm:block"><label className="relative block max-w-xl"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="field h-10 w-full rounded-xl bg-panel2 pl-9" placeholder="Search systems, investigations, and knowledge" aria-label="Global search" /></label></div>
          <div className="ml-auto flex items-center gap-2"><span className="hidden rounded-full border border-warn/30 bg-warn/8 px-3 py-1.5 text-xs font-medium text-warn md:inline-flex">Demo mode</span><NodeSwitcher /><ThemeToggle /><button type="button" className="btn h-9 w-9 rounded-full px-0" aria-label="Help"><CircleHelp size={16} /></button></div>
        </header>
        <div className="flex min-h-10 shrink-0 items-center gap-2 border-b border-accent/20 bg-accent/7 px-4 text-xs text-muted sm:px-6"><FlaskConical size={14} className="text-accent" /><strong className="text-fg">Synthetic data</strong><span className="hidden sm:inline">• No production infrastructure connected • Suggestions are advisory</span><span className="ml-auto hidden text-[11px] lg:inline">Live: {live}{demo ? ` — Demo: ${demo}` : ""}</span></div>
        <main className="scroll min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto min-h-full max-w-[1500px] p-4 sm:p-6 lg:p-8">
            {sessionError && <div role="alert" className="mb-4 rounded-xl border border-crit/30 bg-crit/8 p-3 text-sm text-crit"><TriangleAlert className="mr-2 inline" size={16} />Session unavailable: {sessionError}</div>}
            {!session && !sessionError && <p className="text-sm text-muted">Connecting to the simulated session...</p>}
            <div className="mb-4 flex items-center gap-2 text-xs text-muted lg:hidden"><span>CAIL</span><ChevronRight size={12} /><span>{current}</span></div>
            {page === "overview" && <OverviewPage onNavigate={navigate} />}
            {page === "systems" && <SystemsPage onNavigate={navigate} />}
            {page === "investigations" && <InvestigationsPage onNavigate={navigate} />}
            {page === "assistant" && <AssistantPage />}
            {page === "knowledge" && <KnowledgePage />}
            {page === "simulator" && <SimulatorPage onNavigate={navigate} />}
            {page === "graph" && <KnowledgeGraphPage />}
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
