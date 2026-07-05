# Distributed Job Scheduler

A production-grade distributed job scheduler — comparable to Temporal, BullMQ, Sidekiq, and Celery —
built for reliability, horizontal scalability, and enterprise observability.

## Status

**Implemented and verified end-to-end.** Backend (auth, orgs/projects, queues, jobs, workers,
scheduler, DLQ, WebSocket realtime) and frontend (React dashboard, neobrutalism theme) both run
locally against real Postgres/Redis, with 16 passing pytest tests (including a concurrency test
proving atomic claiming never double-executes a job) and a Playwright-verified UI.

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture.md](./docs/Architecture.md) | High-level design, ER diagrams, sequence diagrams, deployment |
| [Design-Decisions.md](./docs/Design-Decisions.md) | Why Postgres over Redis-as-queue, SKIP LOCKED vs. distributed locks, retry semantics, leader election |
| [Database.md](./docs/Database.md) | Schema, indexes, cascade rules, the claim query explained |
| [API.md](./docs/API.md) | Endpoint map, auth schemes, pagination — full schema lives at `/docs` |
| [Deployment.md](./docs/Deployment.md) | Local dev setup, Docker Compose, environment variables |

## Tech Stack

- **Frontend:** React, TypeScript, Vite, TailwindCSS, React Query, React Router, Chart.js
- **Backend:** FastAPI, Python 3.12, SQLAlchemy 2.0 (async), APScheduler
- **Data:** PostgreSQL, Redis (Streams, Cache, Pub/Sub)
- **Ops:** Docker, Docker Compose, Prometheus, structured JSON logging

## Architecture Overview

```
React Dashboard  →  FastAPI API  →  PostgreSQL (source of truth)
                         ↓              ↑
                    APScheduler    Worker Pool (SKIP LOCKED claim)
                         ↓              ↑
                    Redis Streams (dispatch notifications)
```

## Quickstart

```bash
cp .env.example .env   # set JWT_SECRET_KEY
docker compose up --build
```

Open http://localhost:8080, register, create a project, then start a worker for it — see
[Deployment.md](./docs/Deployment.md) for the full bootstrap sequence and local (non-Docker) setup.

## License

MIT
