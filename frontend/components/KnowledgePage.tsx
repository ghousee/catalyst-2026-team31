"use client";

import { useCallback, useEffect, useState } from "react";
import { admin, subName, type ApproveResult, type DocRow, type Note, type Person } from "@/lib/admin";
import { ConsoleProvider } from "@/lib/store";
import { SplitPane } from "./SplitPane";
import { TeachChat } from "./TeachChat";
import { TopBar } from "./TopBar";

const EMPTY = { trigger_text: "", call_text: "", why_text: "", not_when_text: "" };
type Decision = "extends" | "contradicts" | "skipped";

function Pane({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="scroll min-h-0 overflow-y-auto p-4">
      <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-[12px] text-muted">
      <span>{label}</span>
      {children}
    </label>
  );
}

const scope = (n: Note) => `${n.node === "ALL" ? "all nodes" : "\\" + n.node} · ${subName(n.subsystem)} · ${n.kind}`;

function NoteText({ n }: { n: Note }) {
  return (
    <div className="space-y-1 text-[13px]">
      <p className="font-mono text-[12px] text-muted">
        {n.id} · owner {n.owner_name} · entered by {n.entered_by} · {n.captured_via} {n.captured_at} · {scope(n)}
      </p>
      <p><b>When:</b> {n.trigger_text}</p>
      <p><b>Do:</b> {n.call_text}</p>
      {n.why_text && <p><b>Why:</b> {n.why_text}</p>}
      {n.not_when_text && <p><b>Not when:</b> {n.not_when_text}</p>}
    </div>
  );
}

