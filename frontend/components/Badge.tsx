import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "crit" | "info" | "muted" | "prod" | "dr";

const TONES: Record<Tone, string> = {
  ok: "border-ok/40 bg-ok/5 text-ok",
  warn: "border-warn/45 bg-warn/5 text-warn",
  crit: "border-crit/60 bg-crit/8 text-crit",
  info: "border-info/40 bg-info/5 text-info",
  muted: "border-line bg-transparent text-muted",
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
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-[3px] border px-1.5 py-0.5 text-[11px] font-medium leading-none ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
