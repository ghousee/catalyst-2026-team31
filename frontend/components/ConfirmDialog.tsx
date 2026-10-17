"use client";

import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Modal } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  description,
  children,
  confirmLabel,
  busy = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} label={title}>
      <div>
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-warn/25 bg-warn/10 text-warn">
            <TriangleAlert size={18} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-medium text-warn">Review required</p>
            <h2 className="mt-0.5 text-lg font-semibold leading-6">{title}</h2>
            {description && <p className="mt-1 text-sm text-muted">{description}</p>}
          </div>
        </header>
        <div className="px-5 py-4 text-sm text-muted">{children}</div>
        {error && (
          <p role="alert" className="mx-5 mb-4 rounded-lg border border-crit/25 bg-crit/10 px-3 py-2 text-xs text-crit">
            {error}
          </p>
        )}
        <footer className="flex flex-col-reverse gap-2 border-t border-line bg-panel2/40 px-5 py-3 sm:flex-row sm:justify-end">
          <button type="button" className="btn" onClick={onCancel} autoFocus>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? "Switching…" : confirmLabel}
          </button>
        </footer>
      </div>
    </Modal>
  );
}
