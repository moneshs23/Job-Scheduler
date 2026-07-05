import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from "chart.js";
import { Doughnut, Bar } from "react-chartjs-2";
import { Check, Circle } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../lib/errors";
import { StatCard, Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { StatCardSkeleton } from "../components/ui/Skeleton";
import type { OverviewStats } from "../lib/types";

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

export function DashboardPage() {
  const { project } = useProject();

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-overview", project?.id],
    queryFn: async () =>
      (await api.get<OverviewStats>(`/projects/${project!.id}/dashboard/overview`)).data,
    enabled: !!project,
    refetchInterval: 4000,
  });

  if (!project) {
    return <EmptyState />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-black uppercase">Dashboard</h1>
        <p className="text-sm text-nb-ink/60">{project.name} — live system overview</p>
      </div>

      {data && (data.active_queues + data.paused_queues === 0 || data.total_jobs === 0 || data.total_workers === 0) && (
        <OnboardingChecklist
          hasQueue={data.active_queues + data.paused_queues > 0}
          hasJob={data.total_jobs > 0}
          hasWorker={data.total_workers > 0}
        />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {isLoading || !data ? (
          Array.from({ length: 8 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard label="Total Jobs" value={data.total_jobs} accent="bg-nb-cyan" />
            <StatCard label="Queued" value={data.queued_jobs} accent="bg-nb-violet" />
            <StatCard label="Running" value={data.running_jobs} accent="bg-nb-yellow" />
            <StatCard label="Completed" value={data.completed_jobs} accent="bg-nb-lime" />
            <StatCard label="Failed" value={data.failed_jobs} accent="bg-nb-red" />
            <StatCard label="Dead Letter" value={data.dead_letter_jobs} accent="bg-nb-red" />
            <StatCard
              label="Active Workers"
              value={`${data.active_workers}/${data.total_workers}`}
              accent="bg-nb-orange"
            />
            <StatCard label="Failure Rate" value={`${data.failure_rate_pct}%`} accent="bg-nb-pink" />
          </>
        )}
      </div>

      {data && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <h2 className="font-black uppercase mb-3">Job Status Breakdown</h2>
            {data.total_jobs > 0 ? (
              <Doughnut
                data={{
                  labels: ["Queued", "Running", "Completed", "Failed", "Dead Letter"],
                  datasets: [
                    {
                      data: [
                        data.queued_jobs,
                        data.running_jobs,
                        data.completed_jobs,
                        data.failed_jobs,
                        data.dead_letter_jobs,
                      ],
                      backgroundColor: ["#4de8e8", "#ffd53d", "#b2ff3d", "#ff8a3d", "#ff5252"],
                      borderColor: "#111111",
                      borderWidth: 3,
                    },
                  ],
                }}
                options={{ plugins: { legend: { position: "bottom" } } }}
              />
            ) : (
              <p className="text-sm text-nb-ink/50 py-12 text-center">No jobs yet — create one to see it here.</p>
            )}
          </Card>

          <Card>
            <h2 className="font-black uppercase mb-3">Queues</h2>
            <Bar
              data={{
                labels: ["Active", "Paused"],
                datasets: [
                  {
                    label: "Queues",
                    data: [data.active_queues, data.paused_queues],
                    backgroundColor: ["#b2ff3d", "#ff5252"],
                    borderColor: "#111111",
                    borderWidth: 3,
                  },
                ],
              }}
              options={{
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
              }}
            />
            <div className="mt-4 flex items-center gap-2 text-sm font-bold">
              <span className="nb-border bg-nb-cyan px-2 py-1">
                Throughput: {data.throughput_per_min}/min
              </span>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function OnboardingChecklist({
  hasQueue,
  hasJob,
  hasWorker,
}: {
  hasQueue: boolean;
  hasJob: boolean;
  hasWorker: boolean;
}) {
  const steps = [
    { done: hasQueue, label: "Create a queue", to: "/queues" },
    { done: hasJob, label: "Create a job", to: "/jobs" },
    { done: hasWorker, label: "Start a worker", to: "/workers" },
  ];

  return (
    <Card className="bg-nb-yellow/20">
      <h2 className="font-black uppercase text-sm mb-3">Get set up</h2>
      <div className="flex flex-col sm:flex-row gap-2">
        {steps.map((step) => (
          <Link
            key={step.label}
            to={step.to}
            className="nb-border nb-shadow-sm nb-press bg-nb-paper px-3 py-2 flex items-center gap-2 flex-1 font-bold text-sm"
          >
            {step.done ? (
              <Check size={16} className="text-nb-lime shrink-0" strokeWidth={3} />
            ) : (
              <Circle size={16} className="text-nb-ink/30 shrink-0" />
            )}
            <span className={step.done ? "line-through text-nb-ink/50" : ""}>{step.label}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function EmptyState() {
  const { organization, refetchProjects } = useProject();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const createProject = useMutation({
    mutationFn: async () =>
      (await api.post(`/organizations/${organization!.id}/projects`, { name })).data,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      refetchProjects();
      setName("");
      push(`Project "${project.name}" created`);
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) createProject.mutate();
  };

  return (
    <Card className="max-w-lg">
      <h1 className="text-2xl font-black uppercase mb-2">Create your first project</h1>
      <p className="text-sm text-nb-ink/70 mb-4">
        Projects group queues, jobs, and workers. Everything in the scheduler is scoped to one.
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Label>Project name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Production" required />
        </div>
        <Button type="submit" disabled={createProject.isPending}>
          {createProject.isPending ? "Creating…" : "Create project"}
        </Button>
      </form>
    </Card>
  );
}
