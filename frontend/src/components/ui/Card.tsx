import type { HTMLAttributes } from "react";
import clsx from "clsx";

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx("nb-border nb-shadow bg-nb-paper p-5", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  accent = "bg-nb-yellow",
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="nb-border nb-shadow bg-nb-paper p-4 flex flex-col gap-1">
      <span className={clsx("self-start px-2 py-0.5 text-[11px] font-bold uppercase nb-border", accent)}>
        {label}
      </span>
      <span className="text-3xl font-black tabular-nums">{value}</span>
    </div>
  );
}
