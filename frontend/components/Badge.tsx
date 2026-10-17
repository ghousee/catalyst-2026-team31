import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "crit" | "info" | "muted" | "prod" | "dr";

const TONES: Record<Tone, string> = {
  ok: "border-ok/50 bg-ok/12 text-ok",
  warn: "border-warn/50 bg-warn/12 text-warn",
  crit: "border-crit/60 bg-crit/15 text-crit",
  info: "border-info/50 bg-info/12 text-info",
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
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-semibold leading-none ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
