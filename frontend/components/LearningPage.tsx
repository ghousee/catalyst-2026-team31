"use client";

import { BookMarked, Compass, MessageCircleQuestion, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { admin, type Person } from "@/lib/admin";
import { usePolling } from "@/lib/hooks";
import { learning, type Level, type LearningMap, type LearningSubsystem } from "@/lib/learning";
import { useMe } from "@/lib/me";
import { SplitPane } from "./SplitPane";
import { CountUp, PageHeader, Panel as UiPanel, Skeleton, StatCard, SubPill, hueStyle } from "./ui";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const when = (ts: string | null) => (ts ? ts.slice(0, 16).replace("T", " ") : "never");

const Strip = ({ children }: { children: ReactNode }) => <dl className="stagger grid grid-cols-2 gap-4 lg:grid-cols-4">{children}</dl>;

const Panel = (p: Omit<Parameters<typeof UiPanel>[0], "flush">) => <UiPanel flush {...p} />;

const Empty = ({ text }: { text: string }) => <p className="px-4 py-3 text-sm text-muted">{text}</p>;

export function LearningPage() {
  const me = useMe();
  const [user, setUser] = useState(me.id);
  const [rev, setRev] = useState(0);
  const [sharing, setSharing] = useState(false);
  useEffect(() => setUser(me.id), [me.id]);
  const users = usePolling(() => learning.users(), 15000, "learning-users");
  const map = usePolling(() => learning.map(user), 15000, `learning-${user}-${rev}`);
  const options = users.data?.some((u) => u.user_id === user) ? users.data : [{ user_id: user, questions: 0, last_seen: "" }, ...(users.data ?? [])];
  const data = map.data?.user_id === user ? map.data : null;
  const mine = user === me.id;

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Learning map" icon={<Compass size={18} aria-hidden="true" />} description="What this operator has encountered through questions, next to the starting level they gave themselves. Not a test. Live from the question log." />
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="font-medium">Operator</span>
          <select className="field h-9 px-3" value={user} onChange={(e) => setUser(e.target.value)} aria-label="Operator">
            {options.map((u) => <option key={u.user_id} value={u.user_id}>{u.user_id}{u.user_id === me.id ? " (you)" : ""} ({u.questions} questions)</option>)}
          </select>
        </label>
        {mine && <button type="button" className="btn ml-auto" aria-expanded={sharing} onClick={() => setSharing((s) => !s)}>Share something you found</button>}
      </div>
      {mine && sharing && data && <ShareFinding me={me.id} subs={data.subsystems} onDone={() => setSharing(false)} />}
      {(users.error || map.error) && (
        <p role="alert" className="mb-3 rounded-xl border border-crit/30 bg-crit/10 p-3 text-sm text-crit">Learning map unavailable: {map.error ?? users.error}</p>
      )}
      {!data && map.loading && <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" role="status" aria-label="Loading"><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /></div>}
      {data && data.totals.questions === 0 && (
        <p className="mb-3 rounded-xl border border-sky/30 bg-skysoft p-3 text-sm">
          {mine ? "Welcome. Set your starting level for each subsystem below, then ask the AI Assistant anything; this map fills in as you go." : `${user} has not asked anything yet.`}
        </p>
      )}
      {data && <Body d={data} editable={mine} onLevel={async (sub, level) => { await learning.setLevels(user, { [sub]: level }); setRev((r) => r + 1); }} />}
    </div>
  );
}

const LEVEL_TEXT: Record<Level, string> = { new: "New to it", some: "Know some", confident: "Confident" };

/** A junior writes down something they found; it goes to a senior as a draft, and only goes live once that senior signs. */
function ShareFinding({ me, subs, onDone }: { me: string; subs: LearningSubsystem[]; onDone: () => void }) {
  const [persons, setPersons] = useState<Person[]>([]);
  const [f, setF] = useState({ owner_id: "", subsystem: subs[0]?.id ?? "", node: "ALL", trigger_text: "", call_text: "", why_text: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    admin.persons().then((p) => { setPersons(p); setF((x) => ({ ...x, owner_id: x.owner_id || p[0]?.id || "" })); }).catch(() => setErr("Cannot load seniors"));
  }, []);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      const n = await admin.addNote({ ...f, entered_by: me, kind: "note", not_when_text: "" });
      setMsg(`Sent to ${n.owner_name} as draft ${n.id}. It is used in answers only after they confirm and sign it.`);
      setF({ ...f, trigger_text: "", call_text: "", why_text: "" });
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not send");
    }
  };
  return (
    <form onSubmit={submit} className="card rise mb-4 grid gap-3 p-4 text-[13px] md:grid-cols-2">
      <p className="text-muted md:col-span-2">Found something that worked? Write it down and pick a senior to confirm it. Your name stays on it as the person who found it.</p>
      <label className="space-y-1"><span className="text-xs text-muted">When you see this</span><textarea required className="field min-h-[56px] w-full" value={f.trigger_text} onChange={set("trigger_text")} /></label>
      <label className="space-y-1"><span className="text-xs text-muted">What worked</span><textarea required className="field min-h-[56px] w-full" value={f.call_text} onChange={set("call_text")} /></label>
      <label className="space-y-1 md:col-span-2"><span className="text-xs text-muted">Why you think it works (optional)</span><input className="field w-full" value={f.why_text} onChange={set("why_text")} /></label>
      <div className="flex flex-wrap items-end gap-3 md:col-span-2">
        <label className="space-y-1"><span className="block text-xs text-muted">Subsystem</span><select className="field" value={f.subsystem} onChange={set("subsystem")}>{subs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label className="space-y-1"><span className="block text-xs text-muted">Node</span><select className="field" value={f.node} onChange={set("node")}><option value="ALL">all nodes</option><option value="PROD">\PROD only</option><option value="DR">\DR only</option></select></label>
        <label className="space-y-1"><span className="block text-xs text-muted">Senior to confirm</span><select className="field" value={f.owner_id} onChange={set("owner_id")}>{persons.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <button type="submit" className="btn btn-primary" disabled={!f.owner_id}>Send for sign-off</button>
        <button type="button" className="btn" onClick={onDone}>Close</button>
      </div>
      {msg && <p role="status" className="text-ok md:col-span-2">{msg}</p>}
      {err && <p role="alert" className="text-crit md:col-span-2">{err}</p>}
    </form>
  );
}

function Body({ d, editable, onLevel }: { d: LearningMap; editable: boolean; onLevel: (sub: string, level: Level) => Promise<void> }) {
  const t = d.totals;
  const levels = d.self_levels ?? {};
  return (
    <>
      <Strip>
        <StatCard hue="sky" icon={<MessageCircleQuestion size={18} aria-hidden="true" />} label="Questions asked" value={<CountUp value={t.questions} />} note="logged answers, referrals and clarifications" />
        <StatCard hue="teal" icon={<Compass size={18} aria-hidden="true" />} label="Subsystems touched" value={<span><CountUp value={t.subsystems_touched} /> <span className="text-lg font-medium text-muted">of {t.subsystems_total}</span></span>} note="a manual section or veteran note was cited" />
        <StatCard hue="amber" icon={<Users size={18} aria-hidden="true" />} label="Veteran notes seen" value={<CountUp value={t.notes_seen} />} note={`from ${d.veterans.length} veteran(s) · ${t.sections_cited} manual sections cited`} />
        <StatCard hue="green" icon={<BookMarked size={18} aria-hidden="true" />} label="Coverage" value={<CountUp value={Math.round(t.coverage * 100)} suffix="%" />} note={`${t.entities_touched} of ${t.entities_total} events, objects, metrics and commands`} />
      </Strip>
      <div className="mt-4 flex h-[70vh] min-h-[520px]">
        <SplitPane direction="horizontal" id="learning-main" label="subsystem table and the other lists" initial={0.62} minFirst={360} minSecond={260}>
          <Panel title="By subsystem" sub="Coverage = entities touched through cited notes and manual sections / entities in the subsystem">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-skysoft text-xs text-muted">
                <tr>{["Subsystem", "Said they know", "Questions", "Sections", "Notes", "Coverage", "Last seen"].map((c) => <th key={c} className="px-4 py-2 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-line">
                {d.subsystems.map((s) => (
                  <tr key={s.id} className="align-top transition-colors hover:bg-skysoft/50">
                    <td className="px-4 py-2"><SubPill name={s.name} /><p className="mt-1 font-mono text-[11px] text-muted">{s.id}</p></td>
                    <td className="px-4 py-2 text-xs">
                      {editable ? (
                        <select className="field h-8" aria-label={`Your starting level in ${s.name}`} value={levels[s.id] ?? ""}
                          onChange={(e) => void onLevel(s.id, e.target.value as Level)}>
                          {!levels[s.id] && <option value="">not set</option>}
                          {(Object.keys(LEVEL_TEXT) as Level[]).map((l) => <option key={l} value={l}>{LEVEL_TEXT[l]}</option>)}
                        </select>
                      ) : (
                        <span className={levels[s.id] ? "pill" : "text-muted"} style={hueStyle(levels[s.id] === "confident" ? "green" : levels[s.id] === "some" ? "sky" : "amber")}>{levels[s.id] ? LEVEL_TEXT[levels[s.id]] : "not set"}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 tabular-nums">{s.questions}</td>
                    <td className="px-4 py-2 tabular-nums">{s.sections_cited}</td>
                    <td className="px-4 py-2 text-xs">{s.notes.length ? s.notes.map((n) => <p key={n.id}><span className="font-mono text-[11px]">{n.id}</span> <span className="text-muted">{n.owner}</span></p>) : <span className="text-muted">none</span>}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2" role="img" aria-label={`${pct(s.coverage)} covered`}>
                        <div className="h-2 w-28 overflow-hidden rounded-full bg-panel2"><div className="bar-grow h-full rounded-full bg-gradient-to-r from-sky to-navy2 transition-[width] duration-700" style={{ width: pct(s.coverage) }} /></div>
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
