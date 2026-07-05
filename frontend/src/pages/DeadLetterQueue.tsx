import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Skull } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../lib/errors";
import { relativeTime } from "../lib/format";
import type { DeadLetterEntry, Page as PageT, Queue } from "../lib/types";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";

export function DeadLetterQueuePage() {
  const { project } = useProject();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [queueId, setQueueId] = useState("");
  const [page, setPage] = useState(1);

  const { data: queues } = useQuery({
    queryKey: ["queues", project?.id],
    queryFn: async () => (await api.get<Queue[]>(`/projects/${project!.id}/queues`)).data,
    enabled: !!project,
  });

  const effectiveQueueId = queueId || queues?.[0]?.id || "";

  const { data, isLoading } = useQuery({
    queryKey: ["dead-letters", project?.id, effectiveQueueId, page],
    queryFn: async () =>
      (
        await api.get<PageT<DeadLetterEntry>>(`/projects/${project!.id}/dead-letter-queue`, {
          params: { queue_id: effectiveQueueId, page, page_size: 20 },
        })
      ).data,
    enabled: !!project && !!effectiveQueueId,
    refetchInterval: 6000,
  });

  const replay = useMutation({
    mutationFn: async (jobId: string) => (await api.post(`/projects/${project!.id}/jobs/${jobId}/replay`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dead-letters"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      push("Job requeued");
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  if (!project) return null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-black uppercase">Dead Letter Queue</h1>
        <p className="text-sm text-nb-ink/60">Jobs that exhausted every retry attempt</p>
      </div>

      {queues && queues.length > 0 && (
        <Select
          value={effectiveQueueId}
          onChange={(e) => {
            setQueueId(e.target.value);
            setPage(1);
          }}
          className="w-56"
        >
          {queues.map((q) => (
            <option key={q.id} value={q.id}>
              {q.name}
            </option>
          ))}
        </Select>
      )}

      <div className="flex flex-col gap-3">
        {isLoading && (
          <Card className="text-sm text-nb-ink/50">Loading…</Card>
        )}
        {data?.items.map((entry) => (
          <Card key={entry.id} className="flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <Link to={`/jobs/${entry.job_id}`} className="font-black text-sm break-all hover:underline">
                Job {entry.job_id.slice(0, 8)}…
              </Link>
              <div className="text-xs text-nb-ink/60 mt-1">
                Failed after {entry.total_attempts} attempt(s) — {relativeTime(entry.moved_at)}
              </div>
              <div className="nb-border bg-nb-red inline-block px-2 py-1 mt-2 text-xs font-bold max-w-full truncate">
                {entry.failure_reason ?? "Unknown error"}
              </div>
            </div>
            <Button
              disabled={!!entry.replayed_at || replay.isPending}
              onClick={() => replay.mutate(entry.job_id)}
            >
              <RotateCcw size={14} className="inline mr-1 -mt-0.5" />
              {entry.replayed_at ? "Replayed" : "Replay"}
            </Button>
          </Card>
        ))}
        {data?.items.length === 0 && !isLoading && (
          <Card className="text-sm text-nb-ink/60 flex items-center gap-2">
            <Skull size={16} className="opacity-40" /> Nothing in the dead letter queue.
          </Card>
        )}
      </div>

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
    </div>
  );
}
