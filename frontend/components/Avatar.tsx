import { initials } from "@/lib/format";

export function Avatar({ name, size = 28, muted = false }: { name: string; size?: number; muted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      className={`inline-flex shrink-0 items-center justify-center rounded-full border font-semibold ${
        muted ? "border-line bg-panel2 text-muted" : "border-warn/60 bg-warn/15 text-warn"
      }`}
    >
      {initials(name)}
    </span>
  );
}
