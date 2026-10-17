"use client";

import { BookOpen, Monitor, UserRound } from "lucide-react";
import { labelFromId } from "@/lib/format";
import { useConsole } from "@/lib/store";
import type { Lane, Source } from "@/lib/types";

function chipLabel(id: string, s?: Source): string {
  if (!s) return labelFromId(id);
  if (s.kind === "doc") return `${s.part_number ?? s.title}${s.section ? ` · ${s.section}` : ""}`;
  if (s.kind === "heuristic") return `${s.owner_name ?? s.owner} · ${id.split(":")[1] ?? id}`;
  return `${s.command} @ ${s.node}`;
}

export function CitationChip({ sourceId, lane, sources }: { sourceId: string; lane?: Lane; sources?: Source[] }) {
  const { openSource } = useConsole();
  const s = sources?.find((x) => x.id === sourceId);
  const kind: Lane = s ? (s.kind === "heuristic" ? "veteran" : s.kind === "live" ? "live" : "doc") : (lane ?? "doc");
  const Icon = kind === "veteran" ? UserRound : kind === "live" ? Monitor : BookOpen;
  const label = chipLabel(sourceId, s);
  return (
    <button
      type="button"
      className="chip"
      onClick={() => openSource(sourceId, sources)}
      aria-label={`Open source: ${label}`}
      title={sourceId}
    >
      <Icon size={11} aria-hidden="true" className="shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );
}
