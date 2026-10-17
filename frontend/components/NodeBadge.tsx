export function NodeBadge({ display, large = false }: { display: string; large?: boolean }) {
  const prod = display.toUpperCase().includes("PROD");
  const size = large ? "px-3 py-1 text-[15px]" : "px-1.5 py-0.5 text-[11px]";
  // PROD is coral-orange, DR violet: neither is the blue used for the rest of the UI
  return (
    <span
      className={`inline-flex items-center rounded-lg font-mono font-bold text-white shadow-soft ${size} ${prod ? "bg-prod" : "bg-dr"}`}
      aria-label={`Node ${display}`}
    >
      {display}
    </span>
  );
}
