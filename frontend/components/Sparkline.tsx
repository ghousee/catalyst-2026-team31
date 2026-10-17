const W = 200;
const H = 40;

export function Sparkline({ values, threshold, color }: { values: number[]; threshold: number; color: string }) {
  const max = Math.max(threshold * 1.1, ...values) * 1.05;
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * W;
  const y = (v: number) => H - (v / max) * H;
  const line = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-10 w-full" role="img" aria-label="Trend over the last hour with threshold line">
      <line x1="0" x2={W} y1={y(threshold)} y2={y(threshold)} stroke="rgb(var(--crit))" strokeWidth="1" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" opacity="0.8" />
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
