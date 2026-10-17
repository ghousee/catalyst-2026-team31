"use client";

import { useCallback, useEffect, useState } from "react";
import { admin, subName, type DiffSummary, type DocRow, type Note } from "@/lib/admin";
import { ConsoleProvider } from "@/lib/store";
import { SplitPane } from "./SplitPane";
import { TopBar } from "./TopBar";

function Pane({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="scroll min-h-0 overflow-y-auto p-4">
      <h2 className="mb-3 label !text-fg">{title}</h2>
      {children}
    </section>
  );
}

function Inner() {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [flagged, setFlagged] = useState<Note[]>([]);
  const [diff, setDiff] = useState<DiffSummary | null>(null);
  const [title, setTitle] = useState("");
  const [subsystem, setSubsystem] = useState("");
  const [edition, setEdition] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, n] = await Promise.all([admin.documents(), admin.notes("approved")]);
      setDocs(d);
      setFlagged(n.filter((x) => x.needs_review));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "API unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title);
      form.append("subsystem", subsystem);
      form.append("edition", edition);
      setDiff(await admin.upload(form));
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const subs = [...new Set(docs.map((d) => d.subsystem))];
  return (
    <div className="flex h-screen min-w-[1100px] flex-col">
      <TopBar />
      {err && <p role="alert" className="border-b border-crit/50 px-4 py-2 text-[13px] text-crit">{err}</p>}
      <main className="flex min-h-0 flex-1">
        <SplitPane direction="horizontal" id="documents-main" label="upload and document list" initial={0.4} minFirst={300} minSecond={360}>
          <SplitPane direction="vertical" id="documents-left" label="upload form and last diff" initial={0.55} minFirst={160} minSecond={100}>
            <Pane title="Upload a document">
              <form onSubmit={submit} className="space-y-3 text-[12px] text-muted">
                <label className="block space-y-1">
                  <span>File (.pdf or .txt)</span>
                  <input type="file" accept=".pdf,.txt" required className="field w-full" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                </label>
                <label className="block space-y-1">
                  <span>Title (the same title again = a new edition of the same document)</span>
                  <input className="field w-full" required value={title} onChange={(e) => setTitle(e.target.value)} />
                </label>
                <label className="block space-y-1">
                  <span>Subsystem (pick one, or type a new name to create it)</span>
                  <input className="field w-full" required list="subsystems" value={subsystem} onChange={(e) => setSubsystem(e.target.value)} />
                  <datalist id="subsystems">
                    {subs.map((s) => (
                      <option key={s} value={subName(s)} />
                    ))}
                  </datalist>
                </label>
                <label className="block space-y-1">
                  <span>Edition / version</span>
                  <input className="field w-full" value={edition} onChange={(e) => setEdition(e.target.value)} />
                </label>
                <button type="submit" className="btn btn-primary" disabled={busy || !file}>{busy ? "Loading…" : "Upload"}</button>
              </form>
            </Pane>
            <Pane title="Last upload">
              {!diff && <p className="text-[12.5px] text-muted">Nothing uploaded in this session.</p>}
              {diff && (
                <div className="space-y-1 text-[13px]" role="status">
                  <p className="font-semibold">{diff.title} ({diff.edition}) · {subName(diff.subsystem)}{diff.subsystem_created ? " (new subsystem created)" : ""}</p>
                  <p>added {diff.added} · changed {diff.changed} · unchanged {diff.unchanged} · removed {diff.removed}</p>
                  {diff.changed_ids.length > 0 && <p className="font-mono text-[12px] text-muted">changed: {diff.changed_ids.join(", ")}</p>}
                  {diff.removed_ids.length > 0 && <p className="font-mono text-[12px] text-muted">removed: {diff.removed_ids.join(", ")}</p>}
                  <p>notes flagged for re-check: {diff.notes_flagged.length ? diff.notes_flagged.join(", ") : "none"}</p>
                </div>
              )}
            </Pane>
          </SplitPane>
          <SplitPane direction="vertical" id="documents-right" label="documents and flagged notes" initial={0.6} minFirst={120} minSecond={100}>
            <Pane title="Documents">
              <table className="w-full text-left text-[12.5px]">
                <thead className="label !font-normal">
                  <tr><th className="pb-1">Key</th><th>Title</th><th>Edition</th><th>Subsystem</th><th>Chunks</th><th>Last loaded</th></tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.key} className="border-t border-line align-top">
                      <td className="py-1 font-mono">{d.key}</td>
                      <td>{d.title}</td>
                      <td>{d.edition}</td>
                      <td>{subName(d.subsystem)}</td>
                      <td>{d.chunks}{d.removed ? ` (+${d.removed} removed)` : ""}</td>
                      <td>{d.last_loaded?.slice(0, 16)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Pane>
            <Pane title="Notes needing re-check">
              {flagged.length === 0 && <p className="text-[12.5px] text-muted">No approved note is flagged.</p>}
              <ul className="space-y-2">
                {flagged.map((n) => (
                  <li key={n.id} className="card p-3 text-[13px]">
                    <p className="font-mono text-[12px] text-muted">{n.id} · {n.owner_name}</p>
                    <p>{n.call_text}</p>
                    <p className="font-medium text-warn">⚠ manual changed since this note was signed — needs re-check</p>
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

export function DocumentsPage() {
  return (
    <ConsoleProvider>
      <Inner />
    </ConsoleProvider>
  );
}
