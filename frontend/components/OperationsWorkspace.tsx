"use client";

import {
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FileCheck2,
  FlaskConical,
  Gauge,
  Menu,
  Search,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api, USE_MOCKS } from "@/lib/api";
import { environmentName, humanizeEnvironmentText } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { ConsoleProvider, useConsole } from "@/lib/store";
import type { ScenarioName } from "@/lib/types";
import { DOC_SOURCES, HEURISTIC_SOURCES } from "@/mocks/fixtures";
import { AlertsPanel } from "./AlertsPanel";
import { AppIcon, type AppIconName } from "./AppIcon";
import { ChatPane } from "./ChatPane";
import { NodeSwitcher } from "./NodeSwitcher";
import { SourceDialog } from "./SourceDialog";
import { Sparkline } from "./Sparkline";
import { ThemeToggle } from "./ThemeToggle";

type PageId = "overview" | "systems" | "investigations" | "assistant" | "knowledge" | "simulator";

const NAV: Array<{ id: PageId; label: string; icon: AppIconName }> = [
  { id: "overview", label: "Dashboard", icon: "overview" },
  { id: "systems", label: "Systems", icon: "systems" },
  { id: "investigations", label: "Investigations", icon: "investigations" },
  { id: "assistant", label: "AI Assistant", icon: "assistant" },
  { id: "knowledge", label: "Knowledge", icon: "knowledge" },
  { id: "simulator", label: "Training Simulator", icon: "simulator" },
];

const METRICS = [
  { id: "audit-capacity-pct", label: "Audit trail", unit: "%", threshold: 80 },
  { id: "cpu-busy-time", label: "CPU", unit: "%", threshold: 85 },
  { id: "request-qtime", label: "Queue time", unit: " ms", threshold: 40 },
];

