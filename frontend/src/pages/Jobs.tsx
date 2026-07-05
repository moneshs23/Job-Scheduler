import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { getErrorMessage } from "../lib/errors";
import { relativeTime } from "../lib/format";
import type { Job, Page as PageT, Queue } from "../lib/types";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Label, Select } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { StatusBadge } from "../components/ui/Badge";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { TableRowSkeleton } from "../components/ui/Skeleton";

const STATUS_OPTIONS = [
  "",
  "queued",
  "scheduled",
  "claimed",
  "running",
  "completed",
  "failed",
  "retry",
  "cancelled",
  "dead_letter",
];

const TERMINAL = new Set(["completed", "cancelled", "dead_letter"]);

export function JobsPage() {
  const { project } = useProject();
  const { push } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounce(searchInput, 350);
  const [modalOpen, setModalOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<Job | null>(null);

  const { data: queues } = useQuery({
    queryKey: ["queues", project?.id],
    queryFn: async () => (await api.get<Queue[]>(`/projects/${project!.id}/queues`)).data,
    enabled: !!project,
  });

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["jobs", project?.id, page, status, search],
    queryFn: async () =>
      (
        await api.get<PageT<Job>>(`/projects/${project!.id}/jobs`, {
          params: { page, page_size: 20, status: status || undefined, search: search || undefined },
        })
      ).data,
    enabled: !!project,
    refetchInterval: 5000,
    placeholderData: (prev) => prev,
  });

  const cancelJob = useMutation({
    mutationFn: async (jobId: string) => (await api.post(`/projects/${project!.id}/jobs/${jobId}/cancel`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", project?.id] });
      push("Job cancelled");
      setCancelTarget(null);
    },
    onError: (err) => {
      push(getErrorMessage(err), "error");
      setCancelTarget(null);
    },
  });

  if (!project) return null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-black uppercase">Jobs</h1>
          <p className="text-sm text-nb-ink/60">{data?.total ?? 0} total</p>
        </div>
        <Button
          onClick={() => setModalOpen(true)}
          disabled={!queues?.length}
          title={queues?.length ? undefined : "Create a queue first — jobs need one to run in"}
        >
          <Plus size={16} className="inline mr-1 -mt-0.5" /> New Job
        </Button>
      </div>

      {queues && queues.length === 0 && (
        <Card className="flex items-center justify-between flex-wrap gap-3 bg-nb-cyan">
          <span className="text-sm font-bold">You need a queue before you can create a job.</span>
          <Link to="/queues">
            <Button variant="secondary">Go to Queues →</Button>
          </Link>
        </Card>
      )}

      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-nb-ink/40" />
          <Input
            placeholder="Search by job name…"
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
            className="w-56 pl-8"
          />
        </div>
        <Select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s ? s.replace("_", " ") : "All statuses"}
            </option>
          ))}
        </Select>
      </div>

      <Card className={`p-0 overflow-x-auto transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
        <table className="w-full text-sm min-w-[720px]">
          <thead>
            <tr className="border-b-[3px] border-nb-ink text-left uppercase text-xs">
              <th className="p-3">Name</th>
              <th className="p-3">Status</th>
              <th className="p-3">Attempts</th>
              <th className="p-3">Created</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} cols={5} />)}
            {data?.items.map((job) => (
              <tr
                key={job.id}
                className="border-b border-nb-ink/15 hover:bg-nb-bg cursor-pointer"
                onClick={() => navigate(`/jobs/${job.id}`)}
              >
                <td className="p-3 font-bold">{job.name}</td>
                <td className="p-3">
                  <StatusBadge status={job.status} />
                </td>
                <td className="p-3 tabular-nums">
                  {job.attempt_count}/{job.max_attempts}
                </td>
                <td className="p-3 text-xs text-nb-ink/60" title={new Date(job.created_at).toLocaleString()}>
                  {relativeTime(job.created_at)}
                </td>
                <td className="p-3">
                  {!TERMINAL.has(job.status) && (
                    <Button
                      variant="danger"
                      className="px-2 py-1 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setCancelTarget(job);
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-nb-ink/60">
                  No jobs match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      {data && data.pages > 1 && (
        <div className="flex items-center gap-2">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </Button>
          <span className="text-sm font-bold">
            Page {data.page} / {data.pages}
          </span>
          <Button variant="secondary" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
            Next →
          </Button>
        </div>
      )}

      {queues && (
        <CreateJobModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          projectId={project.id}
          queues={queues}
        />
      )}

      <ConfirmDialog
        open={!!cancelTarget}
        title="Cancel this job?"
        message={`"${cancelTarget?.name}" will stop being claimed or retried. This can't be undone.`}
        confirmLabel="Cancel job"
        onConfirm={() => cancelTarget && cancelJob.mutate(cancelTarget.id)}
        onCancel={() => setCancelTarget(null)}
        loading={cancelJob.isPending}
      />
    </div>
  );
}

