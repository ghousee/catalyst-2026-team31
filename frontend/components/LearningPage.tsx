"use client";

import { useState, type ReactNode } from "react";
import { usePolling } from "@/lib/hooks";
import { learning, type LearningMap } from "@/lib/learning";
import { USER_ID } from "@/lib/store";
import { SplitPane } from "./SplitPane";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const when = (ts: string | null) => (ts ? ts.slice(0, 16).replace("T", " ") : "never");

function Tile({ label, value, note }: { label: string; value: number | string; note: string }) {
  return (
    <div className="min-w-0 lg:px-5 lg:first:pl-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="num mt-0.5 text-xl font-medium leading-tight">{value}</dd>
      <dd className="mt-0.5 text-[11.5px] leading-4 text-muted">{note}</dd>
    </div>
  );
}

function Strip({ cols, children }: { cols: string; children: ReactNode }) {
  return <dl className={`grid grid-cols-2 gap-y-4 border-y border-line py-3 lg:gap-y-0 lg:divide-x lg:divide-line ${cols}`}>{children}</dl>;
}

function Panel({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex min-h-0 flex-col overflow-hidden rounded border border-line bg-panel">
      <div className="flex shrink-0 items-baseline gap-3 border-b border-line px-4 py-2">
        <h3 className="shrink-0 text-[13px] font-semibold">{title}</h3>
        {sub && <p className="truncate text-xs text-muted" title={sub}>{sub}</p>}
      </div>
      <div className="scroll min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

const Empty = ({ text }: { text: string }) => <p className="px-4 py-3 text-sm text-muted">{text}</p>;

export function LearningPage() {
  const [user, setUser] = useState(USER_ID);
  const users = usePolling(() => learning.users(), 15000, "learning-users");
  const map = usePolling(() => learning.map(user), 15000, `learning-${user}`);
  const options = users.data?.some((u) => u.user_id === user) ? users.data : [{ user_id: user, questions: 0, last_seen: "" }, ...(users.data ?? [])];
  const data = map.data?.user_id === user ? map.data : null;

  return (
    <div className="flex h-full flex-col">
      <header className="mb-4">
        <h2 className="text-xl font-semibold tracking-tight text-fg">Learning map</h2>
        <p className="mt-1 max-w-3xl text-[13px] text-muted">What this operator has encountered through questions, not a test of what they know. Live from the question log.</p>
      </header>
      <label className="mb-3 flex items-center gap-2 text-sm">
        <span className="font-medium">Operator</span>
        <select className="field h-9 px-3" value={user} onChange={(e) => setUser(e.target.value)} aria-label="Operator">
          {options.map((u) => <option key={u.user_id} value={u.user_id}>{u.user_id} ({u.questions} questions)</option>)}
        </select>
      </label>
      {(users.error || map.error) && (
        <p role="alert" className="mb-3 border-l-2 border-crit pl-3 text-sm text-crit">
          {map.error?.includes("no questions") ? `${user} has not asked anything yet.` : `Learning map unavailable: ${map.error ?? users.error}`}
        </p>
      )}
      {!data && map.loading && <p className="text-sm text-muted">Loading...</p>}
      {data && <Body d={data} />}
    </div>
  );
}

function Body({ d }: { d: LearningMap }) {
  const t = d.totals;
  return (
    <>
      <Strip cols="lg:grid-cols-4">
        <Tile label="Questions asked" value={t.questions} note="logged answers, referrals and clarifications" />
        <Tile label="Subsystems touched" value={`${t.subsystems_touched} of ${t.subsystems_total}`} note="a manual section or veteran note was cited" />
        <Tile label="Veteran notes seen" value={t.notes_seen} note={`from ${d.veterans.length} veteran(s) · ${t.sections_cited} manual sections cited`} />
        <Tile label="Coverage" value={pct(t.coverage)} note={`${t.entities_touched} of ${t.entities_total} events, objects, metrics and commands`} />
      </Strip>
      <div className="mt-3 flex h-[70vh] min-h-[520px]">
        <SplitPane direction="horizontal" id="learning-main" label="subsystem table and the other lists" initial={0.62} minFirst={360} minSecond={260}>
          <Panel title="By subsystem" sub="Coverage = entities touched through cited notes and manual sections / entities in the subsystem">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-panel2 text-xs text-muted">
                <tr>{["Subsystem", "Questions", "Sections", "Notes", "Coverage", "Last seen"].map((c) => <th key={c} className="px-4 py-2 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-line">
                {d.subsystems.map((s) => (
                  <tr key={s.id} className="align-top hover:bg-panel2/40">
                    <td className="px-4 py-2"><p className="font-medium">{s.name}</p><p className="font-mono text-[11px] text-muted">{s.id}</p></td>
                    <td className="px-4 py-2 tabular-nums">{s.questions}</td>
                    <td className="px-4 py-2 tabular-nums">{s.sections_cited}</td>
                    <td className="px-4 py-2 text-xs">{s.notes.length ? s.notes.map((n) => <p key={n.id}><span className="font-mono text-[11px]">{n.id}</span> <span className="text-muted">{n.owner}</span></p>) : <span className="text-muted">none</span>}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2" role="img" aria-label={`${pct(s.coverage)} covered`}>
                        <div className="h-1.5 w-24 overflow-hidden bg-panel2"><div className="h-full bg-accent" style={{ width: pct(s.coverage) }} /></div>
                        <span className="text-xs tabular-nums text-muted">{s.entities_touched}/{s.entities_total}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs text-muted">{when(s.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <SplitPane direction="vertical" id="learning-right" label="never touched and the lists below" initial={0.4} minFirst={120} minSecond={160}>
            <Panel title="Never touched" sub="Subsystems and events no cited source has covered">
              {d.gaps.subsystems.length === 0 && d.gaps.events.length === 0 && <Empty text="Nothing left: every subsystem and event has been touched." />}
              {d.gaps.subsystems.length > 0 && <p className="px-4 pt-3 text-sm"><span className="font-medium">Subsystems:</span> {d.gaps.subsystems.join(", ")}</p>}
              {d.gaps.events.length > 0 && (
                <ul className="divide-y divide-line">
                  {d.gaps.events.map((e) => <li key={e.id} className="px-4 py-2 text-sm">{e.name} <span className="text-xs text-muted">{e.subsystem}</span></li>)}
                </ul>
              )}
            </Panel>
            <SplitPane direction="vertical" id="learning-bottom" label="recent questions and veterans" initial={0.6} minFirst={120} minSecond={100}>
              <Panel title="Recent questions" sub="Last 10">
                <ul className="divide-y divide-line">
                  {d.recent.map((r, i) => (
                    <li key={`${r.ts}-${i}`} className="px-4 py-2 text-sm">
                      <p>{r.question}</p>
                      <p className="text-xs text-muted">{when(r.ts)} · {r.outcome}{r.subsystem ? ` · ${r.subsystem}` : ""}</p>
                    </li>
                  ))}
                </ul>
              </Panel>
              <Panel title="Veterans learned from" sub="Owners of the notes cited to this operator">
                {d.veterans.length === 0 ? <Empty text="No veteran notes cited yet." /> : (
                  <ul className="divide-y divide-line">
                    {d.veterans.map((v) => <li key={v.id} className="flex justify-between px-4 py-2 text-sm"><span>{v.name}</span><span className="text-muted">{v.notes} note(s)</span></li>)}
                  </ul>
                )}
              </Panel>
            </SplitPane>
          </SplitPane>
        </SplitPane>
      </div>
    </>
  );
}
