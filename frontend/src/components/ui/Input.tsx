import { type InputHTMLAttributes, type SelectHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={clsx(
        "nb-border bg-nb-paper px-3 py-2 text-sm font-medium outline-none focus:bg-nb-yellow/20 placeholder:text-nb-ink/40",
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...rest }, ref) => (
    <select
      ref={ref}
      className={clsx("nb-border bg-nb-paper px-3 py-2 text-sm font-bold outline-none", className)}
      {...rest}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export function Label({ children }: { children: React.ReactNode }) {
  return <label className="text-xs font-bold uppercase tracking-wide">{children}</label>;
}
