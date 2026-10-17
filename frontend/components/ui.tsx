"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/** Category hues. Values are CSS variables from globals.css, so both themes work. */
export type Hue = "sky" | "teal" | "amber" | "rose" | "indigo" | "green" | "violet" | "crit";
const HUE: Record<Hue, string> = {
  sky: "--sky", teal: "--sub-pathway", amber: "--sub-tacl", rose: "--sub-peek",
  indigo: "--sub-tmf", green: "--sub-scf", violet: "--sub-fup", crit: "--crit",
};
export const hueStyle = (h: Hue): CSSProperties => ({ ["--c" as string]: `var(${HUE[h]})` });

const SUB_HUES: Array<[string, string]> = [
  ["TMF", "--sub-tmf"], ["PATHWAY", "--sub-pathway"], ["SCF", "--sub-scf"], ["STORAGE", "--sub-scf"],
  ["TACL", "--sub-tacl"], ["PEEK", "--sub-peek"], ["MEASURE", "--sub-measure"], ["FUP", "--sub-fup"],
];

/** Coloured subsystem pill (TMF, Pathway, SCF Storage, TACL, PEEK, Measure, FUP). The text label always stays. */
export function SubPill({ name, className = "" }: { name: string; className?: string }) {
  const key = name.toUpperCase();
  const v = SUB_HUES.find(([k]) => key.includes(k))?.[1] ?? "--sub-other";
  return <span className={`pill ${className}`} style={{ ["--c" as string]: `var(${v})` }}>{name}</span>;
}

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Number that counts up to `value` (and between values as it changes). Shows the final number at once with reduced motion. */
export function CountUp({ value, suffix = "", ms = 800 }: { value: number; suffix?: string; ms?: number }) {
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (reduced()) { setShown(value); from.current = value; return; }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const v = a + (value - a) * (1 - Math.pow(1 - t, 3));
      from.current = v;
      setShown(v);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return <>{Math.round(shown)}{suffix}</>;
}

export const Skeleton = ({ className = "h-6 w-12" }: { className?: string }) => <span aria-hidden="true" className={`skeleton align-middle ${className}`} />;

/** Gradient header band at the top of each page, with two slowly drifting soft shapes. */
export function PageHeader({ title, description, icon, aside }: { title: string; description?: ReactNode; icon?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="rise relative mb-5 overflow-hidden rounded-2xl border border-sky/25 bg-gradient-to-r from-skysoft via-panel to-panel px-5 py-4 shadow-soft">
      <span aria-hidden="true" className="drift pointer-events-none absolute -right-8 -top-12 h-40 w-40 rounded-full bg-sky/20 blur-2xl" />
      <span aria-hidden="true" className="drift pointer-events-none absolute -bottom-14 right-40 h-32 w-32 rounded-full bg-[rgb(var(--sub-pathway)/0.16)] blur-2xl [animation-delay:-4s]" />
      <div className="relative flex items-center gap-3">
        {icon && <span className="icon-chip" style={hueStyle("sky")}>{icon}</span>}
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-semibold tracking-tight text-head">{title}</h2>
          {description && <p className="mt-0.5 max-w-3xl text-[13px] text-muted">{description}</p>}
        </div>
        {aside && <div className="shrink-0">{aside}</div>}
      </div>
    </header>
  );
}

/** Tinted stat card: coloured icon chip, big number, one short note. `value` may be a CountUp. */
export function StatCard({ label, value, note, icon, hue = "sky", alert = false }: { label: string; value: ReactNode; note: ReactNode; icon: ReactNode; hue?: Hue; alert?: boolean }) {
  return (
    <div className="tint lift min-w-0 rounded-2xl border p-4 shadow-soft" style={hueStyle(hue)}>
      <div className="flex items-start justify-between gap-2">
        <dt className="text-[12.5px] font-semibold text-muted">{label}</dt>
        <span className="icon-chip">{icon}</span>
      </div>
      <dd className="mt-1 flex items-center gap-2 font-display text-[32px] font-semibold leading-none tracking-tight text-head">
        {value}
        {alert && <span className="live-dot text-crit" aria-hidden="true" />}
      </dd>
      <dd className="mt-2 line-clamp-2 text-[12px] leading-4 text-muted" title={typeof note === "string" ? note : undefined}>{note}</dd>
    </div>
  );
}

/** Titled card panel used across pages. `children` scroll if the panel is given a fixed height. */
export function Panel({ title, sub, aside, children, className = "", flush = false }: { title: string; sub?: string; aside?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section aria-label={title} className={`card flex min-h-0 flex-col overflow-hidden ${className}`}>
      <div className="flex shrink-0 items-center gap-3 border-b border-line bg-gradient-to-r from-skysoft/70 to-transparent px-4 py-2.5">
        <h3 className="shrink-0 text-[13.5px] font-semibold text-head">{title}</h3>
        {sub && <p className="truncate text-xs text-muted" title={sub}>{sub}</p>}
        {aside && <div className="ml-auto shrink-0 text-xs text-muted">{aside}</div>}
      </div>
      <div className={`scroll min-h-0 flex-1 overflow-auto ${flush ? "" : "p-4"}`}>{children}</div>
    </section>
  );
}