function SectionTitle({ eyebrow, title, description }: { eyebrow?: string; title: string; description: string }) {
  return (
    <header className="mb-6">
      {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-accent">{eyebrow}</p>}
      <h2 className="text-2xl font-semibold tracking-tight text-fg">{title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
    </header>
  );
}

function MetricCard({ label, value, note, icon, tone = "neutral" }: { label: string; value: string; note: string; icon: AppIconName; tone?: "neutral" | "ok" | "warn" | "crit" }) {
  const iconTone = tone === "ok" ? "text-ok bg-ok/10" : tone === "warn" ? "text-warn bg-warn/10" : tone === "crit" ? "text-crit bg-crit/10" : "text-accent bg-accent/10";
  return (
    <article className="rounded-2xl border border-line bg-panel p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
        </div>
        <span className={`grid h-9 w-9 place-items-center rounded-xl ${iconTone}`}><AppIcon name={icon} size={19} /></span>
      </div>
      <p className="mt-3 text-xs text-muted">{note}</p>
    </article>
  );
}

function HealthCharts() {
  const { session } = useConsole();
  const node = session?.node ?? "";
  const { data, error, loading } = usePolling(() => (node ? api.getMetrics(node, "60m") : Promise.resolve(null)), 4000, node);

  return (
    <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">System health</h3>
          <p className="mt-0.5 text-xs text-muted">Live operational indicators for {environmentName(session?.node_display)}</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/10 px-2.5 py-1 text-xs font-medium text-ok">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" /> Monitoring active
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

function OverviewPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { session } = useConsole();
  const { data: alerts } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const active = alerts?.length ?? 0;

  return (
    <div>
      <SectionTitle title="Operations dashboard" description="Understand the state of monitored systems, find what needs attention, and begin an evidence-backed investigation." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Monitored systems" value="24" note="6 connected data sources" icon="systems" />
        <MetricCard label="Healthy" value="19" note="79% reporting normally" icon="overview" tone="ok" />
        <MetricCard label="Warnings" value="3" note="Capacity and performance signals" icon="investigations" tone="warn" />
        <MetricCard label="Active investigations" value={String(Math.max(2, active))} note="1 investigation needs review" icon="assistant" tone="crit" />
      </div>

      <div className="mt-5">
        <HealthCharts />
      </div>

      <section className="mt-5 overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <h3 className="font-semibold">Needs attention</h3>
            <p className="text-xs text-muted">Prioritized observations across monitored systems</p>
          </div>
          <button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("investigations")}>View investigations</button>
        </div>
        <div className="border-b border-line bg-accent/[0.045] px-5 py-4">
          <div className="grid items-center gap-4 lg:grid-cols-[minmax(220px,0.75fr)_minmax(360px,1.5fr)_auto]">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent/10 text-accent"><AppIcon name="assistant" size={21} /></span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">AI operational summary</p>
                <p className="mt-0.5 text-xs text-muted">Evidence checked 2 minutes ago</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-medium leading-5">Audit capacity is approaching its configured limit in {environmentName(session?.node_display)}.</p>
              <p className="mt-1 text-xs leading-5 text-muted"><span className="font-semibold text-warn">Moderate confidence:</span> a quarter-end pattern matches, but process status must be checked before the cause is confirmed.</p>
            </div>
            <button type="button" className="btn btn-primary justify-center whitespace-nowrap" onClick={() => onNavigate("assistant")}>Review investigation <ChevronRight size={14} /></button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-panel2/70 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">System</th><th className="px-4 py-3 font-medium">Health</th><th className="px-4 py-3 font-medium">Observation</th><th className="px-4 py-3 font-medium">Source</th><th className="px-5 py-3 font-medium">Updated</th></tr></thead>
            <tbody className="divide-y divide-line">
              <tr className="hover:bg-panel2/40"><td className="px-5 py-4 font-medium">Pathway-02</td><td className="px-4 py-4"><span className="status-chip status-critical">Critical</span></td><td className="px-4 py-4">Audit capacity rising; file may be pinned</td><td className="px-4 py-4 text-muted">EMS simulator</td><td className="px-5 py-4 text-muted">Now</td></tr>
              <tr className="hover:bg-panel2/40"><td className="px-5 py-4 font-medium">Storage-03</td><td className="px-4 py-4"><span className="status-chip status-warning">Warning</span></td><td className="px-4 py-4">Disk path errors above baseline</td><td className="px-4 py-4 text-muted">Metrics feed</td><td className="px-5 py-4 text-muted">4 min ago</td></tr>
              <tr className="hover:bg-panel2/40"><td className="px-5 py-4 font-medium">Reports-01</td><td className="px-4 py-4"><span className="status-chip status-warning">Warning</span></td><td className="px-4 py-4">Queue latency approaching limit</td><td className="px-4 py-4 text-muted">Application health</td><td className="px-5 py-4 text-muted">8 min ago</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const SYSTEM_ROWS = [
  ["Payments-01", "TMF", "Production", "Healthy", "0", "Now"],
  ["Pathway-02", "Pathway", "Production", "Critical", "3", "1 min ago"],
  ["Storage-03", "SCF Storage", "Production", "Warning", "1", "4 min ago"],
  ["Reports-01", "Pathway", "Test", "Warning", "1", "8 min ago"],
  ["Recovery-01", "TMF", "DR", "Healthy", "0", "2 min ago"],
  ["CPU-Cluster-A", "PEEK", "Production", "Healthy", "0", "Now"],
];

function SystemsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const [query, setQuery] = useState("");
  const rows = SYSTEM_ROWS.filter((row) => row.join(" ").toLowerCase().includes(query.toLowerCase()));
  return (
    <div>
      <SectionTitle title="Systems" description="A searchable inventory of monitored enterprise systems and their current operational state." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="relative min-w-[260px] flex-1 sm:max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} /><input className="field h-10 w-full rounded-xl bg-panel pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems" /></label>
        <span className="text-xs text-muted">{rows.length} systems shown • data minimized for demo</span>
      </div>
      <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr>{["System", "Subsystem", "Environment", "Health", "Alerts", "Updated", ""].map((head) => <th key={head} className="px-5 py-3 font-medium">{head}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">{rows.map((row) => <tr key={row[0]} className="hover:bg-panel2/40">{row.map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-medium" : "text-muted"}`}>{index === 3 ? <span className={`status-chip status-${cell.toLowerCase()}`}>{cell}</span> : cell}</td>)}<td className="px-5 py-4 text-right"><button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => onNavigate("assistant")}>Investigate</button></td></tr>)}</tbody>
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
          <button type="button" className="btn btn-primary w-full py-2.5" onClick={() => onNavigate("assistant")}><AppIcon name="assistant" size={16} /> Open AI investigation</button>
        </aside>
      </div>
    </div>
  );
}

function AssistantPage() {
  return (
    <div className="flex h-full min-h-[680px] flex-col">
      <SectionTitle eyebrow="Advisory only" title="AI troubleshooting assistant" description="Ask questions in everyday language. CAIL grounds each answer in approved knowledge and scoped operational evidence." />
      <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_340px]">
        <section className="flex min-h-[570px] flex-col overflow-hidden rounded-2xl border border-line bg-panel shadow-sm"><ChatPane /></section>
        <aside className="space-y-4">
          <section className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
            <div className="flex items-center gap-2"><Database size={17} className="text-accent" /><h3 className="font-semibold">Investigation context</h3></div>
            <dl className="mt-4 space-y-3 text-sm"><div><dt className="text-xs text-muted">Selected system</dt><dd className="mt-0.5 font-medium">Pathway-02</dd></div><div><dt className="text-xs text-muted">Incident</dt><dd className="mt-0.5 font-medium">INC-1042 • Active</dd></div><div><dt className="text-xs text-muted">Evidence window</dt><dd className="mt-0.5 font-medium">Last 60 minutes</dd></div></dl>
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
  const entries = useMemo(() => [
    ...DOC_SOURCES.slice(0, 6).map((source) => ({ id: source.id, name: source.title, detail: source.section ?? "Approved excerpt", type: "Manual", scope: source.applies_to ?? "All supported series", status: "Approved" })),
    ...HEURISTIC_SOURCES.map((source) => ({ id: source.id, name: `${source.owner_name ?? source.owner} expert note`, detail: humanizeEnvironmentText(source.why), type: "Expert note", scope: humanizeEnvironmentText(source.scope ?? "Scoped"), status: "Approved" })),
  ], []);
  const visible = entries.filter((entry) => filter === "all" || (filter === "manuals" ? entry.type === "Manual" : entry.type === "Expert note"));
  return (
    <div>
      <SectionTitle title="Knowledge" description="Approved manuals, reviewed operating procedures, and preserved expert experience used to ground CAIL answers." />
      <div className="mb-4 flex flex-wrap gap-2">{(["all", "manuals", "expert"] as const).map((item) => <button key={item} type="button" className={`rounded-full border px-4 py-2 text-sm font-medium ${filter === item ? "border-accent bg-accent/10 text-accent" : "border-line bg-panel text-muted hover:text-fg"}`} onClick={() => setFilter(item)}>{item === "all" ? "All knowledge" : item === "manuals" ? "Manuals & runbooks" : "Expert knowledge"}</button>)}</div>
      <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
        <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">Name</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 font-medium">Applicable scope</th><th className="px-4 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Review</th></tr></thead><tbody className="divide-y divide-line">{visible.map((entry) => <tr key={entry.id} className="hover:bg-panel2/40"><td className="max-w-md px-5 py-4"><p className="font-medium">{entry.name}</p><p className="mt-1 truncate text-xs text-muted">{entry.detail}</p></td><td className="px-4 py-4 text-muted">{entry.type}</td><td className="px-4 py-4 text-muted">{entry.scope}</td><td className="px-4 py-4"><span className="status-chip status-healthy"><FileCheck2 size={12} />{entry.status}</span></td><td className="px-5 py-4 text-muted">17 Oct 2026</td></tr>)}</tbody></table></div>
      </section>
      <p className="mt-4 text-xs text-muted">Expert corrections enter a review queue before they become searchable knowledge.</p>
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
      <div className="grid gap-4 md:grid-cols-2">{SCENARIOS.map((scenario, index) => <article key={scenario.id} className="rounded-2xl border border-line bg-panel p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-accent/10 text-accent"><AppIcon name="simulator" size={21} /></span><span className="rounded-full bg-panel2 px-2.5 py-1 text-xs text-muted">Scenario {index + 1}</span></div><h3 className="mt-4 text-lg font-semibold">{scenario.title}</h3><p className="mt-2 min-h-10 text-sm leading-5 text-muted">{scenario.description}</p><div className="mt-4 flex items-center gap-4 text-xs text-muted"><span className="inline-flex items-center gap-1"><Gauge size={13} />{scenario.difficulty}</span><span className="inline-flex items-center gap-1"><Clock3 size={13} />{scenario.duration}</span></div><button type="button" className="btn btn-primary mt-5 w-full py-2" disabled={running === scenario.id} onClick={() => void start(scenario.id)}>{running === scenario.id ? "Scenario running" : "Start scenario"}</button></article>)}</div>
      {status && <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ok/30 bg-ok/8 p-4 text-sm" role="status"><span className="inline-flex items-center gap-2"><CheckCircle2 size={17} className="text-ok" />{status}</span>{running && <button type="button" className="btn" onClick={() => onNavigate("assistant")}>Open AI Assistant</button>}</div>}
    </div>
  );
}

function WorkspaceShell() {
  const { session, sessionError } = useConsole();
  const [page, setPage] = useState<PageId>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const navigate = (next: PageId) => { setPage(next); setMobileOpen(false); };
  const current = NAV.find((item) => item.id === page)?.label ?? "Dashboard";

  return (
    <div className="flex h-screen min-w-0 bg-bg text-fg">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-panel transition-transform lg:static lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-16 items-center gap-3 border-b border-line px-5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-sm font-bold text-white">C</span><div><p className="font-semibold leading-tight">CAIL</p><p className="text-[11px] text-muted">Operations Assistant</p></div><button type="button" className="ml-auto p-1 text-muted lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button></div>
        <nav className="flex-1 space-y-1 p-3" aria-label="Primary navigation">{NAV.map((item) => { const active = page === item.id; return <button key={item.id} type="button" className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors ${active ? "bg-accent/10 text-accent" : "text-muted hover:bg-panel2 hover:text-fg"}`} onClick={() => navigate(item.id)}><AppIcon name={item.icon} size={18} />{item.label}{item.id === "investigations" && <span className="ml-auto rounded-full bg-crit/10 px-2 py-0.5 text-[11px] text-crit">2</span>}</button>; })}</nav>
        <div className="border-t border-line p-4"><div className="rounded-xl bg-panel2 p-3"><p className="flex items-center gap-2 text-xs font-medium"><ShieldCheck size={14} className="text-ok" />Advisory mode</p><p className="mt-1 text-[11px] leading-4 text-muted">No production execution or credentials.</p></div><p className="mt-3 text-[10px] text-muted">CAIL Catalyst 2026 prototype</p><a className="mt-1 block text-[10px] text-muted underline-offset-2 hover:underline" href="https://freeicons.io/icon-list/business-%26-management-%28line-style%29" target="_blank" rel="noreferrer">Icons by Nine One · Freeicons.io</a></div>
      </aside>
      {mobileOpen && <button className="fixed inset-0 z-30 bg-black/30 lg:hidden" aria-label="Close navigation backdrop" onClick={() => setMobileOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-panel px-4 sm:px-6">
          <button type="button" className="btn px-2 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={17} /></button>
          <div className="hidden min-w-0 flex-1 sm:block"><label className="relative block max-w-xl"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="field h-10 w-full rounded-xl bg-panel2 pl-9" placeholder="Search systems, investigations, and knowledge" aria-label="Global search" /></label></div>
          <div className="ml-auto flex items-center gap-2"><span className="hidden rounded-full border border-warn/30 bg-warn/8 px-3 py-1.5 text-xs font-medium text-warn md:inline-flex">Demo mode</span><NodeSwitcher /><ThemeToggle /><button type="button" className="btn h-9 w-9 rounded-full px-0" aria-label="Help"><CircleHelp size={16} /></button></div>
        </header>
        <div className="flex min-h-10 shrink-0 items-center gap-2 border-b border-accent/20 bg-accent/7 px-4 text-xs text-muted sm:px-6"><FlaskConical size={14} className="text-accent" /><strong className="text-fg">Synthetic data</strong><span className="hidden sm:inline">• No production infrastructure connected • Suggestions are advisory</span><span className="ml-auto hidden text-[11px] lg:inline">{USE_MOCKS ? "Mock services active" : "API mode"}</span></div>
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
