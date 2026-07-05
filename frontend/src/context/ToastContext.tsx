import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import clsx from "clsx";

type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  push: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, { bg: string; icon: typeof CheckCircle2 }> = {
  success: { bg: "bg-nb-lime", icon: CheckCircle2 },
  error: { bg: "bg-nb-red", icon: XCircle },
  info: { bg: "bg-nb-cyan", icon: Info },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const push = useCallback((message: string, variant: ToastVariant = "success") => {
    const id = idRef.current++;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => {
          const { bg, icon: Icon } = VARIANT_STYLES[toast.variant];
          return (
            <div
              key={toast.id}
              className={clsx(
                "nb-border nb-shadow pointer-events-auto flex items-start gap-2 px-4 py-3 font-bold text-sm animate-[toast-in_0.15s_ease-out]",
                bg,
              )}
            >
              <Icon size={18} className="shrink-0 mt-0.5" />
              <span className="flex-1">{toast.message}</span>
              <button onClick={() => dismiss(toast.id)} className="shrink-0 opacity-70 hover:opacity-100">
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
