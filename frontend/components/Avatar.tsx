import { initials } from "@/lib/format";

const HUES = ["--sub-tmf", "--sub-pathway", "--sub-scf", "--sub-tacl", "--sub-peek", "--sub-fup", "--sub-measure"];
const hueOf = (name: string) => HUES[[...name].reduce((a, ch) => a + ch.charCodeAt(0), 0) % HUES.length];

export function Avatar({ name, size = 28, muted = false }: { name: string; size?: number; muted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: size * 0.4, ["--c" as string]: `var(${hueOf(name)})` }}
      className={`inline-flex shrink-0 items-center justify-center rounded-full border font-semibold ${
        muted ? "border-line bg-panel2 text-muted" : "border-[rgb(var(--c)/0.4)] bg-[rgb(var(--c)/0.18)] text-[color-mix(in_srgb,rgb(var(--c))_65%,rgb(var(--fg)))]"
      }`}
    >
      {initials(name)}
    </span>
  );
}
