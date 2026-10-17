// Who is using the app, picked in the top bar and remembered in this browser. No login: a prototype on synthetic data.
// A junior's id is any name they type; a senior is a person row (they can teach and sign).
import { useSyncExternalStore } from "react";

export interface Me {
  id: string;
  name: string;
  role: "junior" | "senior";
}

const KEY = "cail.me";
const DEFAULT: Me = { id: "newhire1", name: "newhire1", role: "junior" };
let cached: Me | null = null;
const listeners = new Set<() => void>();

export function getMe(): Me {
  if (cached) return cached;
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(KEY) : null;
    cached = raw ? (JSON.parse(raw) as Me) : DEFAULT;
  } catch {
    cached = DEFAULT;
  }
  return cached;
}

export function setMe(me: Me) {
  cached = me;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(me));
  } catch {
    /* private window: keep it for this tab only */
  }
  listeners.forEach((l) => l());
}

/** "Priya Shah" -> "priya_shah" (the id the backend stores questions under) */
export const toUserId = (name: string) =>
  name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32);

export function useMe(): Me {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    getMe,
    () => DEFAULT,
  );
}
