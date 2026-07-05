import { type ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-nb-yellow text-nb-ink hover:brightness-95",
  secondary: "bg-nb-paper text-nb-ink hover:bg-nb-bg",
  danger: "bg-nb-red text-nb-ink hover:brightness-95",
  ghost: "bg-transparent text-nb-ink hover:bg-nb-bg border-transparent shadow-none",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", className, children, ...rest }, ref) => (
    <button
      ref={ref}
      className={clsx(
        "nb-border nb-shadow-sm nb-press font-bold uppercase tracking-wide text-sm px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed",
        variantClasses[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
);
Button.displayName = "Button";
