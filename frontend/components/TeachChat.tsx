"use client";

import { useState } from "react";
import { admin, subName, type Person, type TeachDraft, type TeachMessage } from "@/lib/admin";

const LABELS: [keyof TeachDraft, string][] = [
  ["trigger_text", "When you see this"],
  ["call_text", "What to do"],
  ["why_text", "Why"],
  ["not_when_text", "When it does NOT apply"],
];

/** Chat where a veteran talks and the assistant asks short follow-ups, then hands back an editable draft. */
export function TeachChat({ persons, subs, onSaved }: { persons: Person[]; subs: string[]; onSaved: () => void }) {
  const [who, setWho] = useState("");
  const [msgs, setMsgs] = useState<TeachMessage[]>([]);
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState<TeachDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const owner = who || persons[0]?.id || "";

  const reset = () => {
    setMsgs([]);
    setDraft(null);
    setInput("");
  };

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || busy) return;
    const next: TeachMessage[] = [...msgs, { role: "veteran", text: input.trim() }];
    setMsgs(next);
    setInput("");
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const t = await admin.teach(owner, next);
      if (t.type === "question") setMsgs([...next, { role: "assistant", text: t.text }]);
      else setDraft(t.draft);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Teach failed");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!draft) return;
    setErr(null);
    try {
      const n = await admin.addNote({ owner_id: owner, entered_by: owner, ...draft });
      setNote(`Saved as draft ${n.id}. Find it under Pending sign-off and approve it to make it live.`);
      reset();
      onSaved();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Save failed");
    }
  };

  const set = (k: keyof TeachDraft, v: string) => setDraft((d) => (d ? { ...d, [k]: v } : d));

  return (
    <div className="space-y-3">
      <label className="block space-y-1 text-[12px] text-muted">
        <span>Who is teaching (they own and sign the note)</span>
        <select className="field w-full" aria-label="Teaching" value={owner} onChange={(e) => { setWho(e.target.value); reset(); }}>
          {persons.map((p) => (
            <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
          ))}
        </select>
      </label>
      <ul className="space-y-2" aria-label="Teach conversation">
        {msgs.length === 0 && <li className="text-[12.5px] text-muted">Tell me something a new operator should know, in your own words.</li>}
        {msgs.map((m, i) => (
          <li key={i} className={`rounded border p-2 text-[13px] ${m.role === "veteran" ? "border-line bg-panel2" : "border-accent/40"}`}>
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{m.role === "veteran" ? "You" : "Assistant"}</span>
            <p>{m.text}</p>
          </li>
        ))}
        {busy && <li className="text-[12.5px] text-muted">Thinking…</li>}
      </ul>
      {!draft && (
        <form onSubmit={send} className="space-y-2">
          <textarea className="field min-h-[64px] w-full" aria-label="Your message" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. On DR, when a path shows DOWN after a CLIM restart, wait 5 minutes before resetting…" />
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary" disabled={busy || !input.trim() || !owner}>Send</button>
            {msgs.length > 0 && <button type="button" className="btn" onClick={reset}>Start over</button>}
          </div>
        </form>
      )}
      {draft && (
        <div className="card space-y-3 p-3">
          <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">Draft (edit anything before saving)</p>
          {LABELS.map(([k, label]) => (
            <label key={k} className="block space-y-1 text-[12px] text-muted">
              <span>{label}</span>
              <textarea className="field min-h-[56px] w-full" value={draft[k]} onChange={(e) => set(k, e.target.value)} />
            </label>
          ))}
          <div className="grid grid-cols-3 gap-3">
            <label className="block space-y-1 text-[12px] text-muted">
              <span>Node</span>
              <select className="field w-full" value={draft.node} onChange={(e) => set("node", e.target.value)}>
                <option value="PROD">\PROD only</option>
                <option value="DR">\DR only</option>
                <option value="ALL">all nodes</option>
              </select>
            </label>
            <label className="block space-y-1 text-[12px] text-muted">
              <span>Subsystem</span>
              <select className="field w-full" value={draft.subsystem} onChange={(e) => set("subsystem", e.target.value)}>
                <option value="">choose…</option>
                {subs.map((s) => (
                  <option key={s} value={s}>{subName(s)}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-[12px] text-muted">
              <span>Kind</span>
              <select className="field w-full" value={draft.kind} onChange={(e) => set("kind", e.target.value)}>
                <option value="note">note</option>
                <option value="warning_pattern">warning pattern</option>
              </select>
            </label>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn btn-primary" disabled={!draft.trigger_text.trim() || !draft.call_text.trim() || !draft.subsystem} onClick={save}>
              Save draft
            </button>
            <button type="button" className="btn" onClick={reset}>Discard</button>
          </div>
        </div>
      )}
      {note && <p role="status" className="text-[12.5px] text-ok">{note}</p>}
      {err && <p role="alert" className="text-[12.5px] text-crit">{err}</p>}
    </div>
  );
}
