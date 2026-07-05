# Database

PostgreSQL is the single source of truth for all durable state. Redis is a cache/notification
layer only — nothing there is required for correctness, and losing it degrades latency, not data.

Schema is managed by Alembic (`backend/migrations/`); the mapped models live in `backend/app/models/`.
See [Architecture.md](./Architecture.md#4-database-er-diagram) for the full ER diagram.

## Tables

| Table | Purpose |
|---|---|
| `users` | Login identity, global role, bcrypt password hash |
| `organizations` | Top-level tenant boundary |
| `organization_members` | User ↔ organization, with an org-scoped role (`owner`/`admin`/`member`) |
| `projects` | Groups queues/jobs/workers under one organization |
| `retry_policies` | Named backoff configs (`fixed`/`linear`/`exponential`/`custom`), reusable across queues |
| `queues` | Priority, concurrency limit, pause flag, optional retry policy |
| `jobs` | One row per job instance — status, payload, attempt count, scheduling fields |
| `scheduled_jobs` | 1:1 with a job; drives delayed/cron/recurring firing (see below) |
| `workers` | Registered worker processes, heartbeat timestamp, concurrency |
| `worker_heartbeats` | Time-series of heartbeat samples (cpu/memory/active_jobs) per worker |
| `job_executions` | One row per attempt — start/finish, duration, result or error |
| `job_logs` | Structured log lines attached to a job/execution |
| `dead_letter_queue` | Jobs that exhausted `max_attempts`, with the original payload preserved |
| `api_keys` | Hashed API keys (SHA-256), optionally scoped to one project |
| `audit_logs` | Who did what, before/after state, for compliance |

## Why Postgres, not just Redis

Redis Streams give you a fast queue, but Sidekiq/BullMQ/RabbitMQ-Redis backends all suffer the same
failure mode: if Redis loses data (eviction, restart without AOF, failover), jobs vanish silently.
Postgres gives ACID guarantees, foreign keys that make orphaned state impossible, and — critically —
`SELECT ... FOR UPDATE SKIP LOCKED`, which is what makes atomic claiming possible without a separate
distributed lock service.

## The claim query

This is the mechanism that lets N workers poll the same queue without ever double-executing a job:

```sql
BEGIN;

SELECT id FROM jobs
WHERE queue_id = :queue_id
  AND status IN ('queued', 'retry')
  AND (scheduled_at IS NULL OR scheduled_at <= now())
  AND (next_retry_at IS NULL OR next_retry_at <= now())
ORDER BY priority DESC, created_at ASC
LIMIT :limit
FOR UPDATE SKIP LOCKED;

UPDATE jobs SET status = 'claimed', claimed_at = now(), worker_id = :worker_id
WHERE id IN (<ids from above>)
RETURNING *;

COMMIT;
```

`SKIP LOCKED` means a second worker's identical query — running concurrently — simply skips any row
already locked by the first worker's open transaction, instead of blocking on it. No two workers ever
see the same row as a candidate. This is implemented in
[`app/repositories/job.py`](../backend/app/repositories/job.py)'s `claim_jobs()`, and is covered by
a concurrency test (`tests/integration/test_claim_engine.py::test_concurrent_claims_never_double_claim_the_same_job`)
that fires 4 simulated workers at 20 jobs simultaneously and asserts zero duplicates.

## Indexes worth knowing about

- `ix_jobs_claim_candidates (queue_id, status, priority, scheduled_at)` — covers the claim query's
  WHERE + ORDER BY so it doesn't degrade to a sequential scan as the `jobs` table grows.
- `ix_jobs_project_status (project_id, status)` — backs the dashboard's status-breakdown counts and
  the jobs list's status filter.
- `uq_project_idempotency_key (project_id, idempotency_key)` — enforces idempotent job creation.

## Cascade rules

- Deleting an `organization` cascades to its `projects`, which cascades to `queues`, `retry_policies`,
  and (via `queues`) `jobs`.
- Deleting a `job` cascades to its `job_executions`, `job_logs`, `scheduled_jobs` row, and
  `dead_letter_queue` entry.
- Deleting a `worker` sets `jobs.worker_id` and `job_executions.worker_id` to `NULL` (history is kept;
  only the live pointer is cleared) and cascades its `worker_heartbeats`.

## Recurring / cron jobs

There's no separate "job template" table. A cron/recurring job is a normal `jobs` row that stays in
`scheduled` status forever, paired with a `scheduled_jobs` row (`schedule_type = 'cron'`) holding the
cron expression and `next_run_at`. Every scheduler tick, `app/scheduler/service.py::scan_cron_jobs`
finds due schedules, **clones** the template job into a fresh `queued` row (a real, independent job
with its own execution history), and advances `next_run_at` via `croniter`. The template itself is
never claimed or executed — only its clones are.
