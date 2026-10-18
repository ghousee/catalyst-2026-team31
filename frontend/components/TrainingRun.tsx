"use client";

import { CircleCheck, CircleX, GraduationCap, Play, RotateCcw, TerminalSquare } from "lucide-react";
import { useState } from "react";
import { API_URL } from "@/lib/api";
import { CitationChip } from "./CitationChip";

/** Guided sandbox exercise for "Audit trail filling". Nothing is recorded: commands return simulated output
 * (POST /training/run) and the free-text answer is graded against Maria's notes without saving (POST /training/grade). */

type Choice = { label: string; ok: boolean; why: string; source?: string };
type Step =
  | { kind: "choice"; title: string; prompt: string; run?: string; choices: Choice[] }
  | { kind: "write"; title: string; prompt: string; notes: string[] };

const BRIEF = {
  alarm: "IR Prognosis: TMF 185, audit file $AUDIT.ZTMFAT.AA000409 is pinned by an active transaction (second time in 30 minutes)",
  context: "\\PROD · quarter-end settlement night · audit trail at 62% and rising about 0.6% a minute",
  task: "Find out why the audit trail is filling and decide what to do, before it is full (about 40 minutes).",
};

const STEPS: Step[] = [
  {
    kind: "choice", title: "Pick your first check", prompt: "TMF 185 says an audit file is pinned. What do you run first?",
    choices: [
      { label: "TMFCOM STATUS AUDITTRAIL, DETAIL", ok: true, why: "Right: it shows how full the trail is and which file is pinned, and why. Read-only, so it is safe.", source: "doc:TMF-Reference:status-audittrail-output-displayed" },
      { label: "TMFCOM STATUS TRANSACTION", ok: true, why: "Useful, but you do not yet know which file is pinned. Most veterans look at the audit trail first.", source: "doc:TMF-Reference:status-transactions" },
      { label: "TMFCOM ALTER AUDITTRAIL MAT, ADDOVERFLOW $volume", ok: false, why: "Not yet. It changes the system, and Maria's rule is to add overflow only as a bridge, after you have found the pinning transaction.", source: "maria:h11" },
      { label: "Raise FILESPERVOLUME", ok: false, why: "Maria: do not start with FILESPERVOLUME at quarter-end. The active volumes have no room for the new files; it cost BEGINTRANS twice.", source: "maria:h11" },
    ],
  },
  {
    kind: "choice", title: "Read the audit trail", run: "tmfcom.status_audittrail_detail", prompt: "According to the output, what is pinning the audit file?",
    choices: [
      { label: "A long-running transaction", ok: true, why: "Right: 'Pinned reason: long-running transaction'. The file cannot be released until that transaction ends." },
      { label: "The $AUDIT disk is down", ok: false, why: "No: the output shows a pinned file, not a disk error. A down volume would show DISK messages and a different state." },
      { label: "TMF is stopped", ok: false, why: "No: if TMF were stopped you would see that in STATUS TMF and no new transactions at all." },
    ],
  },
  {
    kind: "choice", title: "Find the transaction", run: "tmfcom.status_transaction", prompt: "Which transaction is it, and who owns it?",
    choices: [
      { label: "The SETTLE-SC settlement batch, active for 3h27m", ok: true, why: "Right: the quarter-end settlement batch holds one transaction open for hours. That is Maria's pattern exactly.", source: "maria:h7" },
      { label: "A user TERM session that just started", ok: false, why: "No: the oldest active transaction is hours old and owned by $SETL1 (SETTLE-SC), not a new session." },
      { label: "There is no active transaction", ok: false, why: "No: STATUS TRANSACTION lists 3 active, and the oldest is the one in the audit trail output." },
    ],
  },
  {
    kind: "write", title: "Decide", notes: ["maria:h7", "maria:h11"],
    prompt: "You have about 40 minutes before the trail is full. What do you do now, and what do you NOT do? Write it in your own words.",
  },
];

const post = async <T,>(path: string, body: unknown): Promise<T> => {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
};

interface Graded { score: number; feedback: string; veterans: { note_id: string; owner_name: string; call_text: string; why_text: string; not_when_text: string }[] }

