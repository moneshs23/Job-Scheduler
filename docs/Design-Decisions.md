# Design Decisions

Short explanations of the choices that shape this system, and what they trade off against.

## Postgres as the queue, Redis as a doorbell

BullMQ and most Redis-based queues make Redis the source of truth. That's fast, but it means a Redis
data-loss event (eviction under memory pressure, a restart without AOF fsync, a botched failover)
silently drops jobs. This system instead keeps every durable fact — job state, attempt count,
execution history — in Postgres, and uses Redis purely as a low-latency wake-up signal (Streams) and
fan-out bus (Pub/Sub for the WebSocket hub). If Redis disappears entirely, workers fall back to
polling Postgres directly on `WORKER_POLL_INTERVAL_MS`; nothing is lost, throughput just degrades to
poll-interval latency instead of near-instant.

## `SELECT ... FOR UPDATE SKIP LOCKED` instead of a distributed lock

The alternative designs — a Redis `SETNX` lock per job, or a dedicated coordinator service — both add
a second system that has to agree with Postgres about job state, which is exactly the kind of
two-phase-commit problem you don't want. `SKIP LOCKED` gets the same atomicity guarantee for free from
a database transaction: two workers running the identical claim query concurrently will never see the
same row, because the second worker's query simply skips whatever the first worker's open transaction
has locked. No lock service, no lease renewal, no split-brain window. The cost is that this only works
because Postgres is already the source of truth — it wouldn't help if job state lived in Redis.

## `job.max_attempts` as the retry cap, not `retry_policy.max_retries`

Both fields exist on purpose but answer different questions: `RetryPolicy` (attached to a *queue*)
answers "how should the delay between attempts grow" — fixed, linear, exponential, or a custom list.
`Job.max_attempts` (set per job at creation time) answers "how many times should *this* job be tried."
Early in implementation the execution engine used the policy's `max_retries` for both, which meant a
job created with `max_attempts: 2` actually got 4 attempts (the queue's default policy allowed 3
retries beyond the first try) — caught by manual end-to-end testing, not by a unit test, because the
unit tests for each piece were individually correct. The fix: the engine reads `job.max_attempts` to
decide whether to retry or dead-letter, and asks the retry policy only for the delay. Lesson generalized:
when two config sources can each independently answer "how many," decide upfront which one wins.

## `server_default=func.now()`, never `server_default="now()"`

A second bug caught by end-to-end testing rather than unit tests, and worth documenting because it's
easy to reintroduce: nine columns across eight models (`jobs.created_at`, `queues.created_at`,
`api_keys.created_at`, `audit_logs.created_at`, `organization_members.joined_at`,
`workers.registered_at`, `worker_heartbeats.heartbeat_at`, `job_logs.logged_at`,
`dead_letter_queue.moved_at`) were declared with `server_default="now()"` — a bare Python string.
SQLAlchemy compiles a bare string server default as a **quoted SQL string literal**, not a function
call. Postgres then parses that literal once, at the moment the `CREATE TABLE` / `ALTER TABLE` DDL
runs, and freezes it into a fixed timestamp default — so *every row ever inserted afterward* got the
exact same `created_at`, down to the microsecond, no matter when it was actually created. Unit tests
never caught it because each test run creates its own schema fresh and finishes in milliseconds, so
"every row has an identical timestamp" looked indistinguishable from "every row was created quickly."
It surfaced as relative-time UI (job lists, audit log) showing implausible ages like "2h ago" for a
job created seconds earlier.

The fix is `server_default=func.now()` (a live SQL function reference, compiles to `DEFAULT now()`
with no quotes), which Postgres evaluates fresh per row. Two follow-ups to make sure this specific
mistake can't silently ship again: `migrations/env.py` now sets `compare_server_default=True`, because
Alembic's autogenerate ignores `server_default` changes entirely unless you opt in — the initial
migration was generated *before* that flag existed, which is exactly how nine wrong defaults made it
into a committed migration without a diff ever flagging them. And
`tests/integration/test_schema_defaults.py` asserts every timestamp-default column's
`information_schema.columns.column_default` contains `now()` and isn't a quoted literal.

## Cron/recurring jobs clone instances rather than templating at execution time

The ER schema ties `scheduled_jobs` to a job 1:1. Rather than inventing a separate "recurring job
definition" table, a cron job is a normal job that never leaves `scheduled` status — the scheduler's
cron scanner clones it into a fresh, independently-tracked `queued` job on every firing and advances
the template's `next_run_at`. This keeps the schema uniform (every job has the same execution/log/DLQ
relationships, whether it came from a one-off create or a cron firing) at the cost of one extra row
per firing, which is a fine trade for the audit trail it buys you — every recurring firing has its own
full execution history instead of overwriting a single row.

## Workers are scoped to one project

`workers.project_id` is `NOT NULL`. This mirrors how BullMQ/Sidekiq workers are typically deployed —
one worker fleet per logical service/queue namespace — rather than a single global worker pool serving
every tenant. It also keeps the claim query cheap (index on `queue_id`, not a cross-tenant scan) and
means a noisy tenant can't starve another tenant's concurrency slots. The trade-off: multi-project
deployments run one worker process (or fleet) per project rather than sharing one pool, which is more
processes to operate but gives hard isolation for free.

## Leader election for the scheduler, not for workers

Workers don't need leader election — `SKIP LOCKED` already makes concurrent claiming safe, so you
scale workers by just running more of them. The scheduler is different: `scan_delayed_jobs` and
`scan_cron_jobs` aren't idempotent-by-locking the way claiming is (nothing stops two scheduler
replicas from both flipping the same delayed job to `queued`, which is harmless, or both cloning the
same cron firing, which duplicates work). A cheap Redis `SET NX EX` lock, renewed on an interval well
inside its TTL, lets you run multiple scheduler replicas for availability while guaranteeing only one
is actively scanning at a time — if the leader dies, the lock expires and another replica picks it up
within `SCHEDULER_LEADER_LOCK_TTL_SEC`.

## Neobrutalism for the dashboard

Thick black borders, hard (non-blurred) offset shadows, and saturated flat colors instead of gradients
or soft elevation. For an operations dashboard — where the job is scanning many small numbers and
status badges quickly — high contrast and unambiguous edges read faster than a softer, more decorative
system would. It also happens to be a deliberate, opinionated choice rather than a generic component
library default, which was the explicit brief.
