"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Native <dialog>: focus trap, Esc to close, restores focus. `side` docks it to the right edge. */
export function Modal({
  open,
  onClose,
  label,
  side = false,
  children,
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  side?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  const cls = side
    ? "m-0 ml-auto h-full max-h-none w-[420px] max-w-full rounded-none border-l border-line bg-panel p-0"
    : "m-auto w-[460px] max-w-[92vw] rounded border border-line bg-panel p-0";

  return (
    <dialog
      ref={ref}
      aria-label={label}
      className={cls}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open ? children : null}
    </dialog>
  );
}
