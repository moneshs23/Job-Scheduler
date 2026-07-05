import clsx from "clsx";

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("nb-border nb-skeleton", className)} />;
}

export function StatCardSkeleton() {
  return (
    <div className="nb-border nb-shadow bg-nb-paper p-4 flex flex-col gap-2">
      <Skeleton className="h-5 w-20" />
      <Skeleton className="h-8 w-14" />
    </div>
  );
}

export function TableRowSkeleton({ cols }: { cols: number }) {
  return (
    <tr className="border-b border-nb-ink/15">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="p-3">
          <Skeleton className="h-4 w-full max-w-32" />
        </td>
      ))}
    </tr>
  );
}
