import type { Config } from "tailwindcss";

const c = (v: string) => `rgb(var(--${v}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: c("bg"),
        panel: c("panel"),
        panel2: c("panel2"),
        line: c("line"),
        fg: c("fg"),
        muted: c("muted"),
        head: c("head"),
        accent: c("accent"),
        navy: c("navy"),
        navy2: c("navy2"),
        sky: c("sky"),
        skysoft: c("skysoft"),
        ok: c("ok"),
        warn: c("warn"),
        crit: c("crit"),
        info: c("info"),
        prod: c("prod"),
        dr: c("dr"),
        term: c("term"),
        termfg: c("term-fg"),
      },
      borderRadius: { DEFAULT: "10px" },
      boxShadow: { soft: "var(--shadow)", lift: "var(--shadow-lift)" },
      fontFamily: {
        sans: ["var(--font-sans)", "Figtree", "Segoe UI", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-sans)", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "IBM Plex Mono", "Cascadia Mono", "Consolas", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
