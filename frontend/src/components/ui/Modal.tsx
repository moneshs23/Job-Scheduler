import type { ReactNode } from "react";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="nb-border nb-shadow-lg bg-nb-paper w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-black uppercase">{title}</h2>
          <button
            onClick={onClose}
            className="nb-border nb-shadow-sm nb-press bg-nb-paper px-2 py-1 font-bold"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
