import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "crit" | "info" | "muted" | "prod" | "dr";

const TONES: Record<Tone, string> = {
  ok: "border-ok/35 bg-ok/10 text-ok",
  warn: "border-warn/40 bg-warn/10 text-warn",
  crit: "border-crit/45 bg-crit/10 text-crit",
  info: "border-info/35 bg-info/10 text-info",
  muted: "border-line bg-panel2 text-muted",
  prod: "border-prod bg-prod text-white",
  dr: "border-dr bg-dr text-white",
};

export function Badge({
  tone = "muted",
  children,
  title,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-semibold leading-none ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
