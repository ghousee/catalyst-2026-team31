"use client";

import { useEffect, useRef, useState } from "react";

/** Close a popover on outside click or Escape. */
export function useDismiss<T extends HTMLElement>(open: boolean, close: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

export interface Polled<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Poll `fn` every `ms`. Keeps previous data on error. Re-runs when `key` changes. */
export function usePolling<T>(fn: () => Promise<T>, ms: number, key: string): Polled<T> {
  const [state, setState] = useState<Polled<T>>({ data: null, error: null, loading: true });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let alive = true;
    let last = "";
    setState((s) => ({ ...s, loading: true }));
    const tick = async () => {
      try {
        const d = await fnRef.current();
        if (!alive) return;
        const sig = JSON.stringify(d);
        setState((s) => (sig === last && !s.error && !s.loading ? s : { data: d, error: null, loading: false }));
        last = sig;
      } catch (e) {
        if (alive) setState((s) => ({ data: s.data, error: e instanceof Error ? e.message : "Request failed", loading: false }));
      }
    };
    void tick();
    const t = setInterval(tick, ms);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [ms, key]);
  return state;
}
