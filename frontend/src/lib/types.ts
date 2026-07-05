export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  settings: Record<string, unknown> | null;
  created_at: string;
}

export interface RetryPolicy {
  id: string;
  project_id: string;
  name: string;
  strategy: "fixed" | "linear" | "exponential" | "custom";
  max_retries: number;
  base_delay_ms: number;
  max_delay_ms: number;
  multiplier: number;
}

export interface Queue {
  id: string;
  project_id: string;
  name: string;
  priority: number;
  concurrency_limit: number;
  is_paused: boolean;
  retry_policy_id: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
}

export interface QueueMetrics {
  queue_id: string;
  queue_name: string;
  queued: number;
  scheduled: number;
  running: number;
  completed: number;
  failed: number;
  retry: number;
  dead_letter: number;
  is_paused: boolean;
  concurrency_limit: number;
  active_workers: number;
  throughput_per_min: number;
  avg_latency_ms: number | null;
}

export type JobStatus =
  | "queued"
  | "scheduled"
  | "claimed"
  | "running"
  | "completed"
  | "failed"
  | "retry"
  | "cancelled"
  | "dead_letter";

export interface Job {
  id: string;
  queue_id: string;
  project_id: string;
  name: string;
  status: JobStatus;
  priority: number;
  payload: Record<string, unknown> | null;
  idempotency_key: string | null;
  attempt_count: number;
  max_attempts: number;
  worker_id: string | null;
  batch_id: string | null;
  scheduled_at: string | null;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  next_retry_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface JobExecution {
  id: string;
  job_id: string;
  worker_id: string | null;
  attempt_number: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  error_stack: string | null;
}

export interface JobLog {
  id: string;
  job_id: string;
  execution_id: string | null;
  level: string;
  message: string;
  context: Record<string, unknown> | null;
  logged_at: string;
}

export interface DeadLetterEntry {
  id: string;
  job_id: string;
  queue_id: string;
  original_payload: Record<string, unknown> | null;
  failure_reason: string | null;
  total_attempts: number;
  moved_at: string;
  replayed_at: string | null;
}

export interface Worker {
  id: string;
  project_id: string;
  hostname: string;
  worker_type: string;
  status: "starting" | "idle" | "busy" | "draining" | "stopped";
  concurrency: number;
  active_jobs: number;
  capabilities: Record<string, unknown> | null;
  registered_at: string;
  last_heartbeat_at: string | null;
}

export interface OverviewStats {
  total_jobs: number;
  queued_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  dead_letter_jobs: number;
  active_workers: number;
  total_workers: number;
  active_queues: number;
  paused_queues: number;
  throughput_per_min: number;
  failure_rate_pct: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