function CreateJobModal({
  open,
  onClose,
  projectId,
  queues,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  queues: Queue[];
}) {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [form, setForm] = useState({
    name: "",
    queue_id: queues[0]?.id ?? "",
    task: "echo",
    argsJson: "{}",
    scheduleMode: "immediate" as "immediate" | "delay" | "cron",
    delaySeconds: 10,
    cronExpression: "*/5 * * * *",
    maxAttempts: 3,
  });
  const [formError, setFormError] = useState<string | null>(null);

  const createJob = useMutation({
    mutationFn: async () => {
      let args: unknown;
      try {
        args = JSON.parse(form.argsJson || "{}");
      } catch {
        throw new Error("Args must be valid JSON");
      }
      const body: Record<string, unknown> = {
        name: form.name,
        queue_id: form.queue_id,
        max_attempts: form.maxAttempts,
        payload: { task: form.task, args },
      };
      if (form.scheduleMode === "delay") body.delay_seconds = form.delaySeconds;
      if (form.scheduleMode === "cron") body.cron_expression = form.cronExpression;
      return (await api.post(`/projects/${projectId}/jobs`, body)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", projectId] });
      push("Job created");
      onClose();
    },
    onError: (err: unknown) => setFormError(getErrorMessage(err, "Failed to create job")),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    createJob.mutate();
  };

  return (
    <Modal open={open} onClose={onClose} title="New Job">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Label>Name</Label>
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. send-welcome-email"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label>Queue</Label>
          <Select value={form.queue_id} onChange={(e) => setForm({ ...form, queue_id: e.target.value })}>
            {queues.map((q) => (
              <option key={q.id} value={q.id}>
                {q.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label>Task</Label>
          <Select value={form.task} onChange={(e) => setForm({ ...form, task: e.target.value })}>
            <option value="echo">echo</option>
            <option value="sleep">sleep</option>
            <option value="http_request">http_request</option>
            <option value="fail">fail (always fails)</option>
            <option value="random_fail">random_fail</option>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label>Args (JSON)</Label>
          <Input
            value={form.argsJson}
            onChange={(e) => setForm({ ...form, argsJson: e.target.value })}
            placeholder='{"seconds": 2}'
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label>Schedule</Label>
          <Select
            value={form.scheduleMode}
            onChange={(e) => setForm({ ...form, scheduleMode: e.target.value as typeof form.scheduleMode })}
          >
            <option value="immediate">Run immediately</option>
            <option value="delay">Delay (seconds)</option>
            <option value="cron">Recurring (cron)</option>
          </Select>
        </div>
        {form.scheduleMode === "delay" && (
          <Input
            type="number"
            min={1}
            value={form.delaySeconds}
            onChange={(e) => setForm({ ...form, delaySeconds: Number(e.target.value) })}
          />
        )}
        {form.scheduleMode === "cron" && (
          <Input
            value={form.cronExpression}
            onChange={(e) => setForm({ ...form, cronExpression: e.target.value })}
            placeholder="*/5 * * * *"
          />
        )}
        <div className="flex flex-col gap-1">
          <Label>Max attempts</Label>
          <Input
            type="number"
            min={1}
            value={form.maxAttempts}
            onChange={(e) => setForm({ ...form, maxAttempts: Number(e.target.value) })}
          />
        </div>
        {formError && <div className="nb-border bg-nb-red px-3 py-2 text-sm font-bold">{formError}</div>}
        <Button type="submit" disabled={createJob.isPending}>
          {createJob.isPending ? "Creating…" : "Create job"}
        </Button>
      </form>
    </Modal>
  );
}
