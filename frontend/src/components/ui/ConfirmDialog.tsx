import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger = true,
  onConfirm,
  onCancel,
  loading = false,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 p-4">
      <div className="nb-border nb-shadow-lg bg-nb-paper w-full max-w-sm p-6 animate-[modal-in_0.12s_ease-out]">
        <div className="flex items-center gap-2 mb-3">
          <div className="nb-border bg-nb-red p-1.5">
            <AlertTriangle size={18} />
          </div>
          <h2 className="text-lg font-black uppercase">{title}</h2>
        </div>
        <p className="text-sm text-nb-ink/70 mb-5">{message}</p>
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} disabled={loading}>
            {loading ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
