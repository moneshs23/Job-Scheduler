# Distributed Job Scheduler — Architecture

> **Status:** Implemented. This document reflects the design as built — see the repo root README for what's running and verified.

A production-grade distributed job scheduler comparable to Temporal, BullMQ, Sidekiq, Celery, and cloud worker systems. Designed for millions of jobs, horizontal scale, atomic execution, and enterprise observability.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Microservice Architecture](#2-microservice-architecture)
3. [Folder Structure](#3-folder-structure)
4. [Database ER Diagram](#4-database-er-diagram)
5. [Sequence Diagrams](#5-sequence-diagrams)
6. [Worker Lifecycle](#6-worker-lifecycle-diagram)
7. [Job Lifecycle](#7-job-lifecycle-diagram)
8. [Queue Flow](#8-queue-flow-diagram)
9. [Deployment Diagram](#9-deployment-diagram)
10. [Component Rationale](#10-component-rationale)
11. [Frontend Design — Neobrutalism Theme](#11-frontend-design--neobrutalism-theme)
12. [Technology Decisions Summary](#12-technology-decisions-summary)

---

## 1. High-Level Architecture

The system follows a **modular monolith with horizontally scalable worker processes**. The API, scheduler, and workers share the same codebase but run as separate deployable processes — a pragmatic pattern used by Sidekiq (web + workers) and Celery (beat + workers + API).

```mermaid
flowchart TB
    subgraph Client Layer
        UI["React Dashboard<br/>(Neobrutalism UI)"]
        CLI["CLI / SDK / Webhooks"]
    end

    subgraph Gateway Layer
        LB["Load Balancer<br/>(Nginx / Traefik)"]
    end

    subgraph Application Layer
        API["FastAPI API Server<br/>REST + WebSocket + OpenAPI"]
        SCHED["Scheduler Service<br/>(APScheduler)"]
    end

    subgraph Data Layer
        PG[("PostgreSQL<br/>Source of Truth")]
        REDIS[("Redis<br/>Streams · Cache · Pub/Sub")]
    end

    subgraph Worker Layer
        W1["Worker Node 1"]
        W2["Worker Node 2"]
        WN["Worker Node N"]
    end

    subgraph Observability
        PROM["Prometheus"]
        GRAF["Grafana"]
        LOGS["Structured JSON Logs"]
    end

    UI -->|REST / WS| LB
    CLI -->|REST| LB
    LB --> API

    API --> PG
    API --> REDIS
    SCHED --> PG
    SCHED -->|Publish ready jobs| REDIS

    W1 -->|Claim FOR UPDATE SKIP LOCKED| PG
    W2 -->|Claim FOR UPDATE SKIP LOCKED| PG
    WN -->|Claim FOR UPDATE SKIP LOCKED| PG

    W1 -->|Heartbeats · Logs| PG
    W2 -->|Heartbeats · Logs| PG
    WN -->|Heartbeats · Logs| PG

    W1 -->|Stream consume| REDIS
    W2 -->|Stream consume| REDIS
    WN -->|Stream consume| REDIS

    API -->|Pub/Sub events| REDIS
    REDIS -->|Realtime push| UI

    API --> PROM
    SCHED --> PROM
    W1 --> PROM
    W2 --> PROM
    WN --> PROM

    API --> LOGS
    SCHED --> LOGS
    W1 --> LOGS
    WN --> LOGS

    PROM --> GRAF
```

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Single source of truth** | PostgreSQL holds all durable state (jobs, queues, workers, audit) |
| **Atomic claiming** | `SELECT … FOR UPDATE SKIP LOCKED` inside a transaction |
| **At-least-once delivery** | Claim + idempotency keys + execution records prevent duplicate side effects |
| **Separation of concerns** | API (control plane) ≠ Scheduler (time plane) ≠ Workers (execution plane) |
| **Fail-safe retries** | Configurable backoff policies with DLQ escape hatch |
| **Observable by default** | Prometheus metrics, structured logs, WebSocket live feed |

---

## 2. Microservice Architecture

Although deployed from one repository, the runtime is split into **five logical services** that can be scaled independently.

```mermaid
flowchart LR
    subgraph Control Plane
        AUTH["Auth Service<br/>JWT · RBAC · API Keys"]
        PROJ["Project Service<br/>Orgs · Projects · Queues"]
        JOB_API["Job API Service<br/>CRUD · Search · Cancel"]
    end

    subgraph Time Plane
        CRON["Cron Scanner<br/>APScheduler"]
        DELAY["Delay Scanner<br/>Scheduled → Queued"]
        RECUR["Recurring Engine<br/>Cron expressions"]
    end

    subgraph Execution Plane
        CLAIM["Claim Engine<br/>PG SKIP LOCKED"]
        EXEC["Execution Engine<br/>Concurrency pool"]
        RETRY["Retry Engine<br/>Backoff · DLQ"]
    end

    subgraph Realtime Plane
        WS["WebSocket Hub"]
        PUBSUB["Redis Pub/Sub Bridge"]
    end

    subgraph Observability Plane
        METRICS["Metrics Collector"]
        HEALTH["Health Probes"]
        AUDIT["Audit Logger"]
    end

    AUTH --> PROJ
    PROJ --> JOB_API
    JOB_API --> CRON
    JOB_API --> DELAY
    CRON --> RECUR
    DELAY --> CLAIM
    RECUR --> CLAIM
    CLAIM --> EXEC
    EXEC --> RETRY
    EXEC --> WS
    RETRY --> WS
    WS --> PUBSUB

    EXEC --> METRICS
    CLAIM --> METRICS
    JOB_API --> AUDIT
    AUTH --> AUDIT
```

### Service Responsibilities

| Service | Process | Scale Strategy |
|---------|---------|----------------|
| **API Server** | `uvicorn app.main:app` | Horizontal — stateless behind LB |
| **Scheduler** | `python -m app.scheduler.main` | Single leader with Redis distributed lock (optional HA standby) |
| **Worker** | `python -m app.workers.main` | Horizontal — add nodes per queue load |
| **WebSocket** | Embedded in API (or separate if needed) | Sticky sessions or Redis-backed fan-out |
| **Metrics** | `/metrics` endpoint on each process | Scraped by Prometheus |

### Inter-Service Communication

```mermaid
flowchart TB
    subgraph Sync
        REST["REST API calls<br/>(Client → API)"]
        PG_TX["PostgreSQL transactions<br/>(Claim, state updates)"]
    end

    subgraph Async
        STREAMS["Redis Streams<br/>(Job dispatch notifications)"]
        PUBSUB2["Redis Pub/Sub<br/>(Dashboard realtime)"]
        POLL["Worker poll loop<br/>(DB + Stream hybrid)"]
    end

    REST --> PG_TX
    SCHED --> STREAMS
    STREAMS --> POLL
    POLL --> PG_TX
    PG_TX --> PUBSUB2
    PUBSUB2 --> WS2["WebSocket clients"]
```

**Hybrid dispatch model:** The scheduler writes job state to PostgreSQL (durable) and publishes a lightweight notification to Redis Streams (fast wake-up). Workers primarily claim from PostgreSQL (correctness) and use Streams as a hint to reduce idle polling latency.

---

## 3. Folder Structure

> This reflects the repository exactly as implemented (verified against the working tree, not the
> pre-implementation plan) — see [github.com/moneshs23/Job-Schedular](https://github.com/moneshs23/Job-Schedular).

```
distributed-job-scheduler/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── docs/
│   ├── Architecture.md          ← this document
│   ├── Design-Decisions.md
│   ├── Database.md
│   ├── API.md
│   └── Deployment.md
│
├── docker/
│   └── prometheus/
│       └── prometheus.yml
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/                  # initial schema, queue unique constraint, now() default fix
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint
│   │   ├── config/
│   │   │   ├── settings.py            # Pydantic Settings (env-driven)
│   │   │   └── constants.py           # job/worker status enums, Redis key prefixes
│   │   ├── api/
│   │   │   ├── router.py              # Aggregates all routers under /api/v1
│   │   │   └── routes/
│   │   │       ├── auth.py            # register/login/refresh/me/api-keys
│   │   │       ├── organizations.py   # orgs, projects, audit-logs
│   │   │       ├── queues.py          # queues + retry-policies
│   │   │       ├── jobs.py            # jobs + dead-letter-queue
│   │   │       ├── workers.py         # registration, heartbeats, shutdown
│   │   │       ├── dashboard.py       # overview stats
│   │   │       ├── websocket.py       # /ws realtime endpoint
│   │   │       └── health.py          # DB + Redis health check
│   │   ├── auth/
│   │   │   ├── security.py            # JWT issue/verify, bcrypt hashing, API key generation
│   │   │   └── dependencies.py        # Principal resolution, RBAC, project-scope checks
│   │   ├── models/                    # SQLAlchemy 2.0 ORM — 9 files, 15 tables
│   │   │   ├── base.py                # Declarative base, timestamp/UUID mixins
│   │   │   ├── organization.py        # User, Organization, OrganizationMember, Project
│   │   │   ├── queue.py               # Queue, RetryPolicy
│   │   │   ├── job.py                 # Job, ScheduledJob
│   │   │   ├── worker.py              # Worker, WorkerHeartbeat
│   │   │   ├── execution.py           # JobExecution, JobLog
│   │   │   ├── dead_letter.py         # DeadLetterEntry
│   │   │   ├── api_key.py             # APIKey
│   │   │   └── audit.py               # AuditLog
│   │   ├── schemas/                   # Pydantic request/response models (mirrors models/)
│   │   ├── repositories/              # Data-access layer — one repo per model, Repository pattern
│   │   ├── services/                  # Business logic — auth, project, queue, job, worker, dashboard, audit
│   │   ├── scheduler/
│   │   │   ├── main.py                # Scheduler process entrypoint
│   │   │   ├── service.py             # Delay scanner + cron scanner
│   │   │   └── leader.py              # Redis-lock leader election for HA
│   │   ├── workers/
│   │   │   ├── main.py                # Worker process entrypoint (signal handling)
│   │   │   └── worker.py              # Poll → claim → execute → heartbeat → graceful shutdown
│   │   ├── execution/
│   │   │   ├── engine.py              # Runs one claimed job; decides retry vs. dead-letter
│   │   │   └── registry.py            # Pluggable task handlers (echo, sleep, http_request, ...)
│   │   ├── retry/
│   │   │   └── policy.py              # fixed/linear/exponential/custom backoff math
│   │   ├── queues/
│   │   │   ├── redis_client.py
│   │   │   ├── streams.py             # Redis Streams — claim wake-up signal
│   │   │   └── pubsub.py              # Redis Pub/Sub — WebSocket event bus
│   │   ├── websocket/
│   │   │   └── hub.py                 # Connection registry + broadcast
│   │   ├── middleware/
│   │   │   ├── rate_limit.py          # Fixed-window, Redis-backed, per-IP
│   │   │   ├── request_logging.py     # Structured request logs + Prometheus timing
│   │   │   └── exception_handler.py   # Uniform {"error": ...} responses
│   │   ├── database/
│   │   │   └── session.py             # Async engine + session factory
│   │   ├── logging/
│   │   │   └── setup.py               # structlog JSON configuration
│   │   └── monitoring/
│   │       └── metrics.py             # Prometheus counters/histograms
│   └── tests/
│       ├── conftest.py                # Test DB/session/client fixtures
│       ├── unit/
│       │   ├── test_retry_policy.py
│       │   └── test_auth_security.py
│       └── integration/
│           ├── test_claim_engine.py           # Proves SKIP LOCKED never double-claims
│           ├── test_api_job_lifecycle.py
│           ├── test_validation_and_audit.py
│           └── test_schema_defaults.py        # Regression guard for the now() default bug
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    ├── Dockerfile
    ├── nginx.conf
    └── src/
        ├── main.tsx
        ├── App.tsx                   # Routes + provider tree
        ├── index.css                 # Neobrutalism design tokens (theme-aware)
        ├── lib/
        │   ├── api.ts                 # axios instance + refresh-token interceptor
        │   ├── types.ts               # Shared TS types mirroring backend schemas
        │   ├── errors.ts              # Axios error → user-facing message
        │   └── format.ts              # Relative time, duration, number formatting
        ├── hooks/
        │   ├── useRealtime.ts         # WebSocket → React Query cache invalidation
        │   ├── useTheme.ts            # Dark/light toggle, persisted
        │   └── useDebounce.ts
        ├── context/
        │   ├── AuthContext.tsx
        │   ├── ProjectContext.tsx     # Current org/project selection
        │   └── ToastContext.tsx
        ├── components/
        │   ├── Layout.tsx             # Sidebar nav + realtime indicator
        │   ├── ProtectedRoute.tsx
        │   └── ui/                    # Button, Card, Modal, Badge, ConfirmDialog, Skeleton, Input
        └── pages/
            ├── Login.tsx / Register.tsx
            ├── Dashboard.tsx          # Overview cards, charts, onboarding checklist
            ├── Queues.tsx             # Priority, concurrency, pause/resume, retry policies
            ├── Jobs.tsx / JobDetail.tsx
            ├── Workers.tsx            # Live status + copy-paste start command
            ├── DeadLetterQueue.tsx
            ├── ApiKeys.tsx
            └── AuditLog.tsx
```

---

## 4. Database ER Diagram

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        enum role "admin|member|viewer"
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    ORGANIZATIONS {
        uuid id PK
        string name
        string slug UK
        timestamp created_at
    }

    ORGANIZATION_MEMBERS {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        enum role "owner|admin|member"
        timestamp joined_at
    }

    PROJECTS {
        uuid id PK
        uuid organization_id FK
        string name
        string slug
        jsonb settings
        timestamp created_at
    }

    QUEUES {
        uuid id PK
        uuid project_id FK
        string name
        int priority "0-100"
        int concurrency_limit
        boolean is_paused
        uuid retry_policy_id FK
        jsonb config
        timestamp created_at
    }

    RETRY_POLICIES {
        uuid id PK
        uuid project_id FK
        string name
        enum strategy "fixed|linear|exponential|custom"
        int max_retries
        int base_delay_ms
        int max_delay_ms
        float multiplier
        jsonb custom_delays
    }

    JOBS {
        uuid id PK
        uuid queue_id FK
        uuid project_id FK
        string name
        enum status "queued|scheduled|claimed|running|completed|failed|retry|cancelled|dead_letter"
        int priority
        jsonb payload
        jsonb metadata
        string idempotency_key UK
        int attempt_count
        int max_attempts
        uuid worker_id FK
        timestamp scheduled_at
        timestamp claimed_at
        timestamp started_at
        timestamp completed_at
        timestamp next_retry_at
        timestamp created_at
    }

    SCHEDULED_JOBS {
        uuid id PK
        uuid job_id FK
        enum schedule_type "delay|cron|recurring"
        string cron_expression
        timestamp run_at
        timestamp last_run_at
        timestamp next_run_at
        boolean is_active
    }

    WORKERS {
        uuid id PK
        uuid project_id FK
        string hostname
        string worker_type
        enum status "starting|idle|busy|draining|stopped"
        int concurrency
        int active_jobs
        jsonb capabilities
        timestamp registered_at
        timestamp last_heartbeat_at
    }

    WORKER_HEARTBEATS {
        uuid id PK
        uuid worker_id FK
        enum status
        int active_jobs
        float cpu_percent
        float memory_mb
        jsonb metadata
        timestamp heartbeat_at
    }

    JOB_EXECUTIONS {
        uuid id PK
        uuid job_id FK
        uuid worker_id FK
        int attempt_number
        enum status "running|completed|failed|cancelled"
        timestamp started_at
        timestamp finished_at
        int duration_ms
        jsonb result
        string error_message
        string error_stack
    }

    JOB_LOGS {
        uuid id PK
        uuid job_id FK
        uuid execution_id FK
        enum level "debug|info|warn|error"
        text message
        jsonb context
        timestamp logged_at
    }

    DEAD_LETTER_QUEUE {
        uuid id PK
        uuid job_id FK
        uuid queue_id FK
        jsonb original_payload
        string failure_reason
        int total_attempts
        timestamp moved_at
    }

    API_KEYS {
        uuid id PK
        uuid user_id FK
        uuid project_id FK
        string key_hash
        string name
        jsonb scopes
        timestamp expires_at
        timestamp created_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        string action
        string resource_type
        uuid resource_id
        jsonb before_state
        jsonb after_state
        string ip_address
        timestamp created_at
    }

    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERS : has
    USERS ||--o{ ORGANIZATION_MEMBERS : belongs
    ORGANIZATIONS ||--o{ PROJECTS : owns
    PROJECTS ||--o{ QUEUES : contains
    PROJECTS ||--o{ RETRY_POLICIES : defines
    QUEUES ||--o| RETRY_POLICIES : uses
    QUEUES ||--o{ JOBS : holds
    PROJECTS ||--o{ JOBS : scopes
    JOBS ||--o| SCHEDULED_JOBS : schedules
    JOBS ||--o{ JOB_EXECUTIONS : runs
    JOBS ||--o{ JOB_LOGS : logs
    JOBS ||--o| DEAD_LETTER_QUEUE : dead_letters
    WORKERS ||--o{ JOB_EXECUTIONS : executes
    WORKERS ||--o{ WORKER_HEARTBEATS : pulses
    WORKERS ||--o{ JOBS : claims
    USERS ||--o{ API_KEYS : owns
    USERS ||--o{ AUDIT_LOGS : performs
```

### Key Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| `jobs` | `(queue_id, status, priority DESC, created_at)` | Priority claim query |
| `jobs` | `(status, scheduled_at)` WHERE status = 'scheduled' | Delay scanner |
| `jobs` | `(status, next_retry_at)` WHERE status = 'retry' | Retry scanner |
| `jobs` | `(idempotency_key)` UNIQUE | Dedup |
| `jobs` | `(project_id, status, created_at DESC)` | Dashboard listing |
| `workers` | `(project_id, status, last_heartbeat_at)` | Health checks |
| `job_executions` | `(job_id, attempt_number)` | History lookup |
| `audit_logs` | `(organization_id, created_at DESC)` | Compliance queries |

---

## 5. Sequence Diagrams

### 5.1 Job Creation (Immediate)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI
    participant Auth as Auth Service
    participant JS as Job Service
    participant PG as PostgreSQL
    participant RS as Redis Stream
    participant WS as WebSocket

    User->>API: POST /api/v1/jobs
    API->>Auth: Validate JWT + RBAC
    Auth-->>API: User context
    API->>JS: create_job(payload, queue_id)
    JS->>PG: BEGIN TRANSACTION
    JS->>PG: INSERT job (status=queued)
    JS->>PG: COMMIT
    JS->>RS: XADD job:queue:{id} notification
    JS->>WS: Publish job.created event
    JS-->>API: JobResponse
    API-->>User: 201 Created
    WS-->>User: Realtime dashboard update
```

### 5.2 Atomic Job Claim & Execution

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker
    participant CE as Claim Engine
    participant PG as PostgreSQL
    participant EE as Execution Engine
    participant RP as Retry Policy
    participant DLQ as Dead Letter Queue
    participant WS as WebSocket

    loop Poll Loop
        W->>CE: claim_next_job(queue_ids)
        CE->>PG: BEGIN
        CE->>PG: SELECT id FROM jobs<br/>WHERE status IN (queued, retry)<br/>AND queue_id = ANY(...)<br/>AND (next_retry_at IS NULL OR next_retry_at <= NOW())<br/>ORDER BY priority DESC, created_at<br/>LIMIT 1<br/>FOR UPDATE SKIP LOCKED
        alt Job found
            CE->>PG: UPDATE jobs SET status=claimed,<br/>worker_id=?, claimed_at=NOW()
            CE->>PG: COMMIT
            CE-->>W: Job instance

            W->>EE: execute(job)
            EE->>PG: UPDATE status=running, started_at=NOW()
            EE->>PG: INSERT job_execution

            alt Success
                EE->>PG: UPDATE status=completed
                EE->>WS: job.completed
            else Failure
                EE->>PG: UPDATE status=failed
                EE->>RP: calculate_next_retry(job)
                alt Retries remaining
                    RP->>PG: UPDATE status=retry,<br/>next_retry_at=?, attempt_count++
                    EE->>WS: job.retry_scheduled
                else Max retries exceeded
                    RP->>DLQ: move_to_dlq(job)
                    RP->>PG: UPDATE status=dead_letter
                    EE->>WS: job.dead_lettered
                end
            end
        else No job
            CE->>PG: ROLLBACK
            W->>W: Sleep / await Stream hint
        end
    end
```

### 5.3 Scheduled / Cron Job Activation

```mermaid
sequenceDiagram
    autonumber
    participant APS as APScheduler
    participant DS as Delay Scanner
    participant RE as Recurring Engine
    participant PG as PostgreSQL
    participant RS as Redis Stream
    participant W as Worker

    loop Every 1s
        APS->>DS: scan_due_jobs()
        DS->>PG: SELECT * FROM jobs j<br/>JOIN scheduled_jobs s ON ...<br/>WHERE status=scheduled<br/>AND (run_at <= NOW() OR next_run_at <= NOW())
        DS->>PG: UPDATE status=queued
        DS->>RS: XADD notification per queue
    end

    loop Cron tick
        APS->>RE: scan_cron_expressions()
        RE->>PG: Find recurring scheduled_jobs
        RE->>PG: INSERT new job instance (queued)
        RE->>PG: UPDATE scheduled_jobs.next_run_at
        RE->>RS: XADD notification
    end

    RS-->>W: Stream message (wake hint)
    W->>W: Immediate claim attempt
```

### 5.4 Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React App
    participant API as FastAPI
    participant Auth as Auth Service
    participant PG as PostgreSQL
    participant Redis as Redis

    User->>UI: Login (email, password)
    UI->>API: POST /auth/login
    API->>Auth: authenticate()
    Auth->>PG: SELECT user by email
    Auth->>Auth: verify bcrypt hash
    Auth->>Auth: generate access + refresh JWT
    Auth->>Redis: Store refresh token JTI
    Auth-->>API: TokenPair
    API-->>UI: 200 + tokens
    UI->>UI: Store tokens (httpOnly cookie / memory)

    Note over UI,API: Subsequent requests
    UI->>API: GET /api/v1/jobs + Bearer token
    API->>Auth: decode + validate JWT
    API->>Auth: check RBAC for project
    API-->>UI: 200 Job list
```

---

## 6. Worker Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> Starting: Process spawn

    Starting --> Registering: Load config
    Registering --> Idle: INSERT worker row\nSend registration heartbeat

    Idle --> Claiming: Poll interval /\nStream notification
    Claiming --> Executing: Job claimed (PG txn)
    Claiming --> Idle: No jobs available

    Executing --> Idle: Job completed
    Executing --> Retry: Job failed\n(retries remain)
    Executing --> DLQ: Job failed\n(max retries)
    Executing --> Cancelling: Cancel signal received

    Cancelling --> Idle: Graceful cancel done
    Retry --> Idle: Retry scheduled\n(back to PG queue)

    Idle --> Draining: SIGTERM / SIGINT\n(drain mode)
    Executing --> Draining: SIGTERM received
    Draining --> Stopped: Active jobs finish\nOR timeout exceeded

    Stopped --> [*]: UPDATE worker status=stopped\nFinal heartbeat

    note right of Executing
        Heartbeat every 5s
        Updates active_jobs count
        Renews claim lease (optional)
    end note

    note right of Draining
        No new claims
        Wait for in-flight jobs
        Configurable drain timeout
    end note
```

### Worker Internal Architecture

```mermaid
flowchart TB
    subgraph Worker Process
        MAIN["main.py\nasyncio event loop"]
        POLL["Claim Poller\n(adaptive interval)"]
        POOL["Concurrency Pool\n(asyncio.Semaphore)"]
        HB["Heartbeat Loop\n(background task)"]
        SHUT["Signal Handler\nSIGTERM/SIGINT"]
        EXEC["Job Executor\n(user handler registry)"]

        MAIN --> POLL
        MAIN --> HB
        MAIN --> SHUT
        POLL --> POOL
        POOL --> EXEC
        SHUT -->|drain| POOL
    end

    POLL --> PG2[("PostgreSQL")]
    HB --> PG2
    EXEC --> PG2
    POLL --> RS2[("Redis Stream")]
```

---

## 7. Job Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> Queued: Immediate job created

    [*] --> Scheduled: Delayed / Cron / Recurring
    Scheduled --> Queued: Scheduler activates\n(scheduled_at reached)

    Queued --> Claimed: Worker claims\n(FOR UPDATE SKIP LOCKED)
    Claimed --> Running: Execution starts

    Running --> Completed: Success
    Running --> Failed: Unhandled error
    Running --> Cancelled: User cancel / timeout

    Failed --> Retry: attempt < max_retries\n(backoff applied)
    Retry --> Queued: next_retry_at reached

    Failed --> DeadLetter: attempt >= max_retries
    DeadLetter --> Queued: Manual replay\n(DLQ admin action)

    Completed --> [*]
    Cancelled --> [*]
    DeadLetter --> [*]

    note right of Queued
        Priority ordering within queue
        Respects queue pause flag
        Respects concurrency limit
    end note

    note right of Retry
        Strategies:
        - Fixed delay
        - Linear backoff
        - Exponential backoff
        - Custom delay array
    end note
```

### Job Type Matrix

| Type | Initial State | Trigger | Re-queue |
|------|--------------|---------|----------|
| **Immediate** | `queued` | API create | No |
| **Delayed** | `scheduled` | `scheduled_at` | No |
| **Cron** | `scheduled` | Cron expression | Yes — new instance each tick |
| **Recurring** | `scheduled` | Interval / cron | Yes |
| **Batch** | `queued` (parent) | Parent dispatches children | Children independent |

---

## 8. Queue Flow Diagram

```mermaid
flowchart TB
    subgraph Ingress
        API_CREATE["API: Create Job"]
        SCHED_ACTIVATE["Scheduler: Activate"]
        RETRY_READY["Retry: next_retry_at due"]
        DLQ_REPLAY["DLQ: Manual Replay"]
    end

    subgraph Queue Engine
        QM["Queue Manager"]
        PAUSE{"Queue Paused?"}
        PRIO["Priority Sorter<br/>priority DESC, FIFO"]
        CONC{"Concurrency<br/>Available?"}
        CLAIM2["Atomic Claim<br/>SKIP LOCKED"]
    end

    subgraph Queues
        QH["high-priority"]
        QD["default"]
        QL["low-priority"]
    end

    subgraph Dispatch
        RS3["Redis Stream<br/>queue:{id}:notify"]
        WORKERS["Worker Pool"]
    end

    subgraph Egress
        SUCCESS["Completed"]
        FAIL["Failed → Retry Engine"]
        DEAD["Dead Letter Queue"]
    end

    API_CREATE --> QM
    SCHED_ACTIVATE --> QM
    RETRY_READY --> QM
    DLQ_REPLAY --> QM

    QM --> QH
    QM --> QD
    QM --> QL

    QH --> PAUSE
    QD --> PAUSE
    QL --> PAUSE

    PAUSE -->|No| PRIO
    PAUSE -->|Yes| WAIT["Jobs wait in PG"]

    PRIO --> CONC
    CONC -->|Yes| CLAIM2
    CONC -->|No| WAIT2["Workers poll later"]

    CLAIM2 --> RS3
    RS3 --> WORKERS
    CLAIM2 --> WORKERS

    WORKERS --> SUCCESS
    WORKERS --> FAIL
    FAIL -->|max retries| DEAD
    FAIL -->|retries left| RETRY_READY
```

### Priority Queue Implementation

Jobs are **not** stored in Redis priority queues (which lack durability). PostgreSQL holds ordering:

```sql
-- Claim query (simplified)
SELECT j.id
FROM jobs j
JOIN queues q ON j.queue_id = q.id
WHERE j.status IN ('queued', 'retry')
  AND q.is_paused = false
  AND j.queue_id = ANY(:worker_queue_ids)
  AND (j.next_retry_at IS NULL OR j.next_retry_at <= NOW())
ORDER BY j.priority DESC, j.created_at ASC
LIMIT 1
FOR UPDATE OF j SKIP LOCKED;
```

Queue-level `concurrency_limit` is enforced by counting active (`claimed`, `running`) jobs per queue before claim.

---

## 9. Deployment Diagram

```mermaid
flowchart TB
    subgraph Internet
        USER["Browser / API Clients"]
    end

    subgraph Docker Host / Kubernetes Cluster
        subgraph Edge
            NGINX["Nginx Reverse Proxy<br/>TLS termination<br/>Rate limit"]
        end

        subgraph Frontend
            FE1["Frontend Container<br/>React static (Vite build)"]
        end

        subgraph Backend
            API1["API Replica 1<br/>FastAPI"]
            API2["API Replica 2<br/>FastAPI"]
            SCHED1["Scheduler<br/>(1 leader)"]
        end

        subgraph Workers
            WK1["Worker Replica 1<br/>concurrency=10"]
            WK2["Worker Replica 2<br/>concurrency=10"]
            WK3["Worker Replica N<br/>concurrency=10"]
        end

        subgraph Data
            PG_PRIMARY[("PostgreSQL Primary")]
            PG_REPLICA[("PostgreSQL Replica<br/>read queries")]
            REDIS_MASTER[("Redis Master")]
            REDIS_REPLICA[("Redis Replica")]
        end

        subgraph Monitoring
            PROM2["Prometheus"]
            GRAF2["Grafana"]
        end
    end

    USER -->|HTTPS| NGINX
    NGINX -->|/| FE1
    NGINX -->|/api /ws| API1
    NGINX -->|/api /ws| API2

    API1 --> PG_PRIMARY
    API2 --> PG_PRIMARY
    API1 --> PG_REPLICA
    API2 --> PG_REPLICA
    API1 --> REDIS_MASTER
    API2 --> REDIS_MASTER

    SCHED1 --> PG_PRIMARY
    SCHED1 --> REDIS_MASTER

    WK1 --> PG_PRIMARY
    WK2 --> PG_PRIMARY
    WK3 --> PG_PRIMARY
    WK1 --> REDIS_MASTER
    WK2 --> REDIS_MASTER
    WK3 --> REDIS_MASTER

    REDIS_MASTER --> REDIS_REPLICA

    API1 --> PROM2
    API2 --> PROM2
    SCHED1 --> PROM2
    WK1 --> PROM2
    WK2 --> PROM2
    WK3 --> PROM2
    PROM2 --> GRAF2
```

### Docker Compose Services (Development)

```mermaid
flowchart LR
    subgraph docker-compose.yml
        postgres["postgres:16"]
        redis["redis:7-alpine"]
        api["api"]
        scheduler["scheduler"]
        worker["worker (scale: 3)"]
        frontend["frontend"]
        prometheus["prometheus"]
        grafana["grafana"]
    end

    api --> postgres
    api --> redis
    scheduler --> postgres
    scheduler --> redis
    worker --> postgres
    worker --> redis
    frontend --> api
    prometheus --> api
    prometheus --> worker
    grafana --> prometheus
```

### Environment Profiles

| Profile | API | Scheduler | Workers | Postgres | Redis |
|---------|-----|-----------|---------|----------|-------|
| **dev** | 1 | 1 | 1 | 1 | 1 |
| **staging** | 2 | 1 (+ standby) | 3 | 1 + replica | Sentinel |
| **production** | 3+ | Leader election | Auto-scale | HA cluster | Cluster |

---

## 10. Component Rationale

### Why each component exists

| Component | Why It Exists |
|-----------|---------------|
| **React Dashboard** | Operators need visibility into queues, workers, failures, and throughput without querying SQL. Neobrutalism theme provides high-contrast, scannable enterprise UI. |
| **FastAPI API** | Typed, async, auto-documented REST + WebSocket hub. Control plane for all job/queue/worker operations. |
| **PostgreSQL** | ACID transactions for atomic job claiming. Relational model fits orgs → projects → queues → jobs hierarchy. `SKIP LOCKED` is the industry-standard pattern (used by Graphile Worker, River, etc.). |
| **Redis Streams** | Low-latency wake-up notifications so workers don't hammer DB on idle polls. Stream consumer groups allow partitioned dispatch. |
| **Redis Cache** | JWT blocklist, rate limit counters, dashboard metric snapshots, distributed lock for scheduler leader. |
| **Redis Pub/Sub** | Fan-out realtime events to WebSocket connections across API replicas. |
| **APScheduler** | Battle-tested cron/interval scanning. Runs in dedicated scheduler process to keep API latency isolated. |
| **Scheduler Service** | Separates time-based activation from request handling. Scans `scheduled` → `queued` transitions without blocking API. |
| **Worker Processes** | Horizontally scalable execution plane. Crash of one worker doesn't affect others; unclaimed jobs remain in PG. |
| **Claim Engine** | Encapsulates `FOR UPDATE SKIP LOCKED` logic — the core correctness primitive preventing duplicate execution. |
| **Execution Engine** | Runs job handlers with concurrency control, cancellation, timeout, and result persistence. |
| **Retry Engine** | Centralizes backoff math (fixed/linear/exponential/custom). Keeps worker code simple. |
| **Dead Letter Queue** | Failed jobs need a quarantine area for inspection, alerting, and manual replay — not silent loss. |
| **Heartbeat System** | Detects stale workers. Enables orchestrator to mark crashed workers and optionally release stale claims. |
| **WebSocket Hub** | Dashboard expects live updates (job state changes, worker status) without polling. |
| **Repository Pattern** | Decouples SQL from business logic. Enables unit testing services with mock repos. |
| **Service Layer** | Orchestrates transactions, validation, and cross-entity rules (e.g., can't enqueue to paused queue). |
| **Prometheus Metrics** | Industry standard for alerting on queue depth, failure rate, worker count, claim latency. |
| **Structured JSON Logs** | Machine-parseable logs for ELK/Datadog. Correlation IDs tie API request → job → execution. |
| **JWT + Refresh Tokens** | Stateless auth for API with revocable refresh via Redis. |
| **RBAC** | Multi-tenant org/project isolation. Roles: owner, admin, member, viewer. |
| **API Keys** | Machine-to-machine job submission without user sessions. |
| **Audit Logs** | Compliance trail for who changed queue config, replayed DLQ jobs, etc. |
| **Alembic Migrations** | Version-controlled schema evolution for production deployments. |
| **Nginx** | TLS, routing, rate limiting at edge. Serves static frontend separately from API. |

### Bonus Features — Architecture Hooks

| Feature | Approach |
|---------|----------|
| **Workflow DAG** | `jobs.metadata.parent_job_id` + dependency table; child jobs start when parent completes |
| **Queue Sharding** | `queues.config.shard_key` — workers subscribe to shard subsets |
| **Distributed Locking** | Redis Redlock for scheduler leader election |
| **Leader Election** | Scheduler standby acquires lock; only leader runs cron scans |
| **AI Failure Summary** | Post-execution hook sends error stack to LLM endpoint; stores summary in `job_executions.result` |
| **Execution Replay** | DLQ → clone job with new idempotency key → re-enqueue |
| **Priority Inheritance** | Child jobs inherit parent priority unless overridden |
| **Rate Limiting** | Redis sliding window per org/project on API; per-queue token bucket for job creation |

---

## 11. Frontend Design — Neobrutalism Theme

The dashboard uses **Neobrutalism** — bold borders, hard shadows, high contrast, flat colors — applied on top of ShadCN UI primitives.

### Design Tokens

```css
/* Core neobrutalism tokens */
--neo-border: 3px solid #000;
--neo-shadow: 4px 4px 0px #000;
--neo-shadow-hover: 6px 6px 0px #000;
--neo-radius: 0px;           /* Sharp corners */
--neo-bg: #FFFDF5;           /* Warm off-white */
--neo-primary: #FF6B35;      /* Orange accent */
--neo-secondary: #004E89;    /* Deep blue */
--neo-success: #06D6A0;
--neo-warning: #FFD166;
--neo-danger: #EF476F;
--neo-muted: #F0EDE5;
--neo-font: 'Space Grotesk', sans-serif;
```

### Dashboard Layout

```mermaid
flowchart TB
    subgraph Layout
        SIDEBAR["Sidebar Nav<br/>bold icons + labels"]
        HEADER["Header<br/>org/project selector · user menu"]
        MAIN["Main Content Area"]
    end

    subgraph Dashboard Page
        CARDS["Overview Cards<br/>Jobs · Queues · Workers · Failures"]
        CHARTS["Chart.js Row<br/>Throughput · Latency · Failures · Retries"]
        TABLES["Jobs Table + Worker Grid<br/>search · filter · pagination"]
        DLQ_PANEL["Dead Letter Panel"]
    end

    SIDEBAR --> MAIN
    HEADER --> MAIN
    MAIN --> CARDS
    MAIN --> CHARTS
    MAIN --> TABLES
    MAIN --> DLQ_PANEL
```

### Key UI Components

| Component | Purpose |
|-----------|---------|
| `NeoCard` | Wrapper with 3px border + offset shadow |
| `NeoButton` | ShadCN Button with brutal shadow + press animation |
| `OverviewCards` | 4-up grid: total jobs, active workers, queue depth, failure rate |
| `ThroughputChart` | Jobs/min line chart (Chart.js) |
| `JobsTable` | Sortable, filterable, paginated with status badges |
| `WorkerGrid` | Live heartbeat indicators (green/yellow/red) |
| `RealtimeProvider` | WebSocket context feeding React Query cache invalidation |

---

## 12. Technology Decisions Summary

| Decision | Choice | Alternatives Considered | Rationale |
|----------|--------|------------------------|-----------|
| Job store | PostgreSQL | Redis-only, DynamoDB | ACID claiming, complex queries, audit |
| Wake-up signal | Redis Streams | Polling only, RabbitMQ | Already in stack; persistent consumer groups |
| Claim pattern | SKIP LOCKED | Advisory locks, Redis BRPOPLPUSH | PostgreSQL-native, no extra broker dependency for correctness |
| Scheduler | APScheduler | Celery Beat, custom cron | Lightweight, embeddable, sufficient for scan workloads |
| API framework | FastAPI | Django, Flask | Async, Pydantic, OpenAPI auto-gen |
| Frontend | React + Vite | Next.js | SPA dashboard; no SSR needed |
| Auth | JWT + Refresh | Session cookies only | Stateless API replicas; refresh revocable in Redis |
| Metrics | Prometheus | Datadog agent | Open-source, pull model, Grafana ecosystem |
| Migrations | Alembic | Raw SQL | SQLAlchemy 2.0 integration |

---

## Next Steps

Once this architecture is **approved**, implementation proceeds in phases:

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **1** | Database schema + migrations + core models | Alembic migrations, SQLAlchemy models |
| **2** | Auth + Organizations + Projects + Queues API | JWT auth, CRUD endpoints |
| **3** | Job engine + claim + state machine + retry | Worker process, claim engine, DLQ |
| **4** | Scheduler (delay, cron, recurring) | APScheduler service |
| **5** | WebSocket + Redis Pub/Sub | Live dashboard feed |
| **6** | Frontend dashboard (neobrutalism) | Full React UI |
| **7** | Observability + Docker Compose | Prometheus, health checks, `docker compose up` |
| **8** | Tests + documentation | Pytest suite, API.md, Deployment.md |

---

**Please review this architecture and confirm approval (or note changes) before implementation begins.**
