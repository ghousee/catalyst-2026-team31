/** ISO -> "02:14:05Z" (deterministic, no locale/timezone, safe for SSR). */
export function fmtTime(iso: string): string {
  const m = /T(\d{2}:\d{2}(?::\d{2})?)/.exec(iso);
  return m ? `${m[1]}Z` : iso;
}

/** ISO -> "2026-10-17 02:14Z" */
export function fmtDateTime(iso: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? `${m[1]} ${m[2]}Z` : iso;
}

/** Pick the line of command output a live claim should rest on. */
export function excerptOf(output: string): string {
  const lines = output.split("\n").map((l) => l.trim()).filter(Boolean);
  const hit = lines.find((l) => /capacity|aborted|STARTED|Busy|SETTLE|Revive|path errors|ACTIVE/i.test(l));
  return hit ?? lines[1] ?? lines[0] ?? "(no output)";
}

export const initials = (name: string): string =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");

export const SUBSYSTEM_OPTIONS = [
  { id: "sub:TMF", label: "TMF" },
  { id: "sub:SCF-STORAGE", label: "Storage" },
  { id: "sub:PATHWAY", label: "Pathway" },
  { id: "sub:PEEK", label: "CPU" },
  { id: "sub:TACL", label: "TACL" },
];
export const SERIES_OPTIONS = [
  { id: "rvu:L", label: "L-series" },
  { id: "rvu:J", label: "J-series" },
];

/** Short chip label derived from a source id when no inline source is available. */
export function labelFromId(id: string): string {
  if (id.startsWith("doc:")) return id.split(":").slice(1).join(" ").replace(/-/g, " ");
  return id;
}

export const relationKind = (rel?: string): { kind: string; target: string } | null => {
  if (!rel) return null;
  const i = rel.indexOf(":");
  return i < 0 ? null : { kind: rel.slice(0, i), target: rel.slice(i + 1) };
};
