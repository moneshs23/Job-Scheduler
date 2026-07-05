import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Plus } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../lib/errors";
import type { Queue, QueueMetrics, RetryPolicy } from "../lib/types";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Label, Select } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { StatCardSkeleton } from "../components/ui/Skeleton";

const STRATEGIES = ["fixed", "linear", "exponential", "custom"] as const;

function nextDefaultQueueName(queues: Queue[] | undefined): string {
  const taken = new Set(queues?.map((q) => q.name));
  if (!taken.has("default")) return "default";
  for (let i = 2; i < 100; i++) {
    if (!taken.has(`default-${i}`)) return `default-${i}`;
  }
  return "";
}

function defaultPolicyName(strategy: string): string {
  return `${strategy}-backoff`;
}

export function QueuesPage() {
  const { project } = useProject();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [showNewPolicy, setShowNewPolicy] = useState(false);
  const [form, setForm] = useState({
    name: "",
    priority: 0,
    concurrency_limit: 10,
    retry_policy_id: "",
  });
  const [policyForm, setPolicyForm] = useState({
    name: defaultPolicyName("exponential"),
    strategy: "exponential" as (typeof STRATEGIES)[number],
    max_retries: 3,
    base_delay_ms: 1000,
  });
  const [policyNameEdited, setPolicyNameEdited] = useState(false);

  const onPolicyStrategyChange = (strategy: (typeof STRATEGIES)[number]) => {
    setPolicyForm((f) => ({
      ...f,
      strategy,
      name: policyNameEdited ? f.name : defaultPolicyName(strategy),
    }));
  };

  const { data: queues, isLoading } = useQuery({
    queryKey: ["queues", project?.id],
    queryFn: async () => (await api.get<Queue[]>(`/projects/${project!.id}/queues`)).data,
    enabled: !!project,
    refetchInterval: 5000,
  });

  const { data: retryPolicies } = useQuery({
    queryKey: ["retry-policies", project?.id],
    queryFn: async () => (await api.get<RetryPolicy[]>(`/projects/${project!.id}/retry-policies`)).data,
    enabled: !!project,
  });

  const createPolicy = useMutation({
    mutationFn: async () =>
      (await api.post(`/projects/${project!.id}/retry-policies`, policyForm)).data as RetryPolicy,
    onSuccess: (policy) => {
      queryClient.invalidateQueries({ queryKey: ["retry-policies", project?.id] });
      setForm((f) => ({ ...f, retry_policy_id: policy.id }));
      setShowNewPolicy(false);
      push(`Retry policy "${policy.name}" created`);
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  const createQueue = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/projects/${project!.id}/queues`, {
          ...form,
          retry_policy_id: form.retry_policy_id || null,
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queues", project?.id] });
      setModalOpen(false);
      setForm({ name: "", priority: 0, concurrency_limit: 10, retry_policy_id: "" });
      push("Queue created");
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  const togglePause = useMutation({
    mutationFn: async (queue: Queue) =>
      (
        await api.post(
          `/projects/${project!.id}/queues/${queue.id}/${queue.is_paused ? "resume" : "pause"}`,
        )
      ).data,
    onSuccess: (_data, queue: Queue) => {
      queryClient.invalidateQueries({ queryKey: ["queues", project?.id] });
      push(queue.is_paused ? "Queue resumed" : "Queue paused", "info");
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  if (!project) return null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-black uppercase">Queues</h1>
          <p className="text-sm text-nb-ink/60">Priority, concurrency, and health per queue</p>
        </div>
        <Button
          onClick={() => {
            setForm((f) => ({ ...f, name: nextDefaultQueueName(queues) }));
            setModalOpen(true);
          }}
        >
          <Plus size={16} className="inline mr-1 -mt-0.5" /> New Queue
        </Button>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {isLoading && Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
        {queues?.map((queue) => (
          <QueueCard key={queue.id} queue={queue} projectId={project.id} onTogglePause={togglePause.mutate} />
        ))}
        {queues?.length === 0 && !isLoading && (
          <Card className="col-span-full flex items-center justify-between flex-wrap gap-3">
            <span className="text-sm text-nb-ink/60">No queues yet — jobs need a queue to run in.</span>
            <Button
              onClick={() => {
                setForm((f) => ({ ...f, name: nextDefaultQueueName(queues) }));
                setModalOpen(true);
              }}
            >
              <Plus size={16} className="inline mr-1 -mt-0.5" /> Create "default" queue
            </Button>
          </Card>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="New Queue">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            createQueue.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <div className="flex flex-col gap-1">
            <Label>Name</Label>
            <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label>Priority (0-100)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Concurrency limit</Label>
              <Input
                type="number"
                min={1}
                value={form.concurrency_limit}
                onChange={(e) => setForm({ ...form, concurrency_limit: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <Label>Retry policy</Label>
            <Select
              value={form.retry_policy_id}
              onChange={(e) => setForm({ ...form, retry_policy_id: e.target.value })}
            >
              <option value="">Default (exponential, 3 retries)</option>
              {retryPolicies?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.strategy})
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={() => setShowNewPolicy((v) => !v)}
              className="text-xs font-bold underline self-start mt-1"
            >
              {showNewPolicy ? "Cancel" : "+ Create a new retry policy"}
            </button>
          </div>

          {showNewPolicy && (
            <div className="nb-border bg-nb-bg p-3 flex flex-col gap-2">
              <div className="flex flex-col gap-1">
                <Label>Policy name</Label>
                <Input
                  value={policyForm.name}
                  onChange={(e) => {
                    setPolicyNameEdited(true);
                    setPolicyForm({ ...policyForm, name: e.target.value });
                  }}
                  placeholder="e.g. slow-backoff"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="flex flex-col gap-1">
                  <Label>Strategy</Label>
                  <Select
                    value={policyForm.strategy}
                    onChange={(e) => onPolicyStrategyChange(e.target.value as (typeof STRATEGIES)[number])}
                  >
                    {STRATEGIES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1">
                  <Label>Max retries</Label>
                  <Input
                    type="number"
                    min={0}
                    value={policyForm.max_retries}
                    onChange={(e) => setPolicyForm({ ...policyForm, max_retries: Number(e.target.value) })}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label>Base delay (ms)</Label>
                  <Input
                    type="number"
                    min={0}
                    value={policyForm.base_delay_ms}
                    onChange={(e) => setPolicyForm({ ...policyForm, base_delay_ms: Number(e.target.value) })}
                  />
                </div>
              </div>
              <Button
                type="button"
                variant="secondary"
                disabled={!policyForm.name || createPolicy.isPending}
                onClick={() => createPolicy.mutate()}
              >
                {createPolicy.isPending ? "Saving…" : "Save policy"}
              </Button>
            </div>
          )}

          <Button type="submit" disabled={createQueue.isPending}>
            {createQueue.isPending ? "Creating…" : "Create queue"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}

function QueueCard({
  queue,
  projectId,
  onTogglePause,
}: {
  queue: Queue;
  projectId: string;
  onTogglePause: (q: Queue) => void;
}) {
  const { data: metrics } = useQuery({
    queryKey: ["queue-metrics", queue.id],
    queryFn: async () =>
      (await api.get<QueueMetrics>(`/projects/${projectId}/queues/${queue.id}/metrics`)).data,
    refetchInterval: 4000,
  });

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-black text-lg">{queue.name}</h3>
        <span className={`nb-border px-2 py-0.5 text-[11px] font-bold uppercase ${queue.is_paused ? "bg-nb-red" : "bg-nb-lime"}`}>
          {queue.is_paused ? "Paused" : "Active"}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center mb-3">
        <MiniStat label="Queued" value={metrics?.queued ?? "…"} />
        <MiniStat label="Running" value={metrics?.running ?? "…"} />
        <MiniStat label="Dead" value={metrics?.dead_letter ?? "…"} />
      </div>

      <div className="text-xs text-nb-ink/60 mb-3 space-y-0.5">
        <div>Priority: <b className="text-nb-ink">{queue.priority}</b></div>
        <div>Concurrency limit: <b className="text-nb-ink">{queue.concurrency_limit}</b></div>
        <div>Active workers: <b className="text-nb-ink">{metrics?.active_workers ?? "…"}</b></div>
        <div>Throughput: <b className="text-nb-ink">{metrics?.throughput_per_min ?? "…"}/min</b></div>
      </div>

      <Button variant="secondary" className="w-full" onClick={() => onTogglePause(queue)}>
        {queue.is_paused ? (
          <>
            <Play size={14} className="inline mr-1 -mt-0.5" /> Resume
          </>
        ) : (
          <>
            <Pause size={14} className="inline mr-1 -mt-0.5" /> Pause
          </>
        )}
      </Button>
    </Card>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="nb-border bg-nb-bg px-2 py-1.5">
      <div className="text-lg font-black tabular-nums">{value}</div>
      <div className="text-[10px] uppercase font-bold text-nb-ink/60">{label}</div>
    </div>
  );
}
