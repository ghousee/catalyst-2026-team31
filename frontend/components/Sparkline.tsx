import { useId } from "react";

const W = 200;
const H = 40;

/** Trend line with a soft coloured area under it. The line wipes in on first render (not on every poll). */
export function Sparkline({ values, threshold, color }: { values: number[]; threshold: number; color: string }) {
  const id = useId();
  const max = Math.max(threshold * 1.1, ...values) * 1.05;
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * W;
  const y = (v: number) => H - (v / max) * H;
  const line = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="draw h-full min-h-10 w-full" role="img" aria-label="Trend over the last hour with threshold line">
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.35" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${line} ${W},${H}`} fill={`url(#${id})`} />
      <line x1="0" x2={W} y1={y(threshold)} y2={y(threshold)} stroke="rgb(var(--crit))" strokeWidth="1" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" opacity="0.7" />
      <polyline points={line} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
