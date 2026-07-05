import asyncio
import os
import uuid

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://scheduler:scheduler@localhost:5432/scheduler_test"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ["ENVIRONMENT"] = "test"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.database.session import get_db
from app.models import Base
from app.models.organization import Organization, OrganizationMember, Project, User
from app.models.queue import Queue
from app.models.worker import Worker

settings = get_settings()
# NullPool: pytest-asyncio gives each test function its own event loop, and a pooled
# asyncpg connection bound to one loop breaks when reused from another. A fresh
# connection per checkout avoids the cross-loop reuse entirely.
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _reset_redis_client():
    """Each pytest-asyncio test function runs its own event loop, but get_redis() is
    lru_cached — without this reset, a client created in one test's loop gets reused
    (and breaks) in the next."""
    from app.queues.redis_client import get_redis

    get_redis.cache_clear()
    yield
    get_redis.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine():
    """execute_job() opens sessions from app.database.session's module-level engine —
    dispose its pool after every test so the next test's event loop doesn't inherit
    connections bound to a loop that's already closed."""
    yield
    from app.database.session import engine as app_engine

    await app_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    from app.main import app

    async def _override_get_db():
        # Mirrors get_db()'s real per-request lifecycle: a fresh view of committed
        # state each request, instead of serving stale identity-mapped objects left
        # over from earlier requests or direct DB manipulation in the test body.
        db_session.expire_all()
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_project(db_session):
    """A user + organization + project + queue, ready for job/worker tests."""
    user = User(email=f"{uuid.uuid4().hex}@test.com", password_hash="x", full_name="Test User", role="admin")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))

    project = Project(organization_id=org.id, name="Test Project", slug=f"test-project-{uuid.uuid4().hex[:8]}")
    db_session.add(project)
    await db_session.flush()

    queue = Queue(project_id=project.id, name="default", priority=0, concurrency_limit=10)
    db_session.add(queue)
    await db_session.flush()

    worker = Worker(project_id=project.id, hostname="test-worker", status="idle", concurrency=10)
    db_session.add(worker)
    await db_session.flush()
    await db_session.commit()

    return {"user": user, "organization": org, "project": project, "queue": queue, "worker": worker}


@pytest_asyncio.fixture
async def make_worker(db_session):
    """Factory for extra worker rows, e.g. to simulate multiple workers racing for jobs."""

    async def _make(project_id: uuid.UUID) -> Worker:
        worker = Worker(project_id=project_id, hostname=f"test-worker-{uuid.uuid4().hex[:6]}", status="idle", concurrency=10)
        db_session.add(worker)
        await db_session.commit()
        await db_session.refresh(worker)
        return worker

    return _make
