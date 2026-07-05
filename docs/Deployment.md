# Deployment

## Local development (no Docker)

Requirements: Python 3.12, Node 20+, PostgreSQL 16, Redis 7.

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # edit DATABASE_URL / REDIS_URL / JWT_SECRET_KEY if needed
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# In separate terminals:
python -m app.scheduler.main
WORKER_PROJECT_ID=<uuid-of-a-project> python -m app.workers.main

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to :8000
```

Run tests: `cd backend && python -m pytest tests/ -v` (needs a `scheduler_test` Postgres database —
see `tests/conftest.py`).

## Docker Compose

```bash
cp .env.example .env   # set a real JWT_SECRET_KEY
docker compose up --build
```

This starts `postgres`, `redis`, `api` (runs migrations on boot, then serves on :8000), `scheduler`,
`frontend` (nginx on :8080, proxying `/api` to the `api` service), and `prometheus` (:9090).

**The `worker` service is not started by default** — it's declared with `profiles: ["worker"]`
because a worker is scoped to one project, and no project exists until you've registered a user
through the UI and created one. Bootstrap order:

```bash
docker compose up --build            # everything except workers
open http://localhost:8080           # register, create a project, copy its id
WORKER_PROJECT_ID=<that-uuid> docker compose --profile worker up --scale worker=3 worker
```

Scaling workers horizontally is just `--scale worker=N` — they coordinate purely through Postgres
row locks (`SKIP LOCKED`), so there's no coordinator to configure.

## Environment variables

All backend config is in `backend/app/config/settings.py` (pydantic-settings, reads `.env`). The ones
you're likely to change in production:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://scheduler:scheduler@localhost:5432/scheduler` | Must use the `asyncpg` driver |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `JWT_SECRET_KEY` | dev placeholder | **Generate with `openssl rand -hex 32`; never reuse the default.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | 30 / 7 | |
| `CORS_ORIGINS` | localhost dev ports | Comma-separated |
| `WORKER_CONCURRENCY` | 10 | Max concurrent jobs per worker process |
| `WORKER_POLL_INTERVAL_MS` | 500 | Fallback poll interval when no Redis Stream notification arrives |
| `WORKER_HEARTBEAT_INTERVAL_SEC` / `WORKER_DRAIN_TIMEOUT_SEC` | 5 / 30 | Graceful shutdown waits up to the drain timeout for in-flight jobs |
| `SCHEDULER_SCAN_INTERVAL_SEC` | 1 | How often the delay/cron scanners run |
| `SCHEDULER_LEADER_LOCK_TTL_SEC` | 15 | Redis-lock TTL for scheduler leader election (safe to run multiple scheduler replicas) |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SEC` | 100 / 60 | Fixed-window limit per client IP |

## Migrations

`alembic upgrade head` (run automatically by the API container's entrypoint; run manually for local
dev). New migration: `alembic revision --autogenerate -m "description"` after changing models in
`app/models/`.

## Production considerations not yet wired up

Being upfront about what's demonstrated vs. what a real production rollout still needs:

- **TLS termination** — put the API and frontend behind a real load balancer / ingress (nginx, Traefik,
  or a cloud LB) with certificates; nothing here terminates TLS itself.
- **Secrets management** — `JWT_SECRET_KEY` and the Postgres password are plain env vars here; use
  your platform's secret store (Vault, AWS Secrets Manager, k8s Secrets) instead.
- **Postgres HA** — this compose file runs a single Postgres instance. Production needs replication
  and backups (e.g. managed RDS/Cloud SQL, or Patroni).
- **Redis persistence** — Redis here is a plain cache/notification bus and can be lost without data
  loss, but a Sentinel/Cluster setup avoids the brief claim-latency blip a Redis restart causes.
- **Log/metric shipping** — structured JSON logs go to stdout (ready for any log collector); Prometheus
  is wired up for the API only — worker/scheduler processes don't yet expose a `/metrics` port.