function SignedResult({ r, onChanged }: { r: ApproveResult; onChanged: () => void }) {
  const [decided, setDecided] = useState<Record<string, Decision>>({});
  const [err, setErr] = useState<string | null>(null);
  const decide = async (docId: string, d: Decision) => {
    setErr(null);
    try {
      if (d !== "skipped") await admin.link(r.note.id, docId, d);
      setDecided((p) => ({ ...p, [docId]: d }));
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Link failed");
    }
  };
  return (
    <div className="card mb-3 space-y-2 border-ok/50 p-3" role="status">
      <p className="text-[13px] font-semibold text-ok">Signed and live: {r.note.id} (signed by {r.note.signed_by})</p>
      <div>
        <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">Auto-created links</p>
        <ul className="list-disc pl-5 text-[12.5px]">
          {r.auto_links.map((l, i) => (
            <li key={i} className="font-mono">
              {l.src ? `${l.src} ` : ""}{l.rel} → {l.dst}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">Does this note agree with the manual?</p>
        {r.suggested_sections.length === 0 && <p className="text-[12.5px] text-muted">No manual section suggested.</p>}
        <ul className="space-y-2">
          {r.suggested_sections.map((s) => (
            <li key={s.id} className="rounded border border-line bg-panel2 p-2 text-[12.5px]">
              <p className="font-mono">{s.id}</p>
              <p className="font-medium">{s.section}</p>
              <p className="text-muted">{s.snippet}</p>
              <div className="mt-1.5 flex items-center gap-2">
                <button type="button" className="btn" disabled={!!decided[s.id]} onClick={() => decide(s.id, "extends")}>agrees</button>
                <button type="button" className="btn" disabled={!!decided[s.id]} onClick={() => decide(s.id, "contradicts")}>contradicts</button>
                <button type="button" className="btn" disabled={!!decided[s.id]} onClick={() => decide(s.id, "skipped")}>skip</button>
                {decided[s.id] && <span className="text-[12px] text-muted">{decided[s.id] === "skipped" ? "skipped" : `linked: ${decided[s.id]}`}</span>}
              </div>
            </li>
          ))}
        </ul>
      </div>
      {err && <p role="alert" className="text-[12.5px] text-crit">{err}</p>}
    </div>
  );
}

function Inner() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [subs, setSubs] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Note[]>([]);
  const [approved, setApproved] = useState<Note[]>([]);
  const [signedBy, setSignedBy] = useState<Record<string, string>>({});
  const [results, setResults] = useState<ApproveResult[]>([]);
  const [owner, setOwner] = useState("");
  const [enteredBy, setEnteredBy] = useState("");
  const [kind, setKind] = useState("note");
  const [node, setNode] = useState("PROD");
  const [subsystem, setSubsystem] = useState("");
  const [text, setText] = useState(EMPTY);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, a] = await Promise.all([admin.notes("draft"), admin.notes("approved")]);
      setDrafts(d);
      setApproved(a);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "API unavailable");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const [p, docs] = await Promise.all([admin.persons(), admin.documents()]);
        setPersons(p);
        setOwner((o) => o || p[0]?.id || "");
        setEnteredBy((o) => o || p[0]?.id || "");
        const ids = [...new Set(docs.map((d: DocRow) => d.subsystem))].sort();
        setSubs(ids);
        setSubsystem((s) => s || ids[0] || "");
      } catch (e) {
        setErr(e instanceof Error ? e.message : "API unavailable");
      }
      await refresh();
    })();
  }, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      const n = await admin.addNote({ owner_id: owner, entered_by: enteredBy, kind, node, subsystem, ...text });
      setMsg(`Saved as draft ${n.id}. It needs ${n.owner_name}'s signature before the copilot uses it.`);
      setText(EMPTY);
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Save failed");
    }
  };

  const approve = async (n: Note) => {
    setErr(null);
    try {
      const r = await admin.approve(n.id, signedBy[n.id] ?? n.owner_id);
      setResults((p) => [r, ...p]);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Approve failed");
    }
  };

  const retire = async (n: Note) => {
    try {
      await admin.retire(n.id);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Retire failed");
    }
  };

  const personSelect = (value: string, set: (v: string) => void, label: string) => (
    <select className="field w-full" aria-label={label} value={value} onChange={(e) => set(e.target.value)}>
      {persons.map((p) => (
        <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
      ))}
    </select>
  );
  const ta = (k: keyof typeof EMPTY, req = false) => (
    <textarea className="field min-h-[64px] w-full" required={req} value={text[k]} onChange={(e) => setText({ ...text, [k]: e.target.value })} />
  );

  return (
    <div className="flex h-screen min-w-[1100px] flex-col">
      <TopBar />
      {err && <p role="alert" className="border-b border-crit/60 bg-crit/10 px-4 py-2 text-[13px] text-crit">{err}</p>}
      <main className="flex min-h-0 flex-1">
        <SplitPane direction="horizontal" id="knowledge-main" label="form and notes" initial={0.38} minFirst={300} minSecond={360}>
          <SplitPane direction="vertical" id="knowledge-left" label="teach and add form" initial={0.55} minFirst={160} minSecond={160}>
          <Pane title="Teach">
            <TeachChat persons={persons} subs={subs} onSaved={refresh} />
          </Pane>
          <Pane title="Add knowledge">
            <form onSubmit={submit} className="space-y-3">
              <Field label="Owner (whose knowledge it is; only they can sign it)">{personSelect(owner, setOwner, "Owner")}</Field>
              <Field label="Entered by (who is typing it)">{personSelect(enteredBy, setEnteredBy, "Entered by")}</Field>
              <Field label="Kind">
                <select className="field w-full" value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="note">note</option>
                  <option value="warning_pattern">warning pattern</option>
                </select>
              </Field>
              <Field label="When you see this">{ta("trigger_text", true)}</Field>
              <Field label="What to do">{ta("call_text", true)}</Field>
              <Field label="Why">{ta("why_text")}</Field>
              <Field label="When it does NOT apply">{ta("not_when_text")}</Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Node">
                  <select className="field w-full" value={node} onChange={(e) => setNode(e.target.value)}>
                    <option value="PROD">\PROD only</option>
                    <option value="DR">\DR only</option>
                    <option value="ALL">all nodes</option>
                  </select>
                </Field>
                <Field label="Subsystem">
                  <select className="field w-full" value={subsystem} onChange={(e) => setSubsystem(e.target.value)}>
                    {subs.map((s) => (
                      <option key={s} value={s}>{subName(s)}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <button type="submit" className="btn btn-primary" disabled={!owner || !subsystem}>Save as draft</button>
              {msg && <p role="status" className="text-[12.5px] text-ok">{msg}</p>}
            </form>
          </Pane>
          </SplitPane>
          <SplitPane direction="vertical" id="knowledge-right" label="pending and approved notes" initial={0.5} minFirst={120} minSecond={120}>
            <Pane title="Pending sign-off">
              {results.map((r) => (
                <SignedResult key={r.note.id} r={r} onChanged={refresh} />
              ))}
              {drafts.length === 0 && <p className="text-[12.5px] text-muted">No drafts waiting.</p>}
              <ul className="space-y-3">
                {drafts.map((n) => (
                  <li key={n.id} className="card space-y-2 p-3">
                    <NoteText n={n} />
                    <div className="flex items-center gap-2">
                      <select className="field" aria-label={`Signed by, ${n.id}`} value={signedBy[n.id] ?? n.owner_id}
                        onChange={(e) => setSignedBy({ ...signedBy, [n.id]: e.target.value })}>
                        {persons.map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                      <button type="button" className="btn btn-primary" onClick={() => approve(n)}>Approve &amp; sign</button>
                    </div>
                  </li>
                ))}
              </ul>
            </Pane>
            <Pane title="Approved notes">
              {approved.length === 0 && <p className="text-[12.5px] text-muted">None.</p>}
              <ul className="space-y-3">
                {approved.map((n) => (
                  <li key={n.id} className="card space-y-1.5 p-3">
                    <NoteText n={n} />
                    <p className="text-[12px] text-muted">
                      signed by {n.signed_by} {n.signed_at} · links: {n.links.filter((l) => l.rel !== "applies_to").map((l) => `${l.rel} ${l.dst}`).join(", ") || "none"}
                    </p>
                    {n.needs_review && (
                      <p className="text-[12.5px] font-medium text-warn">⚠ manual changed since this note was signed — needs re-check</p>
                    )}
                    <button type="button" className="btn" onClick={() => retire(n)}>Retire</button>
                  </li>
                ))}
              </ul>
            </Pane>
          </SplitPane>
        </SplitPane>
      </main>
    </div>
  );
}

export function KnowledgePage() {
  return (
    <ConsoleProvider>
      <Inner />
    </ConsoleProvider>
  );
}
