import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Cpu, Server, Terminal } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { relativeTime } from "../lib/format";
import type { Worker } from "../lib/types";
import { Card, StatCard } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/Badge";
import { StatCardSkeleton } from "../components/ui/Skeleton";

export function WorkersPage() {
  const { project } = useProject();

  const { data: workers, isLoading } = useQuery({
    queryKey: ["workers", project?.id],
    queryFn: async () => (await api.get<Worker[]>(`/projects/${project!.id}/workers`)).data,
    enabled: !!project,
    refetchInterval: 4000,
  });

  if (!project) return null;

  const alive = workers?.filter(
    (w) => w.last_heartbeat_at && Date.now() - new Date(w.last_heartbeat_at).getTime() < 30_000,
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-black uppercase">Workers</h1>
        <p className="text-sm text-nb-ink/60">Registration, concurrency, and heartbeat health</p>
      </div>

      {!isLoading && workers && workers.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total" value={workers.length} accent="bg-nb-cyan" />
          <StatCard label="Alive" value={alive?.length ?? 0} accent="bg-nb-lime" />
          <StatCard
            label="Total Capacity"
            value={workers.reduce((sum, w) => sum + w.concurrency, 0)}
            accent="bg-nb-violet"
          />
          <StatCard
            label="In Use"
            value={workers.reduce((sum, w) => sum + w.active_jobs, 0)}
            accent="bg-nb-orange"
          />
        </div>
      )}

      {workers?.length === 0 && !isLoading && <StartWorkerGuide projectId={project.id} />}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {isLoading && Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
        {workers?.map((worker) => (
          <WorkerCard key={worker.id} worker={worker} />
        ))}
      </div>

      {workers && workers.length > 0 && !alive?.length && (
        <Card className="text-sm flex items-center gap-2 bg-nb-orange">
          <Server size={16} /> No worker has sent a heartbeat in the last 30s — jobs will queue up
          until one comes back online.
        </Card>
      )}
    </div>
  );
}

function StartWorkerGuide({ projectId }: { projectId: string }) {
  const { push } = useToast();
  const [copied, setCopied] = useState(false);
  const command = `WORKER_PROJECT_ID=${projectId} python -m app.workers.main`;

  const copy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    push("Command copied", "info");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="nb-border bg-nb-yellow p-1.5">
          <Server size={16} />
        </div>
        <h2 className="font-black uppercase">No workers running yet</h2>
      </div>
      <p className="text-sm text-nb-ink/70">
        A worker is a background process — it can't be started from the browser. Run this from a
        terminal in <code className="nb-border px-1">backend/</code> (with the virtualenv activated).
        It'll pick up every queue in this project and start claiming jobs within a few seconds.
      </p>
      <div className="nb-border bg-nb-bg p-3 flex items-center justify-between gap-2">
        <code className="text-xs md:text-sm font-mono break-all flex items-center gap-2">
          <Terminal size={14} className="shrink-0 opacity-50" />
          {command}
        </code>
        <button onClick={copy} className="shrink-0 nb-border nb-shadow-sm nb-press bg-nb-paper p-1.5">
          <Copy size={14} />
        </button>
      </div>
      {copied && <p className="text-xs font-bold text-nb-ink/60">Copied — paste it in your terminal.</p>}
      <p className="text-xs text-nb-ink/50">
        Running the full stack with Docker Compose instead? See{" "}
        <code className="nb-border px-1">docs/Deployment.md</code> — workers run as a scaled
        Compose service there.
      </p>
    </Card>
  );
}

function WorkerCard({ worker }: { worker: Worker }) {
  const isStale =
    worker.status !== "stopped" &&
    (!worker.last_heartbeat_at || Date.now() - new Date(worker.last_heartbeat_at).getTime() > 30_000);
  const load = worker.concurrency > 0 ? worker.active_jobs / worker.concurrency : 0;

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-black truncate flex items-center gap-1.5">
          <Cpu size={16} className="shrink-0 opacity-60" />
          {worker.hostname}
        </h3>
        <StatusBadge status={isStale ? "stopped" : worker.status} />
      </div>

      <div className="mb-3">
        <div className="flex justify-between text-xs font-bold mb-1">
          <span>Load</span>
          <span>
            {worker.active_jobs} / {worker.concurrency}
          </span>
        </div>
        <div className="nb-border h-3 bg-nb-bg overflow-hidden">
          <div
            className="h-full bg-nb-yellow transition-all"
            style={{ width: `${Math.min(100, load * 100)}%` }}
          />
        </div>
      </div>

      <div className="text-xs text-nb-ink/60 space-y-1">
        <div>Type: <b className="text-nb-ink">{worker.worker_type}</b></div>
        <div>Registered: <b className="text-nb-ink">{relativeTime(worker.registered_at)}</b></div>
        <div>
          Last heartbeat:{" "}
          <b className="text-nb-ink">
            {worker.last_heartbeat_at ? relativeTime(worker.last_heartbeat_at) : "never"}
          </b>
        </div>
      </div>
    </Card>
  );
}
