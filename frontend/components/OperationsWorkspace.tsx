"use client";

import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  FlaskConical,
  Gauge,
  Menu,
  Search,
  ShieldCheck,
  TerminalSquare,
  TriangleAlert,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { api, USE_MOCKS } from "@/lib/api";
import { environmentName, fmtTime, humanizeEnvironmentText } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { ConsoleProvider, useConsole } from "@/lib/store";
import type { Alert, ScenarioName } from "@/lib/types";
import { AppIcon, type AppIconName } from "./AppIcon";
import { AssistantComposer, ChatPane } from "./ChatPane";
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
  { id: "knowledge", label: "Knowledge Library", icon: "knowledge" },
  { id: "simulator", label: "Training Simulator", icon: "simulator" },
];

const METRICS = [
  { id: "audit-capacity-pct", label: "Audit trail", unit: "%", threshold: 80 },
  { id: "cpu-busy-time", label: "CPU", unit: "%", threshold: 85 },
  { id: "request-qtime", label: "Queue time", unit: " ms", threshold: 40 },
];

function SectionTitle({ eyebrow, title, description }: { eyebrow?: string; title: string; description: string }) {
  return (
    <header className="mb-5">
      {eyebrow && <p className="mb-1 text-xs font-medium text-accent">{eyebrow}</p>}
      <h2 className="text-2xl font-semibold leading-8 text-fg">{title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
    </header>
  );
}

function MetricCard({ label, value, note, icon, tone = "neutral" }: { label: string; value: string; note: string; icon: AppIconName; tone?: "neutral" | "ok" | "warn" | "crit" }) {
  const iconTone = tone === "ok" ? "text-ok" : tone === "warn" ? "text-warn" : tone === "crit" ? "text-crit" : "text-accent";
  return (
    <article className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted">{label}</p>
          <p className="metric-value mt-2 text-[28px] font-semibold leading-8">{value}</p>
        </div>
        <span className={`grid h-8 w-8 place-items-center ${iconTone}`}><AppIcon name={icon} size={18} /></span>
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
    <section className="rounded-xl border border-line bg-panel p-5">
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
                  <p className="metric-value mt-1 text-xl font-semibold" style={{ color }}>
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
  const { data: alerts, loading: alertsLoading } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const active = alerts?.length ?? 0;

  return (
    <div>
      <SectionTitle title="Operations dashboard" description="Monitor system health and open evidence-backed investigations." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Monitored systems" value="24" note="6 connected data sources" icon="systems" />
        <MetricCard label="Healthy" value="19" note="79% reporting normally" icon="overview" tone="ok" />
        <MetricCard label="Needs attention" value="3" note="Capacity and performance signals" icon="investigations" tone="warn" />
        <MetricCard label="Active investigations" value={alertsLoading || !alerts ? "—" : String(active)} note={alertsLoading || !alerts ? "Checking current alerts" : active === 1 ? "1 investigation needs review" : active > 1 ? `${active} investigations need review` : "No investigations need review"} icon="assistant" tone="warn" />
      </div>

      <div className="mt-6">
        <HealthCharts />
      </div>

      <section className="mt-6 overflow-hidden rounded-xl border border-line bg-panel">
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
              <span className="grid h-8 w-8 place-items-center text-accent"><AppIcon name="assistant" size={19} /></span>
              <div>
                <p className="text-xs font-semibold text-accent">AI operational summary</p>
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
              <tr className="hover:bg-panel2/40"><td className="px-5 py-3 font-medium">Pathway-02</td><td className="px-4 py-3"><span className="status-chip status-warning">Warning</span></td><td className="px-4 py-3">Audit capacity rising; file may be pinned</td><td className="px-4 py-3 text-muted">EMS simulator</td><td className="px-5 py-3 text-muted">Now</td></tr>
              <tr className="hover:bg-panel2/40"><td className="px-5 py-3 font-medium">Storage-03</td><td className="px-4 py-3"><span className="status-chip status-warning">Warning</span></td><td className="px-4 py-3">Disk path errors above baseline</td><td className="px-4 py-3 text-muted">Metrics feed</td><td className="px-5 py-3 text-muted">4 min ago</td></tr>
              <tr className="hover:bg-panel2/40"><td className="px-5 py-3 font-medium">Reports-01</td><td className="px-4 py-3"><span className="status-chip status-warning">Warning</span></td><td className="px-4 py-3">Queue latency approaching limit</td><td className="px-4 py-3 text-muted">Application health</td><td className="px-5 py-3 text-muted">8 min ago</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

type SystemRecord = {
  id: string;
  subsystem: string;
  environment: "Primary Production" | "Disaster Recovery" | "Test Environment";
  health: "Healthy" | "Warning" | "Critical";
  incidents: number;
  lastSignal: string;
  purpose: string;
  expert: { name: string; title: string; availability: "On call" | "On shift" };
  backup: { name: string; title: string };
  contributor?: { name: string; title: string; status: string; knowledge: string };
  dependencies: string[];
  knowledge: string[];
  diagnostics: string[];
  evidence: string[];
};

const SYSTEMS: SystemRecord[] = [
  { id: "Payments-01", subsystem: "TMF", environment: "Primary Production", health: "Healthy", incidents: 0, lastSignal: "Now", purpose: "Coordinates payment transaction processing and settlement handoff.", expert: { name: "Raj Patel", title: "NonStop Systems Specialist", availability: "On call" }, backup: { name: "Lena Kowalski", title: "Storage Administrator" }, contributor: { name: "Maria Rossi", title: "Senior NonStop Operator", status: "Retired · Knowledge contributor", knowledge: "Quarter-end settlement and TMF recovery patterns" }, dependencies: ["Pathway-02", "TMF", "Settlement queue"], knowledge: ["TMF Operations Manual", "Quarter-end settlement runbook"], diagnostics: ["Transaction status", "Queue depth", "TMF process state"], evidence: ["EMS simulator", "Application health", "Approved manuals"] },
  { id: "Pathway-02", subsystem: "Pathway", environment: "Primary Production", health: "Warning", incidents: 3, lastSignal: "1 min ago", purpose: "Routes settlement requests between applications and TMF services.", expert: { name: "Raj Patel", title: "NonStop Systems Specialist", availability: "On call" }, backup: { name: "Lena Kowalski", title: "Storage Administrator" }, contributor: { name: "Maria Rossi", title: "Senior NonStop Operator", status: "Retired · Knowledge contributor", knowledge: "Audit trail, Pathway and quarter-end failure patterns" }, dependencies: ["Payments-01", "TMF", "Audit trail"], knowledge: ["Pathway Operations Manual", "Audit trail capacity runbook", "6 reviewed expert patterns"], diagnostics: ["Audit trail status", "Pathway server status", "Transaction status"], evidence: ["EMS simulator", "Metrics feed", "Expert knowledge"] },
  { id: "Storage-03", subsystem: "SCF Storage", environment: "Primary Production", health: "Warning", incidents: 1, lastSignal: "4 min ago", purpose: "Provides disk paths and storage capacity for monitored NonStop workloads.", expert: { name: "Lena Kowalski", title: "Storage Administrator", availability: "On shift" }, backup: { name: "Raj Patel", title: "NonStop Systems Specialist" }, dependencies: ["Payments-01", "Reports-01", "SCF"], knowledge: ["SCF storage operations", "Disk-path recovery procedure"], diagnostics: ["Disk path status", "Capacity summary", "SCF configuration"], evidence: ["Storage metrics", "SCF events", "Approved procedures"] },
  { id: "Reports-01", subsystem: "Pathway", environment: "Test Environment", health: "Warning", incidents: 1, lastSignal: "8 min ago", purpose: "Generates operational reports in the isolated test environment.", expert: { name: "Raj Patel", title: "NonStop Systems Specialist", availability: "On call" }, backup: { name: "Lena Kowalski", title: "Storage Administrator" }, dependencies: ["Pathway", "Reporting queue"], knowledge: ["Reporting service runbook"], diagnostics: ["Queue latency", "Process status"], evidence: ["Application health", "Test event feed"] },
  { id: "Recovery-01", subsystem: "TMF", environment: "Disaster Recovery", health: "Healthy", incidents: 0, lastSignal: "2 min ago", purpose: "Maintains the validated recovery context for TMF services.", expert: { name: "Raj Patel", title: "NonStop Systems Specialist", availability: "On call" }, backup: { name: "Lena Kowalski", title: "Storage Administrator" }, contributor: { name: "Maria Rossi", title: "Senior NonStop Operator", status: "Retired · Knowledge contributor", knowledge: "TMF recovery and production-to-DR handoff" }, dependencies: ["TMF", "Recovery storage"], knowledge: ["Disaster recovery runbook", "TMF recovery checklist"], diagnostics: ["Recovery process state", "TMF status"], evidence: ["DR event feed", "Recovery checklist"] },
  { id: "CPU-Cluster-A", subsystem: "PEEK", environment: "Primary Production", health: "Healthy", incidents: 0, lastSignal: "Now", purpose: "Provides processor health and workload telemetry for production services.", expert: { name: "Raj Patel", title: "NonStop Systems Specialist", availability: "On call" }, backup: { name: "Lena Kowalski", title: "Storage Administrator" }, dependencies: ["PEEK", "Metrics feed"], knowledge: ["Processor monitoring guide"], diagnostics: ["CPU utilization", "Process activity"], evidence: ["PEEK telemetry", "Metrics feed"] },
];

function SystemsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const [query, setQuery] = useState("");
  const [healthFilter, setHealthFilter] = useState("All health");
  const [environmentFilter, setEnvironmentFilter] = useState("All environments");
  const [selectedId, setSelectedId] = useState("Pathway-02");
  const rows = SYSTEMS.filter((system) => {
    const matchesQuery = [system.id, system.subsystem, system.environment, system.expert.name, system.expert.title, system.backup.name, system.contributor?.name ?? ""].join(" ").toLowerCase().includes(query.toLowerCase());
    const matchesHealth = healthFilter === "All health" || system.health === healthFilter;
    const matchesEnvironment = environmentFilter === "All environments" || system.environment === environmentFilter;
    return matchesQuery && matchesHealth && matchesEnvironment;
  });
  const selected = rows.find((system) => system.id === selectedId) ?? rows[0] ?? null;

  return (
    <div>
      <SectionTitle title="Systems" description="Understand system health, ownership, dependencies, and safe diagnostic coverage." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap gap-2">
          <label className="relative min-w-[240px] flex-1 sm:max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} /><input className="field h-10 w-full rounded-xl bg-panel pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems or experts" /></label>
          <select className="field h-10 rounded-xl bg-panel" value={healthFilter} onChange={(event) => setHealthFilter(event.target.value)} aria-label="Filter systems by health"><option>All health</option><option>Healthy</option><option>Warning</option><option>Critical</option></select>
          <select className="field h-10 rounded-xl bg-panel" value={environmentFilter} onChange={(event) => setEnvironmentFilter(event.target.value)} aria-label="Filter systems by environment"><option>All environments</option><option>Primary Production</option><option>Disaster Recovery</option><option>Test Environment</option></select>
        </div>
        <span className="text-xs text-muted">{rows.length} systems shown • data minimized for demo</span>
      </div>
      <section className="overflow-hidden rounded-xl border border-line bg-panel">
        <div className="divide-y divide-line md:hidden">
          {rows.map((system) => {
            const active = selected?.id === system.id;
            return <article key={system.id} className={`border-l-2 p-4 ${active ? "border-accent bg-accent/[0.045]" : "border-transparent"}`}>
              <button type="button" className="w-full text-left" onClick={() => setSelectedId(system.id)} aria-label={`View ${system.id}`}>
                <span className="flex items-start justify-between gap-3"><span><span className="font-semibold text-fg">{system.id}</span><span className="mt-0.5 block text-xs text-muted">{system.subsystem} · {system.environment}</span></span><span className={`status-chip status-${system.health.toLowerCase()}`}>{system.health}</span></span>
                <span className="mt-3 flex items-center gap-2"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-panel2 text-xs font-semibold">{system.expert.name.split(" ").map((part) => part[0]).join("")}</span><span className="min-w-0"><span className="block text-sm font-medium">{system.expert.name}</span><span className="block truncate text-xs text-muted">{system.expert.title}</span></span></span>
              </button>
              <div className="mt-3 flex items-center justify-between gap-3 text-xs"><span className="text-muted">{system.incidents > 0 ? `${system.incidents} active ${system.incidents === 1 ? "incident" : "incidents"}` : "No active incidents"} · signal {system.lastSignal.toLowerCase()}</span><button type="button" className="shrink-0 font-medium text-accent" onClick={() => system.incidents > 0 ? onNavigate("investigations") : setSelectedId(system.id)}>{system.incidents > 0 ? "Review" : "View"}</button></div>
            </article>;
          })}
          {rows.length === 0 && <p className="px-5 py-8 text-center text-sm text-muted">No systems match the selected filters.</p>}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1060px] text-left text-sm">
            <thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr>{["System", "Environment", "Health", "Active incidents", "Primary expert", "Last signal", ""].map((head) => <th key={head} className="px-4 py-3 font-medium first:pl-5 last:pr-5">{head}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((system) => {
                const active = selected?.id === system.id;
                return <tr key={system.id} tabIndex={0} aria-selected={active} className={`cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${active ? "bg-accent/[0.045]" : "hover:bg-panel2/40"}`} onClick={() => setSelectedId(system.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(system.id); } }}>
                  <td className={`border-l-2 px-4 py-3 pl-5 ${active ? "border-accent" : "border-transparent"}`}><span className="block font-semibold text-fg">{system.id}</span><span className="mt-0.5 block text-xs text-muted">{system.subsystem}</span></td>
                  <td className="px-4 py-3 text-muted">{system.environment}</td>
                  <td className="px-4 py-3"><span className={`status-chip status-${system.health.toLowerCase()}`}>{system.health}</span></td>
                  <td className="px-4 py-3">{system.incidents > 0 ? <span className="status-chip status-warning">{system.incidents} {system.incidents === 1 ? "warning" : "warnings"}</span> : <span className="text-muted">None</span>}</td>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-panel2 text-xs font-semibold text-fg">{system.expert.name.split(" ").map((part) => part[0]).join("")}</span><span><strong className="block font-medium text-fg">{system.expert.name}</strong><span className="block text-xs text-muted">{system.expert.title}</span></span></div></td>
                  <td className="px-4 py-3 text-muted">{system.lastSignal}</td>
                  <td className="px-5 py-3 text-right"><button type="button" className="text-sm font-medium text-accent hover:underline" onClick={(event) => { event.stopPropagation(); if (system.incidents > 0) onNavigate("investigations"); else setSelectedId(system.id); }}>{system.incidents > 0 ? "Review incident" : "View system"}</button></td>
                </tr>;
              })}
              {rows.length === 0 && <tr><td colSpan={7} className="px-5 py-8 text-center text-sm text-muted">No systems match the selected filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {selected && <SystemDetail system={selected} onNavigate={onNavigate} />}
    </div>
  );
}

function SystemDetail({ system, onNavigate }: { system: SystemRecord; onNavigate: (page: PageId) => void }) {
  const initials = (name: string) => name.split(" ").map((part) => part[0]).join("");
  return (
    <section className="mt-5 overflow-hidden rounded-xl border border-line bg-panel" aria-label={`${system.id} system details`}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-semibold">{system.id}</h3><span className={`status-chip status-${system.health.toLowerCase()}`}>{system.health}</span><span className="rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{system.environment}</span></div>
          <p className="mt-1 max-w-3xl text-sm text-muted">{system.purpose}</p>
        </div>
        <button type="button" className={system.incidents > 0 ? "btn btn-primary" : "btn"} onClick={() => onNavigate(system.incidents > 0 ? "investigations" : "assistant")}>{system.incidents > 0 ? "Review active incidents" : "Open in AI Assistant"}<ChevronRight size={14} /></button>
      </header>

      <dl className="grid gap-3 border-b border-line p-4 text-xs sm:grid-cols-3">
        <div className="rounded-lg bg-panel2 p-3"><dt className="text-muted">Current state</dt><dd className="mt-1 font-semibold text-fg">{system.health}{system.incidents > 0 ? ` · ${system.incidents} active ${system.incidents === 1 ? "incident" : "incidents"}` : " · no active incidents"}</dd></div>
        <div className="rounded-lg bg-panel2 p-3"><dt className="text-muted">Last telemetry</dt><dd className="mt-1 font-semibold text-fg">{system.lastSignal}</dd></div>
        <div className="rounded-lg bg-panel2 p-3"><dt className="text-muted">Safe operating mode</dt><dd className="mt-1 inline-flex items-center gap-1.5 font-semibold text-ok"><ShieldCheck size={14} />Read-only diagnostics</dd></div>
      </dl>

      <div className="grid lg:grid-cols-2">
        <section className="border-b border-line p-5 lg:border-b-0 lg:border-r">
          <h4 className="font-semibold">People and expertise</h4>
          <p className="mt-1 text-xs text-muted">Who can operate, validate, or explain this system.</p>
          <div className="mt-4 divide-y divide-line">
            <div className="flex items-center gap-3 pb-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent/10 text-xs font-semibold text-accent">{initials(system.expert.name)}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{system.expert.name}</p><span className={`status-chip ${system.expert.availability === "On shift" ? "status-healthy" : "status-warning"}`}>{system.expert.availability}</span></div><p className="text-xs text-muted">Primary expert · {system.expert.title}</p></div></div>
            <div className="flex items-center gap-3 py-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-panel2 text-xs font-semibold">{initials(system.backup.name)}</span><div><p className="font-medium">{system.backup.name}</p><p className="text-xs text-muted">Backup specialist · {system.backup.title}</p></div></div>
            {system.contributor && <div className="flex items-start gap-3 pt-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-panel2 text-xs font-semibold">{initials(system.contributor.name)}</span><div><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{system.contributor.name}</p><span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">{system.contributor.status}</span></div><p className="text-xs text-muted">{system.contributor.title}</p><p className="mt-1 text-xs text-fg">Knowledge: {system.contributor.knowledge}</p></div></div>}
          </div>
        </section>

        <section className="p-5">
          <h4 className="font-semibold">Operational context</h4>
          <p className="mt-1 text-xs text-muted">Scope CAIL uses when explaining or troubleshooting this system.</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div><h5 className="text-xs font-semibold text-fg">Dependencies</h5><ul className="mt-2 space-y-1.5 text-sm text-muted">{system.dependencies.map((item) => <li key={item}>• {item}</li>)}</ul></div>
            <div><h5 className="text-xs font-semibold text-fg">Evidence sources</h5><ul className="mt-2 space-y-1.5 text-sm text-muted">{system.evidence.map((item) => <li key={item}>• {item}</li>)}</ul></div>
          </div>
        </section>
      </div>

      <div className="grid border-t border-line md:grid-cols-2">
        <section className="border-b border-line p-5 md:border-b-0 md:border-r"><div className="flex items-center gap-2"><FileCheck2 size={16} className="text-ok" /><h4 className="font-semibold">Approved knowledge</h4></div><ul className="mt-3 space-y-2 text-sm">{system.knowledge.map((item) => <li key={item} className="flex items-center justify-between gap-3"><span>{item}</span><span className="status-chip status-healthy">Approved</span></li>)}</ul></section>
        <section className="p-5"><div className="flex items-center gap-2"><ShieldCheck size={16} className="text-ok" /><h4 className="font-semibold">Available safe diagnostics</h4></div><ul className="mt-3 space-y-2 text-sm">{system.diagnostics.map((item) => <li key={item} className="flex items-center justify-between gap-3"><span>{item}</span><span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] font-medium text-muted">Read-only</span></li>)}</ul></section>
      </div>
    </section>
  );
}

function InvestigationsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { session } = useConsole();
  const { data: alerts, error, loading } = usePolling(() => api.getAlerts(), 2000, session?.node ?? "");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [openSections, setOpenSections] = useState<Set<InvestigationSectionId>>(new Set(["incident"]));
  const activeAlerts = alerts ?? [];
  const selected = activeAlerts.find((alert) => alert.id === selectedId) ?? activeAlerts[0] ?? null;

  const toggle = (id: InvestigationSectionId) => setOpenSections((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const selectAlert = (alert: Alert) => {
    setSelectedId(alert.id);
    setOpenSections(new Set(["incident"]));
  };

  return (
    <div>
      <SectionTitle title="Investigations" description="Triage incidents and hand selected cases to CAIL for guided troubleshooting." />

      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full border border-line bg-panel px-3 py-1.5 font-medium"><strong className="mr-1 text-fg">{activeAlerts.length}</strong><span className="text-muted">active</span></span>
        <span className="rounded-full border border-warn/30 bg-warn/8 px-3 py-1.5 font-medium text-warn">{activeAlerts.filter((alert) => alert.severity === "warning").length} {activeAlerts.filter((alert) => alert.severity === "warning").length === 1 ? "warning" : "warnings"}</span>
        <span className="rounded-full border border-line bg-panel px-3 py-1.5 font-medium text-muted">Evidence window: last 60 minutes</span>
      </div>

      <section className="grid min-h-[610px] overflow-hidden rounded-xl border border-line bg-bg lg:grid-cols-[290px_minmax(0,1fr)]">
        <aside className="border-b border-line bg-panel lg:border-b-0 lg:border-r" aria-label="Investigation queue">
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-4">
            <div>
              <h3 className="font-semibold">Investigation queue</h3>
              <p className="mt-0.5 text-xs text-muted">Cases requiring operator attention</p>
            </div>
            <span className="rounded-full bg-panel2 px-2 py-0.5 text-xs font-medium text-muted">{activeAlerts.length}</span>
          </div>
          <div className="divide-y divide-line">
            {loading && <p className="px-4 py-4 text-sm text-muted">Loading active investigations…</p>}
            {error && <p role="alert" className="px-4 py-4 text-sm text-crit">Unable to load investigations: {error}</p>}
            {!loading && !error && activeAlerts.length === 0 && <div className="px-4 py-4"><p className="font-medium">No active investigations</p><p className="mt-1 text-xs text-muted">Watcher alerts will appear here with their evidence trail.</p></div>}
            {activeAlerts.map((alert) => {
              const active = selected?.id === alert.id;
              return (
                <button key={alert.id} type="button" className={`w-full border-l-2 px-4 py-3 text-left transition-colors ${active ? "border-accent bg-accent/8" : "border-transparent hover:bg-panel2/60"}`} onClick={() => selectAlert(alert)} aria-pressed={active}>
                  <div className="flex items-center gap-2"><span className="text-xs font-semibold text-fg">INC-1042</span><span className={`status-chip ${alert.severity === "critical" ? "status-critical" : "status-warning"}`}>{alert.severity === "critical" ? "Critical" : "Warning"}</span></div>
                  <p className="mt-2 text-sm font-semibold leading-5">Master audit trail nearing overflow threshold</p>
                  <p className="mt-2 text-xs text-muted">Pathway-02 · detected 2 minutes ago</p>
                  <div className="mt-2 flex items-center justify-between text-xs"><span className="font-medium text-warn">~{alert.lead_time_min} min lead time</span><ChevronRight size={14} className={active ? "text-accent" : "text-muted"} /></div>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="min-w-0 bg-bg">
          {selected ? (
            <>
              <header className="border-b border-line bg-panel px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">INC-1042</h3><span className={`status-chip ${selected.severity === "critical" ? "status-critical" : "status-warning"}`}>{selected.severity === "critical" ? "Critical" : "Warning"}</span><span className="status-chip bg-accent/10 text-accent">Under investigation</span></div>
                    <p className="mt-2 text-sm text-muted">Watcher detected a known risk pattern before a confirmed service interruption.</p>
                  </div>
                  <button type="button" className="btn btn-primary" onClick={() => onNavigate("assistant")}><AppIcon name="assistant" size={16} /> Open in AI Assistant <ChevronRight size={14} /></button>
                </div>
                <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-[minmax(260px,1.5fr)_minmax(150px,0.75fr)_minmax(150px,0.75fr)]">
                  <div className="rounded-xl border border-line bg-panel2 px-3 py-2"><dt className="font-medium text-muted">Alert</dt><dd className="mt-0.5 font-semibold text-fg">Master audit trail nearing overflow threshold</dd></div>
                  <div className="rounded-xl border border-line bg-panel2 px-3 py-2"><dt className="font-medium text-muted">Affected system</dt><dd className="mt-0.5 font-semibold text-fg">Pathway-02</dd></div>
                  <div className="rounded-xl border border-line bg-panel2 px-3 py-2"><dt className="font-medium text-muted">First detected</dt><dd className="mt-0.5 font-semibold text-fg">2 minutes ago</dd></div>
                </dl>
              </header>

              <div className="space-y-2 p-3 sm:p-4">
                <InvestigationSection id="incident" label="Incident" preview="Audit capacity is rising toward the overflow threshold." badge={<span className="status-chip status-warning">Warning</span>} open={openSections.has("incident")} onToggle={toggle}>
                  <p className="text-base font-semibold">Audit capacity is approaching its configured limit.</p>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">The active audit trail is filling and matches a previously observed quarter-end pattern. No outage or root cause has been confirmed.</p>
                  <div className="mt-4 grid gap-3 text-xs sm:grid-cols-3"><div className="rounded-lg border border-line/70 bg-panel2 p-3"><span className="block text-muted">Current usage</span><strong className="mt-1 block text-lg text-fg">{selected.evidence.find((item) => item.metric)?.value ?? 62}%</strong></div><div className="rounded-lg border border-line/70 bg-panel2 p-3"><span className="block text-muted">Configured limit</span><strong className="mt-1 block text-lg text-fg">80%</strong></div><div className="rounded-lg border border-line/70 bg-panel2 p-3"><span className="block text-muted">Estimated lead time</span><strong className="mt-1 block text-lg text-warn">~{selected.lead_time_min} min</strong></div></div>
                </InvestigationSection>

                <InvestigationSection id="systems" label="Affected systems" preview="Pathway-02, TMF, and Primary Production context" badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">2 systems</span>} open={openSections.has("systems")} onToggle={toggle}>
                  <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-line bg-panel p-3"><p className="font-medium">Pathway-02</p><p className="mt-1 text-xs text-muted">Settlement application · at risk</p></div><div className="rounded-lg border border-line bg-panel p-3"><p className="font-medium">{selected.subsystem}</p><p className="mt-1 text-xs text-muted">Transaction management · warning</p></div></div>
                  <p className="mt-3 text-xs text-muted">Context locked to {environmentName(selected.node)}. Evidence from other environments is excluded.</p>
                </InvestigationSection>

                <InvestigationSection id="evidence" label="Confirmed evidence" preview={`${selected.evidence.length + selected.fix_claims.filter((claim) => claim.verified).length} verified records linked to this case`} badge={<span className="status-chip status-healthy">Verified sources</span>} open={openSections.has("evidence")} onToggle={toggle}>
                  <ul className="space-y-3 text-sm">
                    {selected.evidence.map((item, index) => <li key={`${item.event ?? item.metric}-${index}`} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-line bg-panel p-3"><span>{item.event ? `${item.event} occurred ${item.count ?? 1} times.` : `${item.metric?.replace(/-/g, " ")} is ${item.value}% and ${item.trend}.`}</span><span className="text-xs text-muted">Operational evidence</span></li>)}
                    {selected.fix_claims.filter((claim) => claim.verified).map((claim) => <li key={claim.source_id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-line bg-panel p-3"><span>{humanizeEnvironmentText(claim.text)}</span><span className="text-xs text-muted">{claim.lane === "doc" ? "Approved manual" : "Expert knowledge"} · {Math.round(claim.score * 100)}%</span></li>)}
                  </ul>
                </InvestigationSection>

                <InvestigationSection id="assessment" label="Possible explanation" preview="A long-running transaction may be preventing audit-file reuse." badge={<span className="status-chip status-warning">Unverified</span>} open={openSections.has("assessment")} onToggle={toggle}>
                  <div className="rounded-lg border border-warn/30 bg-warn/8 p-3"><p className="font-medium text-warn">Working hypothesis</p><p className="mt-1 text-sm leading-6">A long-running quarter-end transaction may be pinning the active audit file and preventing it from being reused.</p></div>
                  <div className="mt-3 rounded-lg border border-line bg-panel p-3"><p className="text-xs font-semibold text-muted">Still unknown</p><p className="mt-1 text-sm">The responsible process and root cause remain unconfirmed until the proposed diagnostic is reviewed.</p></div>
                  <p className="mt-3 text-xs text-muted">Pattern warned early in {selected.backtest.hits}/{selected.backtest.of} comparable incidents, averaging {selected.backtest.avg_lead_min} minutes of lead time. This supports investigation, not a causal conclusion.</p>
                </InvestigationSection>

                <InvestigationSection id="action" label="Controlled next step" preview="Review a read-only transaction-status diagnostic." badge={<span className="status-chip status-healthy">Read-only</span>} open={openSections.has("action")} onToggle={toggle}>
                  <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><p className="font-medium">Identify the transaction holding the audit file.</p><p className="mt-1 text-sm text-muted">The command comes from an allowlisted template and must be reviewed by an operator.</p>{selected.next_commands[0] && <code className="mt-3 block overflow-x-auto rounded-lg bg-[#05080a] px-3 py-2 text-sm text-[#7ee2a1]">{selected.next_commands[0].command}</code>}<p className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-warn"><ShieldCheck size={14} />Proposed for review only · not executed</p></div><button type="button" className="btn btn-primary" onClick={() => onNavigate("assistant")}>Review with CAIL <ChevronRight size={14} /></button></div>
                </InvestigationSection>

                <InvestigationSection id="experts" label="Expert knowledge" preview={`${selected.owner_name} pattern with ${selected.backup_expert.name} as backup`} badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">2 experts</span>} open={openSections.has("experts")} onToggle={toggle}>
                  <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-line bg-panel p-3"><p className="font-medium">{selected.owner_name}</p><p className="mt-1 text-xs text-muted">Pattern owner · preserved quarter-end experience</p></div><div className="rounded-lg border border-line bg-panel p-3"><p className="font-medium">{selected.backup_expert.name}</p><p className="mt-1 text-xs text-muted">Available backup specialist</p></div></div>
                </InvestigationSection>

                <InvestigationSection id="timeline" label="Incident timeline" preview="Detection, correlation, and review events" badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">4 events</span>} open={openSections.has("timeline")} onToggle={toggle}>
                  <ol className="divide-y divide-line text-sm"><li className="grid gap-1 py-3 sm:grid-cols-[110px_1fr]"><span className="text-xs text-muted">{fmtTime(selected.ts)}</span><div><p className="font-medium">Watcher opened investigation</p><p className="mt-1 text-xs text-muted">Known pattern and rising audit capacity were correlated.</p></div></li><li className="grid gap-1 py-3 sm:grid-cols-[110px_1fr]"><span className="text-xs text-muted">+ seconds</span><div><p className="font-medium">Evidence validated</p><p className="mt-1 text-xs text-muted">Source records and applicable knowledge were linked.</p></div></li><li className="grid gap-1 py-3 sm:grid-cols-[110px_1fr]"><span className="text-xs text-muted">Pending</span><div><p className="font-medium">Operator review</p><p className="mt-1 text-xs text-muted">No command has been approved or run.</p></div></li></ol>
                </InvestigationSection>
              </div>
            </>
          ) : <div className="grid min-h-[610px] place-items-center p-8 text-center"><div><AppIcon name="investigations" size={28} className="mx-auto text-muted" /><p className="mt-3 font-medium">Select an investigation</p><p className="mt-1 text-sm text-muted">Choose a case from the queue to inspect its evidence.</p></div></div>}
        </div>
      </section>
    </div>
  );
}

type AssistantTab = "investigation" | "terminals" | "activity";
type InvestigationSectionId = "incident" | "systems" | "assessment" | "evidence" | "action" | "experts" | "timeline";

function InvestigationSection({ id, label, preview, badge, open, onToggle, children }: {
  id: InvestigationSectionId;
  label: string;
  preview: string;
  badge?: ReactNode;
  open: boolean;
  onToggle: (id: InvestigationSectionId) => void;
  children: ReactNode;
}) {
  return (
    <section className={`overflow-hidden rounded-xl border bg-panel transition-colors ${open ? "border-accent/35" : "border-line"}`}>
      <button type="button" className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-panel2/60" aria-expanded={open} onClick={() => onToggle(id)}>
        <ChevronDown size={16} className={`shrink-0 text-muted transition-transform ${open ? "rotate-0" : "-rotate-90"}`} aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-fg">{label}</span>
            {badge}
          </span>
          {!open && <span className="mt-0.5 block truncate text-xs text-muted">{preview}</span>}
        </span>
      </button>
      {open && <div className="border-t border-line px-4 py-4">{children}</div>}
    </section>
  );
}

function ConnectedTerminals() {
  const { session, terminal } = useConsole();
  const [system, setSystem] = useState("TMF");
  const systems = ["Pathway-02", "TMF", "Storage-03"];
  const fallback: Record<string, string[]> = {
    "Pathway-02": ["Connected to Pathway monitor (simulated)", "Status: degraded", "Server class SETTLE-SC: running with warnings"],
    TMF: ["Connected to TMF monitor (simulated)", "Audit trail capacity used: 62%", "No approved diagnostic has run in this session."],
    "Storage-03": ["Connected to storage monitor (simulated)", "Path errors: above baseline", "Mirrored volume state: online"],
  };
  const lines = system === "TMF" && terminal.length > 0 ? terminal.map((line) => humanizeEnvironmentText(line.text)) : (fallback[system] ?? []);

  return (
    <div className="p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Connected system terminals</h3>
          <p className="mt-1 text-xs text-muted">Open a scoped terminal without leaving the incident.</p>
        </div>
        <span className="status-chip status-healthy">3 connected</span>
      </div>
      <div className="mt-4 flex gap-1 overflow-x-auto border-b border-line">
        {systems.map((item) => <button key={item} type="button" className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium ${system === item ? "border-accent text-accent" : "border-transparent text-muted hover:text-fg"}`} onClick={() => setSystem(item)}>{item}</button>)}
      </div>
      <div className="mt-4 overflow-hidden rounded-xl border border-line bg-[#05080a] text-[#a9e8bd]">
        <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-4 py-3 text-xs text-white/65">
          <TerminalSquare size={15} />
          <strong className="text-white">{system}</strong>
          <span>· {environmentName(session?.node_display)}</span>
          <span className="ml-auto rounded-full border border-emerald-400/30 px-2 py-0.5 text-emerald-300">Read-only</span>
        </div>
        <pre className="min-h-[280px] overflow-auto p-4 font-mono text-[13px] leading-6">{lines.join("\n")}</pre>
        <div className="border-t border-white/10 px-4 py-3 text-xs text-white/55">Approved AI diagnostics appear here with their output and source record.</div>
      </div>
    </div>
  );
}

function IncidentActivity() {
  const events = [
    ["Now", "AI assessment updated", "Four verified evidence records correlated."],
    ["2 min ago", "Warning detected", "Audit capacity crossed the watch threshold."],
    ["3 min ago", "Expert pattern matched", "Quarter-end settlement pattern matched with moderate confidence."],
    ["8 min ago", "Metric trend changed", "Audit capacity began rising above its hourly baseline."],
  ];
  return <ol className="divide-y divide-line p-4 sm:p-5">{events.map(([time, title, detail]) => <li key={time} className="grid gap-1 py-4 sm:grid-cols-[100px_1fr]"><span className="text-xs text-muted">{time}</span><div><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs text-muted">{detail}</p></div></li>)}</ol>;
}

function AssistantPage() {
  const { messages } = useConsole();
  const [tab, setTab] = useState<AssistantTab>("investigation");
  const [openSections, setOpenSections] = useState<Set<InvestigationSectionId>>(new Set(["incident"]));

  useEffect(() => {
    if (messages.length > 0) setOpenSections(new Set(["assessment"]));
  }, [messages.length]);

  const toggle = (id: InvestigationSectionId) => setOpenSections((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <div className="flex h-full min-h-[680px] flex-col">
      <SectionTitle eyebrow="Advisory only" title="AI troubleshooting assistant" description="Investigate one incident at a time with operator-controlled diagnostics." />
      <section className="flex min-h-[610px] flex-1 flex-col overflow-hidden rounded-xl border border-line bg-panel">
        <header className="border-b border-line px-4 pt-4 sm:px-5">
          <div className="flex flex-wrap items-start justify-between gap-3 pb-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">INC-1042</h3><span className="status-chip status-warning">Warning</span><span className="status-chip bg-accent/10 text-accent">Under investigation</span></div>
              <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-[minmax(260px,1.5fr)_minmax(150px,0.75fr)_minmax(150px,0.75fr)]">
                <div className="rounded-xl border border-line bg-panel2/60 px-3 py-2"><dt className="font-medium text-muted">Alert</dt><dd className="mt-0.5 font-semibold text-fg">Master audit trail nearing overflow threshold</dd></div>
                <div className="rounded-xl border border-line bg-panel2/60 px-3 py-2"><dt className="font-medium text-muted">Affected system</dt><dd className="mt-0.5 font-semibold text-fg">Pathway-02</dd></div>
                <div className="rounded-xl border border-line bg-panel2/60 px-3 py-2"><dt className="font-medium text-muted">First detected</dt><dd className="mt-0.5 font-semibold text-fg">2 minutes ago</dd></div>
              </dl>
            </div>
            <span className="text-xs text-muted">Evidence window: last 60 minutes</span>
          </div>
          <nav className="flex gap-1 overflow-x-auto" aria-label="AI assistant workspace">
            {(["investigation", "terminals", "activity"] as const).map((item) => <button key={item} type="button" className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium capitalize ${tab === item ? "border-accent text-accent" : "border-transparent text-muted hover:text-fg"}`} onClick={() => setTab(item)}>{item === "investigation" ? <AppIcon name="investigations" size={16} /> : item === "terminals" ? <TerminalSquare size={16} /> : <Clock3 size={16} />}{item === "terminals" ? "Connected terminals" : item}{item === "terminals" && <span className="rounded-full bg-panel2 px-1.5 text-[10px]">3</span>}</button>)}
          </nav>
        </header>

        <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="scroll min-h-0 overflow-y-auto bg-panel2/25">
            {tab === "investigation" && <div className="space-y-2 p-3 sm:p-4">
            <InvestigationSection id="incident" label="Incident" preview="Master audit trail nearing overflow threshold." badge={<span className="status-chip status-warning">Warning</span>} open={openSections.has("incident")} onToggle={toggle}>
              <p className="text-base font-semibold">Master audit trail nearing overflow threshold.</p><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Active audit trail capacity is 62% and rising toward the configured 80% overflow threshold. No service interruption has been confirmed.</p><div className="mt-3 grid gap-3 text-xs sm:grid-cols-3"><div><span className="block text-muted">Current usage</span><strong className="mt-0.5 block text-fg">62%</strong></div><div><span className="block text-muted">Overflow threshold</span><strong className="mt-0.5 block text-fg">80%</strong></div><div><span className="block text-muted">Environment</span><strong className="mt-0.5 block text-fg">Primary Production</strong></div></div>
            </InvestigationSection>
            <InvestigationSection id="systems" label="Affected systems" preview="Pathway-02 and TMF" badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">2 systems</span>} open={openSections.has("systems")} onToggle={toggle}>
              <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-line bg-panel2/50 p-3"><p className="font-medium">Pathway-02</p><p className="mt-1 text-xs text-muted">Settlement application · degraded</p></div><div className="rounded-lg border border-line bg-panel2/50 p-3"><p className="font-medium">TMF</p><p className="mt-1 text-xs text-muted">Transaction management · warning</p></div></div>
            </InvestigationSection>
            <InvestigationSection id="assessment" label="AI assessment" preview="A transaction may be preventing audit-file reuse." badge={<span className="status-chip status-warning">Moderate confidence</span>} open={openSections.has("assessment")} onToggle={toggle}>
              <ChatPane showComposer={false} />
            </InvestigationSection>
            <InvestigationSection id="evidence" label="Evidence" preview="4 verified records from live, manual and expert sources" badge={<span className="status-chip status-healthy">4 verified</span>} open={openSections.has("evidence")} onToggle={toggle}>
              <ul className="space-y-3 text-sm"><li className="flex items-start justify-between gap-3"><span>Audit capacity is 62% and rising.</span><span className="text-xs text-muted">Live metric</span></li><li className="flex items-start justify-between gap-3"><span>TMF event 185 occurred twice.</span><span className="text-xs text-muted">EMS simulator</span></li><li className="flex items-start justify-between gap-3"><span>Quarter-end transaction pattern matched.</span><span className="text-xs text-muted">Expert knowledge</span></li></ul>
            </InvestigationSection>
            <InvestigationSection id="action" label="Recommended action" preview="Run a read-only audit-trail diagnostic." badge={<span className="status-chip status-healthy">Read-only check</span>} open={openSections.has("action")} onToggle={toggle}>
              <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-medium">Identify which transaction is holding the audit file.</p><p className="mt-1 text-sm text-muted">The check is allowlisted, read-only and requires operator approval.</p><code className="mt-3 block rounded-lg bg-[#05080a] px-3 py-2 text-sm text-[#7ee2a1]">TMFCOM STATUS AUDITTRAIL, DETAIL</code></div><button type="button" className="btn btn-primary" onClick={() => setOpenSections(new Set(["assessment"]))}>Review with AI <ChevronRight size={14} /></button></div>
            </InvestigationSection>
            <InvestigationSection id="experts" label="Expert knowledge" preview="Maria Rossi and Raj Patel" badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">2 experts</span>} open={openSections.has("experts")} onToggle={toggle}>
              <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-line p-3"><p className="font-medium">Maria Rossi</p><p className="mt-1 text-xs text-muted">24 years · TMF and audit trails · preserved knowledge</p></div><div className="rounded-lg border border-line p-3"><p className="font-medium">Raj Patel</p><p className="mt-1 text-xs text-muted">15 years · Pathway and TMF · on call</p></div></div>
            </InvestigationSection>
            <InvestigationSection id="timeline" label="Incident timeline" preview="6 recorded events" badge={<span className="rounded-full bg-panel2 px-2 py-0.5 text-[11px] text-muted">6 events</span>} open={openSections.has("timeline")} onToggle={toggle}>
              <IncidentActivity />
            </InvestigationSection>
            </div>}
            {tab === "terminals" && <ConnectedTerminals />}
            {tab === "activity" && <IncidentActivity />}
          </div>
          <aside className="border-t border-line bg-panel lg:border-l lg:border-t-0" aria-label="Ask CAIL about this incident">
            <AssistantComposer side />
          </aside>
        </div>
      </section>
    </div>
  );
}

type KnowledgeEntry = {
  id: string;
  title: string;
  summary: string;
  guidance: string;
  source: "Manual" | "Procedure" | "Expert experience" | "Incident learning";
  sourceName: string;
  appliesTo: string[];
  maintainer: string;
  contributor?: string;
  contributorTitle?: string;
  status: "Approved" | "Reviewed" | "Needs review";
  lastReviewed: string;
  nextReview: string;
  version: string;
  evidence: string[];
  relatedSystems: string[];
  relatedIncidents: string[];
};

const KNOWLEDGE_ENTRIES: KnowledgeEntry[] = [
  { id: "doc:TMF-Reference:ch121.185", title: "Audit File Pinned — Event 185", summary: "Explains why an audit trail file cannot be released while its writing transaction remains active.", guidance: "Confirm the owning transaction and its state before considering any intervention. The file remains pinned until the transaction commits or is safely aborted.", source: "Manual", sourceName: "TMF Reference Manual", appliesTo: ["All environments", "TMF", "NonStop L/J-series"], maintainer: "Production Operations", status: "Approved", lastReviewed: "15 Oct 2026", nextReview: "15 Jan 2027", version: "TMF-REF · chapter 121", evidence: ["TMF event 185 definition", "Approved vendor documentation"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-1042", "INC-2291"] },
  { id: "doc:TMF-Reference:ch121.187", title: "Audit Trail Capacity Critical — Event 187", summary: "Describes the critical-capacity condition that can prevent new transactions from beginning.", guidance: "Treat the condition as time-sensitive. Identify long-running transactions and validate application impact before a controlled response is approved.", source: "Manual", sourceName: "TMF Reference Manual", appliesTo: ["All environments", "TMF", "NonStop L/J-series"], maintainer: "Production Operations", status: "Approved", lastReviewed: "15 Oct 2026", nextReview: "15 Jan 2027", version: "TMF-REF · chapter 121", evidence: ["TMF event 187 definition", "Approved vendor documentation"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-1042"] },
  { id: "doc:TMF-Reference:ch4.status-audittrail", title: "Check Audit Trail Status", summary: "Read-only procedure for checking audit capacity and identifying pinned audit files.", guidance: "Review STATUS AUDITTRAIL detail output for capacity, pinned-file state, and the reason each file cannot be released.", source: "Procedure", sourceName: "TMF Reference Manual", appliesTo: ["All environments", "TMF"], maintainer: "Production Operations", status: "Approved", lastReviewed: "17 Oct 2026", nextReview: "17 Jan 2027", version: "TMF-REF · chapter 4", evidence: ["TMFCOM STATUS AUDITTRAIL", "Allowlisted read-only diagnostic"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-1042"] },
  { id: "doc:TMF-Reference:ch4.status-transaction", title: "Check Active Transactions", summary: "Read-only procedure for reviewing transaction identifiers, state, age, and owning process.", guidance: "Use the transaction list to identify unusually old activity. Treat age as an observation, not proof of root cause.", source: "Procedure", sourceName: "TMF Reference Manual", appliesTo: ["All environments", "TMF"], maintainer: "Production Operations", status: "Approved", lastReviewed: "17 Oct 2026", nextReview: "17 Jan 2027", version: "TMF-REF · chapter 4", evidence: ["TMFCOM STATUS TRANSACTION", "Allowlisted read-only diagnostic"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-1042"] },
  { id: "doc:TMF-Reference:ch4.abort-transaction", title: "Controlled Transaction Abort", summary: "Operator-controlled recovery procedure for backing out a named transaction.", guidance: "This is a state-changing action. Confirm the transaction owner, expected application behavior, approval requirements, and rollback implications before execution.", source: "Procedure", sourceName: "TMF Reference Manual", appliesTo: ["Primary Production", "TMF"], maintainer: "Production Operations", status: "Approved", lastReviewed: "12 Oct 2026", nextReview: "12 Jan 2027", version: "TMF-REF · chapter 4", evidence: ["TMFCOM ABORT TRANSACTION", "Human approval required"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-2291"] },
  { id: "doc:TMF-Reference:ch4.status-tmf", title: "Check TMF Service Status", summary: "Read-only procedure for reviewing TMF state, transaction enablement, and active workload.", guidance: "Use the service state to confirm whether TMF is operating normally before investigating individual transactions.", source: "Procedure", sourceName: "TMF Reference Manual", appliesTo: ["All environments", "TMF"], maintainer: "Production Operations", status: "Approved", lastReviewed: "17 Oct 2026", nextReview: "17 Jan 2027", version: "TMF-REF · chapter 4", evidence: ["TMFCOM STATUS TMF", "Allowlisted read-only diagnostic"], relatedSystems: ["Payments-01", "Recovery-01"], relatedIncidents: [] },
  { id: "maria:h7", title: "Quarter-End Transactions Holding Audit Files", summary: "Preserved operational experience linking quarter-end settlement processing to long-running transactions.", guidance: "During quarter-end processing, check the settlement batch transaction before increasing audit capacity or assuming a storage fault.", source: "Expert experience", sourceName: "Structured expert interview", appliesTo: ["Primary Production", "TMF", "Quarter-end settlement"], maintainer: "Production Operations", contributor: "Maria Rossi", contributorTitle: "Senior NonStop Operator · retired", status: "Reviewed", lastReviewed: "30 Sep 2026", nextReview: "30 Dec 2026", version: "Knowledge record h7", evidence: ["3 expert endorsements", "Extends TMF event 185 guidance"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-1042"] },
  { id: "maria:h11", title: "Audit Trail Capacity During Quarter-End", summary: "Incident-derived warning that waiting for a quarter-end batch may allow audit capacity to become critical.", guidance: "Use this as an escalation signal, not as proof that every quarter-end transaction should be aborted. The record conflicts with general manual guidance and requires specialist review.", source: "Incident learning", sourceName: "INC-2291 debrief", appliesTo: ["Primary Production", "TMF", "Quarter-end settlement"], maintainer: "Production Operations", contributor: "Maria Rossi", contributorTitle: "Senior NonStop Operator · retired", status: "Needs review", lastReviewed: "30 Sep 2026", nextReview: "Review requested", version: "Knowledge record h11", evidence: ["2019 and 2023 incident observations", "Conflicts with TMF event 187 guidance"], relatedSystems: ["Payments-01", "Pathway-02"], relatedIncidents: ["INC-2291"] },
  { id: "raj:h3", title: "SETTLE-SC Long-Transaction Pattern", summary: "Identifies SETTLE-SC as the Pathway server class historically associated with long settlement transactions.", guidance: "Check SETTLE-SC process and transaction state first, while keeping other server classes in scope until live evidence confirms the pattern.", source: "Expert experience", sourceName: "Specialist referral", appliesTo: ["Primary Production", "Pathway", "Settlement services"], maintainer: "Raj Patel", contributor: "Raj Patel", contributorTitle: "NonStop Systems Specialist", status: "Reviewed", lastReviewed: "2 Oct 2026", nextReview: "2 Jan 2027", version: "Knowledge record h3", evidence: ["Specialist validation", "Extends Pathway server guidance"], relatedSystems: ["Pathway-02", "Reports-01"], relatedIncidents: ["INC-1042"] },
  { id: "lena:h4", title: "Intermittent Disk Path Failures", summary: "Preserved storage experience associating repeated UP-to-HARDDOWN transitions with path components rather than the drive.", guidance: "Inspect the cable, CLIM, and process-pair path before concluding that the physical drive has failed.", source: "Expert experience", sourceName: "Structured expert interview", appliesTo: ["Primary Production", "Storage", "SCF"], maintainer: "Lena Kowalski", contributor: "Lena Kowalski", contributorTitle: "Storage Administrator", status: "Reviewed", lastReviewed: "28 Sep 2026", nextReview: "28 Dec 2026", version: "Knowledge record h4", evidence: ["4 expert endorsements", "Extends SCF storage guidance"], relatedSystems: ["Storage-03"], relatedIncidents: [] },
];

type KnowledgeFilter = "all" | "manuals" | "expert" | "incidents" | "review";

function KnowledgePage() {
  const [filter, setFilter] = useState<KnowledgeFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(KNOWLEDGE_ENTRIES[0].id);
  const [correctionStatus, setCorrectionStatus] = useState<string | null>(null);
  const visible = KNOWLEDGE_ENTRIES.filter((entry) => {
    const matchesQuery = [entry.title, entry.summary, entry.source, entry.sourceName, entry.maintainer, entry.contributor ?? "", ...entry.appliesTo].join(" ").toLowerCase().includes(query.toLowerCase());
    const matchesFilter = filter === "all" || (filter === "manuals" && (entry.source === "Manual" || entry.source === "Procedure")) || (filter === "expert" && entry.source === "Expert experience") || (filter === "incidents" && entry.source === "Incident learning") || (filter === "review" && entry.status === "Needs review");
    return matchesQuery && matchesFilter;
  });
  const selected = visible.find((entry) => entry.id === selectedId) ?? visible[0] ?? null;
  const filters: Array<{ id: KnowledgeFilter; label: string }> = [{ id: "all", label: "All knowledge" }, { id: "manuals", label: "Manuals and procedures" }, { id: "expert", label: "Expert experience" }, { id: "incidents", label: "Incident learnings" }, { id: "review", label: "Needs review" }];
  const statusClass = (status: KnowledgeEntry["status"]) => status === "Needs review" ? "status-warning" : "status-healthy";

  return (
    <div>
      <SectionTitle title="Knowledge library" description="Approved operational guidance and preserved expert experience used to ground CAIL responses." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="relative min-w-[260px] flex-1 sm:max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} /><input className="field h-10 w-full rounded-xl bg-panel pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search guidance, systems, or contributors" /></label>
        <span className="text-xs text-muted">{visible.length} knowledge {visible.length === 1 ? "item" : "items"}</span>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">{filters.map((item) => <button key={item.id} type="button" className={`rounded-full border px-3.5 py-2 text-sm font-medium ${filter === item.id ? "border-accent bg-accent/10 text-accent" : "border-line bg-panel text-muted hover:text-fg"}`} onClick={() => { setFilter(item.id); setCorrectionStatus(null); }}>{item.label}{item.id === "review" && <span className="ml-1.5 rounded-full bg-warn/10 px-1.5 py-0.5 text-[11px] text-warn">1</span>}</button>)}</div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
        <section className="overflow-hidden rounded-xl border border-line bg-panel" aria-label="Knowledge items">
          <div className="divide-y divide-line md:hidden">
            {visible.map((entry) => { const active = selected?.id === entry.id; return <button key={entry.id} type="button" className={`w-full border-l-2 p-4 text-left ${active ? "border-accent bg-accent/[0.045]" : "border-transparent"}`} onClick={() => { setSelectedId(entry.id); setCorrectionStatus(null); }}><span className="flex items-start justify-between gap-3"><span><span className="block font-semibold text-fg">{entry.title}</span><span className="mt-1 block text-xs text-muted">{entry.source} · {entry.maintainer}</span></span><span className={`status-chip shrink-0 ${statusClass(entry.status)}`}>{entry.status}</span></span><span className="mt-2 block text-xs text-muted">Applies to: {entry.appliesTo.join(" · ")}</span></button>; })}
            {visible.length === 0 && <p className="p-6 text-center text-sm text-muted">No knowledge items match the selected filters.</p>}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="border-b border-line bg-panel2/70 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">Knowledge item</th><th className="px-4 py-3 font-medium">Source</th><th className="px-4 py-3 font-medium">Applies to</th><th className="px-4 py-3 font-medium">Review status</th><th className="px-5 py-3 font-medium">Last reviewed</th></tr></thead>
              <tbody className="divide-y divide-line">{visible.map((entry) => { const active = selected?.id === entry.id; return <tr key={entry.id} tabIndex={0} aria-selected={active} className={`cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${active ? "bg-accent/[0.045]" : "hover:bg-panel2/40"}`} onClick={() => { setSelectedId(entry.id); setCorrectionStatus(null); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(entry.id); setCorrectionStatus(null); } }}><td className={`max-w-sm border-l-2 px-4 py-3 pl-5 ${active ? "border-accent" : "border-transparent"}`}><p className="font-semibold text-fg">{entry.title}</p><p className="mt-1 truncate text-xs text-muted">Maintained by {entry.maintainer}</p></td><td className="px-4 py-3 text-muted">{entry.source}</td><td className="px-4 py-3 text-muted"><span className="line-clamp-2">{entry.appliesTo.join(" · ")}</span></td><td className="px-4 py-3"><span className={`status-chip ${statusClass(entry.status)}`}>{entry.status}</span></td><td className="px-5 py-3 text-muted">{entry.lastReviewed}</td></tr>; })}{visible.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-muted">No knowledge items match the selected filters.</td></tr>}</tbody>
            </table>
          </div>
        </section>

        {selected && <KnowledgeDetail entry={selected} correctionStatus={correctionStatus} onRequestReview={() => setCorrectionStatus("Review request added to the knowledge governance queue.")} />}
      </div>
      <p className="mt-4 text-xs text-muted">Only approved or reviewed records can ground CAIL answers. Corrections enter a human review queue before changing searchable knowledge.</p>
    </div>
  );
}

function KnowledgeDetail({ entry, correctionStatus, onRequestReview }: { entry: KnowledgeEntry; correctionStatus: string | null; onRequestReview: () => void }) {
  const statusClass = entry.status === "Needs review" ? "status-warning" : "status-healthy";
  return (
    <aside className="overflow-hidden rounded-xl border border-line bg-panel xl:sticky xl:top-0" aria-label={`${entry.title} details`}>
      <header className="border-b border-line p-5">
        <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium text-accent">Knowledge item</span><span className={`status-chip ${statusClass}`}>{entry.status}</span></div>
        <h3 className="mt-2 text-lg font-semibold leading-6">{entry.title}</h3>
        <p className="mt-2 text-sm leading-6 text-muted">{entry.summary}</p>
      </header>
      <section className="border-b border-line p-5"><h4 className="font-semibold">Operational guidance</h4><p className="mt-2 text-sm leading-6 text-muted">{entry.guidance}</p></section>
      <section className="border-b border-line p-5"><h4 className="font-semibold">Applies to</h4><div className="mt-3 flex flex-wrap gap-2">{entry.appliesTo.map((item) => <span key={item} className="rounded-full bg-panel2 px-2.5 py-1 text-xs text-muted">{item}</span>)}</div></section>
      <section className="border-b border-line p-5">
        <h4 className="font-semibold">Source and provenance</h4>
        <dl className="mt-3 grid gap-x-4 gap-y-3 text-xs sm:grid-cols-2"><div><dt className="text-muted">Source</dt><dd className="mt-0.5 font-medium text-fg">{entry.sourceName}</dd></div><div><dt className="text-muted">Record</dt><dd className="mt-0.5 font-medium text-fg">{entry.version}</dd></div><div><dt className="text-muted">Maintainer</dt><dd className="mt-0.5 font-medium text-fg">{entry.maintainer}</dd></div><div><dt className="text-muted">Contributor</dt><dd className="mt-0.5 font-medium text-fg">{entry.contributor ?? "Approved documentation"}{entry.contributorTitle && <span className="block font-normal text-muted">{entry.contributorTitle}</span>}</dd></div></dl>
      </section>
      <section className="border-b border-line p-5"><div className="grid gap-4 sm:grid-cols-2"><div><h4 className="font-semibold">Supporting evidence</h4><ul className="mt-2 space-y-1.5 text-xs text-muted">{entry.evidence.map((item) => <li key={item}>• {item}</li>)}</ul></div><div><h4 className="font-semibold">Related context</h4><p className="mt-2 text-xs text-muted">Systems: {entry.relatedSystems.join(", ") || "None"}</p><p className="mt-1 text-xs text-muted">Incidents: {entry.relatedIncidents.join(", ") || "None recorded"}</p></div></div></section>
      <section className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold">Review history</h4><p className="mt-1 text-xs text-muted">Last reviewed {entry.lastReviewed} · Next review {entry.nextReview}</p></div><button type="button" className="btn" onClick={onRequestReview}>Suggest correction</button></div>{correctionStatus && <p className="mt-3 rounded-lg border border-ok/25 bg-ok/8 p-3 text-xs text-ok" role="status">{correctionStatus}</p>}</section>
    </aside>
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
      <SectionTitle eyebrow="Synthetic environment" title="Operator training simulator" description="Practice safe investigations without connecting to production." />
      <div className="mb-5 flex items-center gap-3 rounded-xl border border-accent/25 bg-accent/8 p-4 text-sm"><FlaskConical className="shrink-0 text-accent" size={20} /><div><p className="font-medium">Training data only</p><p className="text-xs text-muted">Events, commands, people, and outcomes are fictional demo data.</p></div></div>
      <div className="grid gap-4 md:grid-cols-2">{SCENARIOS.map((scenario, index) => <article key={scenario.id} className="rounded-xl border border-line bg-panel p-5"><div className="flex items-start justify-between gap-3"><span className="grid h-8 w-8 place-items-center text-accent"><AppIcon name="simulator" size={19} /></span><span className="rounded-full bg-panel2 px-2.5 py-1 text-xs text-muted">Scenario {index + 1}</span></div><h3 className="mt-4 text-lg font-semibold">{scenario.title}</h3><p className="mt-2 min-h-10 text-sm leading-5 text-muted">{scenario.description}</p><div className="mt-4 flex items-center gap-4 text-xs text-muted"><span className="inline-flex items-center gap-1"><Gauge size={13} />{scenario.difficulty}</span><span className="inline-flex items-center gap-1"><Clock3 size={13} />{scenario.duration}</span></div><button type="button" className="btn btn-primary mt-5 w-full py-2" disabled={running === scenario.id} onClick={() => void start(scenario.id)}>{running === scenario.id ? "Scenario running" : "Start scenario"}</button></article>)}</div>
      {status && <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok/30 bg-ok/8 p-4 text-sm" role="status"><span className="inline-flex items-center gap-2"><CheckCircle2 size={17} className="text-ok" />{status}</span>{running && <button type="button" className="btn" onClick={() => onNavigate("assistant")}>Open AI Assistant</button>}</div>}
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
        <nav className="flex-1 space-y-1 p-3" aria-label="Primary navigation">{NAV.map((item) => { const active = page === item.id; return <button key={item.id} type="button" className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${active ? "bg-accent/10 text-accent" : "text-muted hover:bg-panel2 hover:text-fg"}`} onClick={() => navigate(item.id)}><AppIcon name={item.icon} size={18} />{item.label}{item.id === "investigations" && <span className="ml-auto rounded-full bg-warn/10 px-2 py-0.5 text-[11px] text-warn">1</span>}</button>; })}</nav>
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
          <div className="min-h-full w-full p-4 sm:p-6 lg:p-6 xl:p-8">
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