export function TrainingRun({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(-1); // -1 = brief, STEPS.length = debrief
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [outputs, setOutputs] = useState<Record<number, string>>({});
  const [answer, setAnswer] = useState("");
  const [graded, setGraded] = useState<Graded | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const s = STEPS[step];
  const reset = () => { setStep(-1); setPicked({}); setOutputs({}); setAnswer(""); setGraded(null); setErr(null); };
  const run = async (template: string) => {
    setBusy(true); setErr(null);
    try { setOutputs((o) => ({ ...o, [step]: "" })); const r = await post<{ output: string }>("/training/run", { template_id: template }); setOutputs((o) => ({ ...o, [step]: r.output })); }
    catch { setErr("Could not run the simulated check."); }
    finally { setBusy(false); }
  };
  const submit = async (notes: string[]) => {
    setBusy(true); setErr(null);
    try { setGraded(await post<Graded>("/training/grade", { note_ids: notes, answer })); }
    catch { setErr("Could not grade the answer. Is the API running?"); }
    finally { setBusy(false); }
  };
  const right = Object.entries(picked).filter(([i, c]) => (STEPS[+i] as Extract<Step, { kind: "choice" }>).choices[c]?.ok).length;

  return (
    <section aria-label="Guided exercise: Audit trail filling" className="rise mt-5 rounded-2xl border border-sky/40 bg-panel p-5 shadow-soft">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <span className="icon-chip"><GraduationCap size={18} aria-hidden="true" /></span>
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-lg font-semibold text-head">Audit trail filling · guided exercise</h3>
          <p className="text-xs text-muted">Sandbox: nothing you do here is recorded, and commands only return simulated output.</p>
        </div>
        <ol className="flex items-center gap-1.5" aria-label="Progress">
          {[-1, ...STEPS.map((_, i) => i), STEPS.length].map((i) => (
            <li key={i} className={`h-2 w-6 rounded-full ${i < step ? "bg-ok" : i === step ? "bg-accent" : "bg-line"}`} aria-current={i === step ? "step" : undefined} />
          ))}
        </ol>
        <button type="button" className="btn" onClick={onClose}>Close</button>
      </header>

      {step === -1 && (
        <div className="space-y-3">
          <div className="rounded-xl border border-crit/30 bg-crit/5 p-3">
            <p className="text-[11px] font-bold uppercase tracking-wide text-crit">Alarm</p>
            <p className="mt-1 text-[14px] font-semibold text-head">{BRIEF.alarm}</p>
            <p className="mt-1 text-xs text-muted">{BRIEF.context}</p>
          </div>
          <p className="text-[14px]"><strong>Your task:</strong> {BRIEF.task}</p>
          <p className="text-xs text-muted">4 steps: pick a first check, read two simulated outputs, then decide. You will see what a veteran would do at the end.</p>
          <button type="button" className="btn btn-primary" onClick={() => setStep(0)}><Play size={14} aria-hidden="true" />Begin</button>
        </div>
      )}

      {s && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Step {step + 1} of {STEPS.length} · {s.title}</p>
          {s.kind === "choice" && s.run && (
            <div className="space-y-2">
              {outputs[step] === undefined ? (
                <button type="button" className="btn" disabled={busy} onClick={() => void run(s.run!)}>
                  <TerminalSquare size={14} aria-hidden="true" />Run {s.run === "tmfcom.status_audittrail_detail" ? "TMFCOM STATUS AUDITTRAIL, DETAIL" : "TMFCOM STATUS TRANSACTION"} (simulated)
                </button>
              ) : (
                <pre className="term-block overflow-x-auto px-3 py-2 text-[13px]">{outputs[step] || "Running…"}</pre>
              )}
            </div>
          )}
          {(s.kind === "write" || !s.run || outputs[step]) && <p className="text-[14.5px] font-semibold text-head">{s.prompt}</p>}

          {s.kind === "choice" && (!s.run || outputs[step]) && (
            <ul className="grid gap-2 md:grid-cols-2">
              {s.choices.map((c, i) => {
                const chosen = picked[step] === i;
                const done = picked[step] !== undefined;
                return (
                  <li key={c.label}>
                    <button type="button" disabled={done}
                      className={`w-full rounded-xl border p-3 text-left text-[13.5px] transition ${chosen ? (c.ok ? "border-ok bg-ok/10" : "border-crit bg-crit/10") : "border-line bg-panel hover:border-accent"} ${done && !chosen ? "opacity-60" : ""}`}
                      onClick={() => setPicked((p) => ({ ...p, [step]: i }))}>
                      <span className={c.label.startsWith("TMFCOM") ? "font-mono" : ""}>{c.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {s.kind === "choice" && picked[step] !== undefined && (() => {
            const c = s.choices[picked[step]];
            return (
              <div className={`flex items-start gap-2 rounded-xl border p-3 text-[13px] ${c.ok ? "border-ok/40 bg-ok/5" : "border-crit/40 bg-crit/5"}`} role="status">
                {c.ok ? <CircleCheck size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden="true" /> : <CircleX size={16} className="mt-0.5 shrink-0 text-crit" aria-hidden="true" />}
                <div className="space-y-1"><p><strong>{c.ok ? "Good call." : "Not this one."}</strong> {c.why}</p>{c.source && <CitationChip sourceId={c.source} lane={c.source.startsWith("doc:") ? "doc" : "veteran"} />}</div>
              </div>
            );
          })()}

          {s.kind === "write" && (
            <div className="space-y-2">
              <textarea className="field min-h-[90px] w-full" value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!!graded || busy}
                placeholder="e.g. what you check, what you fix first, and what you would avoid" aria-label="Your decision" />
              {!graded && <button type="button" className="btn btn-primary" disabled={busy || answer.trim().split(/\s+/).length < 3} onClick={() => void submit(s.notes)}>{busy ? "Grading…" : "Submit"}</button>}
              {graded && (
                <div className="space-y-3 rounded-xl border border-line bg-panel2 p-3 text-[13px]" role="status">
                  <p><span className={`pill ${graded.score === 2 ? "!text-ok" : graded.score === 1 ? "!text-warn" : "!text-crit"}`}>{graded.score === 2 ? "Got it" : graded.score === 1 ? "Partly" : "Missed"}</span> {graded.feedback}</p>
                  {graded.veterans.map((v) => (
                    <div key={v.note_id} className="border-l-2 border-warn pl-3">
                      <p className="text-xs font-semibold text-muted">What {v.owner_name.split(" ")[0]} would do <CitationChip sourceId={v.note_id} lane="veteran" /></p>
                      <p>{v.call_text}</p>
                      {v.why_text && <p className="text-muted"><strong className="text-fg">Why:</strong> {v.why_text}</p>}
                      {v.not_when_text && <p className="text-muted"><strong className="text-fg">Not when:</strong> {v.not_when_text}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {err && <p role="alert" className="text-sm text-crit">{err}</p>}
          {((s.kind === "choice" && picked[step] !== undefined) || (s.kind === "write" && graded)) && (
            <button type="button" className="btn btn-primary" onClick={() => setStep(step + 1)}>{step === STEPS.length - 1 ? "See debrief" : "Next step"}</button>
          )}
        </div>
      )}

      {step === STEPS.length && (
        <div className="space-y-3 text-[13.5px]">
          <p className="font-display text-lg font-semibold text-head">Debrief</p>
          <p>Checks: <strong>{right} of 3</strong> right first time · Decision: <strong>{graded ? ["Missed", "Partly", "Got it"][graded.score] : "not answered"}</strong></p>
          <ol className="list-decimal space-y-1 pl-5">
            <li>TMF 185 twice at quarter-end with the trail rising is Maria&rsquo;s warning pattern: about 40 minutes before TMF 187 (audit trail critically full).</li>
            <li>Read-only checks first: STATUS AUDITTRAIL shows what is pinned; STATUS TRANSACTION shows the settlement batch holding it.</li>
            <li>Resolve the pinning transaction first. Overflow volumes are only a bridge; FILESPERVOLUME is the wrong first move on \PROD at quarter-end.</li>
          </ol>
          <p className="flex flex-wrap items-center gap-2 text-xs text-muted">Sources:
            <CitationChip sourceId="maria:h7" lane="veteran" /><CitationChip sourceId="maria:h11" lane="veteran" />
            <CitationChip sourceId="doc:TMF-Reference:status-audittrail-output-displayed" lane="doc" /><CitationChip sourceId="doc:TMF-Reference:status-transactions" lane="doc" />
          </p>
          <p className="text-xs text-muted">Sandbox: nothing from this run was saved to your learning map or to Synapse.</p>
          <button type="button" className="btn" onClick={reset}><RotateCcw size={14} aria-hidden="true" />Try again</button>
        </div>
      )}
    </section>
  );
}
