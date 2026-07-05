import clsx from "clsx";
import type { JobStatus } from "../../lib/types";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-nb-cyan",
  scheduled: "bg-nb-violet",
  claimed: "bg-nb-orange",
  running: "bg-nb-yellow",
  completed: "bg-nb-lime",
  failed: "bg-nb-red",
  retry: "bg-nb-orange",
  cancelled: "bg-nb-paper",
  dead_letter: "bg-nb-red",
  idle: "bg-nb-lime",
  busy: "bg-nb-yellow",
  starting: "bg-nb-cyan",
  draining: "bg-nb-orange",
  stopped: "bg-nb-paper",
};

export function StatusBadge({ status }: { status: JobStatus | string }) {
  return (
    <span
      className={clsx(
        "nb-border inline-block px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide",
        STATUS_COLORS[status] ?? "bg-nb-paper",
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}
