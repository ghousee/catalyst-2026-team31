import { environmentName } from "@/lib/format";

export function NodeBadge({ display, large = false }: { display: string; large?: boolean }) {
  const prod = display.toUpperCase().includes("PROD");
  const size = large ? "px-3 py-1 text-lg" : "px-1.5 py-0.5 text-[11px]";
  return (
    <span
      className={`inline-flex items-center rounded font-mono font-bold tracking-wide text-white ${size} ${prod ? "bg-prod" : "bg-dr"}`}
      aria-label={`Environment ${environmentName(display)}`}
      title={display}
    >
      {environmentName(display)}
    </span>
  );
}
