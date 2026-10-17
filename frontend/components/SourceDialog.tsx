"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { fmtDateTime, relationKind } from "@/lib/format";
import { useConsole } from "@/lib/store";
import type { DocSource, HeuristicSource, LiveSource } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import { LaneBadge } from "./LaneBadge";
import { Modal } from "./Modal";

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="grid grid-cols-[110px_1fr] gap-2 py-1">
    <dt className="text-[11px] uppercase tracking-wide text-muted">{k}</dt>
    <dd className="min-w-0 break-words text-[13px]">{children}</dd>
  </div>
);

function Doc({ s }: { s: DocSource }) {
  return (
    <>
      <LaneBadge lane="doc" />
      <h3 className="mt-2 text-base font-semibold">{s.title}</h3>
      <dl className="mt-2 divide-y divide-line">
        {s.part_number && <Row k="Part">{s.part_number}</Row>}
        {s.section && <Row k="Section">{s.section}</Row>}
        {s.applies_to && <Row k="Applies to">{s.applies_to}</Row>}
      </dl>
      <blockquote className="mt-3 rounded border-l-2 border-info bg-panel2 p-3 text-[13px] italic">{s.snippet}</blockquote>
    </>
  );
}

function Veteran({ s }: { s: HeuristicSource }) {
  const name = s.owner_name ?? s.owner;
  const rel = relationKind(s.relation);
  const contradicts = rel?.kind === "contradicts";
  return (
    <>
      <LaneBadge lane="veteran" />
      <div className="mt-2 flex items-center gap-3">
        <Avatar name={name} size={40} />
        <div>
          <h3 className="text-base font-semibold">{name}</h3>
          <p className="text-[12px] text-muted">
            {s.owner_role}
            {s.years ? ` · ${s.years} yrs` : ""}
          </p>
        </div>
      </div>
      {rel && (
        <div
          role={contradicts ? "alert" : undefined}
          className={`mt-3 rounded border p-2 text-[13px] ${
            contradicts ? "border-crit/70 bg-crit/12 font-semibold text-crit" : "border-info/40 bg-info/10 text-info"
          }`}
        >
          {contradicts ? "Contradicts the manual: " : rel.kind === "extends" ? "Extends the manual: " : `${rel.kind}: `}
          <span className="font-mono">{rel.target}</span>
        </div>
      )}
      <p className="mt-3 rounded bg-panel2 p-3 text-[13px]">
        <span className="block text-[11px] uppercase tracking-wide text-muted">Why</span>
        {s.why}
      </p>
      {s.needs_review && (
        <p className="mt-2 text-[12.5px] font-medium text-warn">⚠ manual changed since this note was signed — needs re-check</p>
      )}
      {s.not_when && (
        <p className="mt-2 rounded border border-warn/60 bg-warn/10 p-3 text-[13px]">
          <span className="block text-[11px] uppercase tracking-wide text-muted">Does not apply when</span>
          {s.not_when}
        </p>
      )}
      <dl className="mt-2 divide-y divide-line">
        {s.scope && <Row k="Scope">{s.scope}</Row>}
        {s.captured_via && <Row k="Captured via">{s.captured_via}</Row>}
        {s.captured_at && <Row k="Captured at">{s.captured_at}</Row>}
        {s.provenance && <Row k="Provenance">{s.provenance}</Row>}
        {s.endorsements !== undefined && <Row k="Endorsements">{s.endorsements}</Row>}
        {s.last_validated && <Row k="Last validated">{s.last_validated}</Row>}
      </dl>
    </>
  );
}

function Live({ s }: { s: LiveSource }) {
  return (
    <>
      <LaneBadge lane="live" />
      <h3 className="mt-2 break-words font-mono text-[14px] font-semibold">{s.command}</h3>
      <dl className="mt-2 divide-y divide-line">
        <Row k="Node">{s.node}</Row>
        <Row k="Timestamp">{fmtDateTime(s.ts)}</Row>
      </dl>
      <pre className="mt-3 overflow-x-auto rounded bg-[#05080a] p-3 font-mono text-[12px] text-[#7ee2a1]">{s.excerpt}</pre>
    </>
  );
}

export function SourceDialog() {
  const { sourceView, closeSource } = useConsole();
  return (
    <Modal open={!!sourceView} onClose={closeSource} label="Source details" side>
      <div className="flex h-full flex-col">
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Source</h2>
          <button type="button" className="btn px-2" onClick={closeSource} aria-label="Close source panel">
            <X size={14} aria-hidden="true" />
          </button>
        </header>
        <div className="scroll min-h-0 flex-1 overflow-y-auto p-4">
          {sourceView?.loading && <p className="text-muted">Loading source…</p>}
          {sourceView?.error && (
            <p role="alert" className="text-crit">
              Could not load <span className="font-mono">{sourceView.id}</span>: {sourceView.error}
            </p>
          )}
          {sourceView?.source?.kind === "doc" && <Doc s={sourceView.source} />}
          {sourceView?.source?.kind === "heuristic" && <Veteran s={sourceView.source} />}
          {sourceView?.source?.kind === "live" && <Live s={sourceView.source} />}
          {sourceView && (
            <p className="mt-4 text-[11px] text-muted">
              id <Badge className="font-mono">{sourceView.id}</Badge>
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}
