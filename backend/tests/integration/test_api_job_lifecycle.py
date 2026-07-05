import uuid

import pytest

from app.config.constants import JOB_STATUS_DEAD_LETTER, JOB_STATUS_QUEUED
from app.execution.engine import execute_job
from app.repositories.job import JobRepository


async def _register_and_get_token(client) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{uuid.uuid4().hex}@test.com",
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _create_project_and_queue(client, token: str) -> tuple[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    orgs = await client.get("/api/v1/organizations", headers=headers)
    org_id = orgs.json()[0]["id"]

    project_resp = await client.post(
        f"/api/v1/organizations/{org_id}/projects", headers=headers, json={"name": "Proj"}
    )
    project_id = project_resp.json()["id"]

    queue_resp = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        headers=headers,
        json={"name": "default", "priority": 0, "concurrency_limit": 5},
    )
    queue_id = queue_resp.json()["id"]
    return project_id, queue_id


async def _register_worker(client, token: str, project_id: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/workers",
        headers=headers,
        json={"hostname": "test-worker", "worker_type": "generic", "concurrency": 10},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_full_job_lifecycle_success(client, db_session):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id, queue_id = await _create_project_and_queue(client, token)

    create_resp = await client.post(
        f"/api/v1/projects/{project_id}/jobs",
        headers=headers,
        json={"name": "echo-test", "queue_id": queue_id, "payload": {"task": "echo", "args": {"x": 1}}},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["status"] == JOB_STATUS_QUEUED

    worker_id = uuid.UUID(await _register_worker(client, token, project_id))
    claimed = await JobRepository(db_session).claim_jobs(uuid.UUID(queue_id), worker_id, limit=1)
    assert len(claimed) == 1
    await db_session.commit()

    await execute_job(claimed[0].id, worker_id)

    get_resp = await client.get(f"/api/v1/projects/{project_id}/jobs/{job['id']}", headers=headers)
    assert get_resp.json()["status"] == "completed"

    executions_resp = await client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}/executions", headers=headers
    )
    executions = executions_resp.json()
    assert len(executions) == 1
    assert executions[0]["status"] == "completed"
    assert executions[0]["result"] == {"echoed": {"x": 1}}


@pytest.mark.asyncio
async def test_job_exhausting_retries_lands_in_dead_letter_queue(client, db_session):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id, queue_id = await _create_project_and_queue(client, token)

    # A zero-delay retry policy so the test doesn't need to sleep between claim attempts.
    policy_resp = await client.post(
        f"/api/v1/projects/{project_id}/retry-policies",
        headers=headers,
        json={"name": "instant", "strategy": "fixed", "max_retries": 5, "base_delay_ms": 0},
    )
    policy_id = policy_resp.json()["id"]
    await client.patch(
        f"/api/v1/projects/{project_id}/queues/{queue_id}", headers=headers, json={"retry_policy_id": policy_id}
    )

    create_resp = await client.post(
        f"/api/v1/projects/{project_id}/jobs",
        headers=headers,
        json={
            "name": "always-fails",
            "queue_id": queue_id,
            "max_attempts": 2,
            "payload": {"task": "fail", "args": {"message": "nope"}},
        },
    )
    job_id = create_resp.json()["id"]

    worker_id = uuid.UUID(await _register_worker(client, token, project_id))
    for _ in range(2):
        claimed = await JobRepository(db_session).claim_jobs(uuid.UUID(queue_id), worker_id, limit=1)
        assert len(claimed) == 1
        await db_session.commit()
        await execute_job(claimed[0].id, worker_id)

    get_resp = await client.get(f"/api/v1/projects/{project_id}/jobs/{job_id}", headers=headers)
    body = get_resp.json()
    assert body["status"] == JOB_STATUS_DEAD_LETTER
    assert body["attempt_count"] == 2

    dlq_resp = await client.get(
        f"/api/v1/projects/{project_id}/dead-letter-queue", headers=headers, params={"queue_id": queue_id}
    )
    assert dlq_resp.json()["total"] == 1

    replay_resp = await client.post(f"/api/v1/projects/{project_id}/jobs/{job_id}/replay", headers=headers)
    assert replay_resp.json()["status"] == JOB_STATUS_QUEUED
