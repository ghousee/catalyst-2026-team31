import { initials } from "@/lib/format";

export function Avatar({ name, size = 28, muted = false }: { name: string; size?: number; muted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      className={`inline-flex shrink-0 items-center justify-center rounded-[3px] border font-medium ${
        muted ? "border-line bg-panel2 text-muted" : "border-line bg-panel2 text-fg"
      }`}
    >
      {initials(name)}
    </span>
  );
}
