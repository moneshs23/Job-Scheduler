import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw, XCircle } from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../lib/errors";
import { formatDuration, relativeTime } from "../lib/format";
import type { Job, JobExecution, JobLog } from "../lib/types";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";

const TERMINAL = new Set(["completed", "cancelled", "dead_letter"]);

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { project } = useProject();
  const navigate = useNavigate();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [confirmCancel, setConfirmCancel] = useState(false);

  const { data: job, isLoading } = useQuery({
    queryKey: ["job", project?.id, jobId],
    queryFn: async () => (await api.get<Job>(`/projects/${project!.id}/jobs/${jobId}`)).data,
    enabled: !!project && !!jobId,
    refetchInterval: 4000,
  });

  const { data: executions } = useQuery({
    queryKey: ["job-executions", project?.id, jobId],
    queryFn: async () =>
      (await api.get<JobExecution[]>(`/projects/${project!.id}/jobs/${jobId}/executions`)).data,
    enabled: !!project && !!jobId,
    refetchInterval: 4000,
  });

  const { data: logs } = useQuery({
    queryKey: ["job-logs", project?.id, jobId],
    queryFn: async () => (await api.get<JobLog[]>(`/projects/${project!.id}/jobs/${jobId}/logs`)).data,
    enabled: !!project && !!jobId,
    refetchInterval: 4000,
  });

  const cancelJob = useMutation({
    mutationFn: async () => (await api.post(`/projects/${project!.id}/jobs/${jobId}/cancel`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", project?.id, jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      push("Job cancelled");
      setConfirmCancel(false);
    },
    onError: (err) => {
      push(getErrorMessage(err), "error");
      setConfirmCancel(false);
    },
  });

  const replayJob = useMutation({
    mutationFn: async () => (await api.post(`/projects/${project!.id}/jobs/${jobId}/replay`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", project?.id, jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dead-letters"] });
      push("Job requeued");
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  if (!project) return null;

  if (isLoading || !job) {
    return (
      <div className="flex flex-col gap-4 max-w-4xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const timeline: { label: string; ts: string | null }[] = [
    { label: "Created", ts: job.created_at },
    { label: "Scheduled", ts: job.scheduled_at },
    { label: "Claimed", ts: job.claimed_at },
    { label: "Started", ts: job.started_at },
    { label: "Completed", ts: job.completed_at },
  ];

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm font-bold text-nb-ink/60 hover:text-nb-ink mb-2"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black break-all">{job.name}</h1>
            <p className="text-xs text-nb-ink/50 font-mono">{job.id}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={job.status} />
            {!TERMINAL.has(job.status) && (
              <Button variant="danger" onClick={() => setConfirmCancel(true)}>
                <XCircle size={16} className="inline mr-1 -mt-0.5" /> Cancel
              </Button>
            )}
            {job.status === "dead_letter" && (
              <Button onClick={() => replayJob.mutate()} disabled={replayJob.isPending}>
                <RotateCcw size={16} className="inline mr-1 -mt-0.5" />
                {replayJob.isPending ? "Replaying…" : "Replay"}
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <h2 className="font-black uppercase text-sm mb-3">Details</h2>
          <dl className="text-sm space-y-2">
            <Row label="Attempts" value={`${job.attempt_count} / ${job.max_attempts}`} />
            <Row label="Priority" value={job.priority} />
            <Row label="Idempotency key" value={job.idempotency_key ?? "—"} />
            <Row label="Batch" value={job.batch_id ?? "—"} mono />
            {job.next_retry_at && <Row label="Next retry" value={relativeTime(job.next_retry_at)} />}
            {job.last_error && (
              <div className="pt-2">
                <div className="text-xs font-bold uppercase text-nb-ink/50 mb-1">Last error</div>
                <div className="nb-border bg-nb-red/90 px-3 py-2 text-xs font-mono break-all">{job.last_error}</div>
              </div>
            )}
          </dl>
        </Card>

        <Card>
          <h2 className="font-black uppercase text-sm mb-3">Timeline</h2>
          <ul className="text-sm space-y-2">
            {timeline.map((t) => (
              <li key={t.label} className="flex items-center justify-between">
                <span className="text-nb-ink/60">{t.label}</span>
                <span className={t.ts ? "font-bold" : "text-nb-ink/30"}>
                  {t.ts ? new Date(t.ts).toLocaleString() : "—"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <h2 className="font-black uppercase text-sm mb-3">Payload</h2>
        <pre className="nb-border bg-nb-bg p-3 text-xs overflow-x-auto max-h-64 overflow-y-auto">
          {JSON.stringify(job.payload, null, 2) ?? "null"}
        </pre>
      </Card>

      <Card>
        <h2 className="font-black uppercase text-sm mb-3">Executions ({executions?.length ?? 0})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead>
              <tr className="border-b-[3px] border-nb-ink text-left uppercase text-xs">
                <th className="p-2">Attempt</th>
                <th className="p-2">Status</th>
                <th className="p-2">Duration</th>
                <th className="p-2">Started</th>
                <th className="p-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {executions?.map((exec) => (
                <tr key={exec.id} className="border-b border-nb-ink/15 align-top">
                  <td className="p-2 font-bold">#{exec.attempt_number}</td>
                  <td className="p-2">
                    <StatusBadge status={exec.status} />
                  </td>
                  <td className="p-2 tabular-nums">{formatDuration(exec.duration_ms)}</td>
                  <td className="p-2 text-xs text-nb-ink/60">{new Date(exec.started_at).toLocaleTimeString()}</td>
                  <td className="p-2 text-xs font-mono text-nb-red max-w-64 truncate">
                    {exec.error_message ?? "—"}
                  </td>
                </tr>
              ))}
              {executions?.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-nb-ink/50">
                    No attempts yet — waiting for a worker to claim this job.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-black uppercase text-sm mb-3">Logs ({logs?.length ?? 0})</h2>
        <div className="flex flex-col gap-1.5 max-h-80 overflow-y-auto">
          {logs?.map((log) => (
            <div key={log.id} className="flex items-start gap-2 text-xs font-mono border-b border-nb-ink/10 pb-1.5">
              <span className="text-nb-ink/40 shrink-0">{new Date(log.logged_at).toLocaleTimeString()}</span>
              <LogLevelTag level={log.level} />
              <span className="break-all">{log.message}</span>
            </div>
          ))}
          {logs?.length === 0 && <div className="text-sm text-nb-ink/50">No logs yet.</div>}
        </div>
      </Card>

      <ConfirmDialog
        open={confirmCancel}
        title="Cancel this job?"
        message="This will stop the job from being claimed or retried again. This can't be undone."
        confirmLabel="Cancel job"
        onConfirm={() => cancelJob.mutate()}
        onCancel={() => setConfirmCancel(false)}
        loading={cancelJob.isPending}
      />
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-nb-ink/60">{label}</span>
      <span className={clsx("font-bold text-right break-all", mono && "font-mono text-xs")}>{value}</span>
    </div>
  );
}

function LogLevelTag({ level }: { level: string }) {
  const colors: Record<string, string> = {
    debug: "bg-nb-paper-2",
    info: "bg-nb-cyan",
    warn: "bg-nb-orange",
    error: "bg-nb-red",
  };
  return (
    <span className={`nb-border px-1.5 shrink-0 uppercase font-bold ${colors[level] ?? "bg-nb-paper-2"}`}>
      {level}
    </span>
  );
}
