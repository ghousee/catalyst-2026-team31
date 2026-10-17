"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";

interface Props {
  /** "horizontal" = panes side by side (drag the vertical bar); "vertical" = stacked (drag the horizontal bar). */
  direction: "horizontal" | "vertical";
  /** localStorage key for the saved size; also names the handle for screen readers. */
  id: string;
  label: string;
  /** Share of the container the first pane gets on first load (0..1). */
  initial?: number;
  /** Minimum sizes in px. */
  minFirst?: number;
  minSecond?: number;
  children: [ReactNode, ReactNode];
}

const KEY = (id: string) => `split:${id}`;
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));

/** Two panes with a draggable divider (pointer events, arrow keys). The size is a ratio, saved in localStorage. */
export function SplitPane({ direction, id, label, initial = 0.5, minFirst = 160, minSecond = 160, children }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [ratio, setRatio] = useState(initial);
  const row = direction === "horizontal";

  useEffect(() => {
    try {
      const saved = parseFloat(localStorage.getItem(KEY(id)) ?? "");
      if (saved > 0 && saved < 1) setRatio(saved);
    } catch {
      /* storage blocked: keep the default */
    }
  }, [id]);

  const limits = useCallback(() => {
    const total = (row ? box.current?.clientWidth : box.current?.clientHeight) || 1;
    return { lo: Math.min(minFirst / total, 0.5), hi: Math.max(1 - minSecond / total, 0.5) };
  }, [row, minFirst, minSecond]);

  const save = (r: number) => {
    try {
      localStorage.setItem(KEY(id), String(r));
    } catch {
      /* ignore */
    }
  };

  const move = (e: PointerEvent<HTMLDivElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId) || !box.current) return;
    const rect = box.current.getBoundingClientRect();
    const total = row ? rect.width : rect.height;
    const pos = row ? e.clientX - rect.left : e.clientY - rect.top;
    const { lo, hi } = limits();
    setRatio(clamp(pos / total, lo, hi));
  };

  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const dec = row ? "ArrowLeft" : "ArrowUp";
    const inc = row ? "ArrowRight" : "ArrowDown";
    if (e.key !== dec && e.key !== inc) return;
    e.preventDefault();
    const { lo, hi } = limits();
    const next = clamp(ratio + (e.key === inc ? 1 : -1) * (e.shiftKey ? 0.1 : 0.02), lo, hi);
    setRatio(next);
    save(next);
  };

  const shown = ratio;
  const minStyle = (px: number) => (row ? { minWidth: px } : { minHeight: px }); // CSS keeps the minimums on window resize
  return (
    <div ref={box} className={`flex min-h-0 min-w-0 flex-1 ${row ? "flex-row" : "flex-col"}`}>
      <div
        className="grid min-h-0 min-w-0 grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)] overflow-hidden"
        style={{ flex: `0 0 ${shown * 100}%`, ...minStyle(minFirst) }}
      >
        {children[0]}
      </div>
      <div
        role="separator"
        aria-orientation={row ? "vertical" : "horizontal"}
        aria-label={`Resize: ${label} (arrow keys; Shift for larger steps)`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(shown * 100)}
        tabIndex={0}
        onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
        onPointerMove={move}
        onPointerUp={() => save(shown)}
        onKeyDown={key}
        className={`group shrink-0 touch-none bg-line transition-colors hover:bg-accent/60 focus-visible:bg-accent ${
          row ? "w-1.5 cursor-col-resize" : "h-1.5 cursor-row-resize"
        }`}
      />
      <div
        className="grid min-h-0 min-w-0 flex-1 grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)] overflow-hidden"
        style={minStyle(minSecond)}
      >
        {children[1]}
      </div>
    </div>
  );
}
