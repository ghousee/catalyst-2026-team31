"use client";

import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Modal } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  busy = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} label={title}>
      <div className="space-y-3 p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <TriangleAlert size={18} className="text-warn" aria-hidden="true" />
          {title}
        </h2>
        <div className="text-[13.5px] text-muted">{children}</div>
        {error && (
          <p role="alert" className="text-[12.5px] text-crit">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn" onClick={onCancel} autoFocus>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? "Switching…" : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
