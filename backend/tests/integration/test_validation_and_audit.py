import uuid

import pytest


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


@pytest.mark.asyncio
async def test_custom_validator_error_returns_422_not_500(client):
    """Regression test: a Pydantic model_validator raising ValueError used to crash the
    custom exception handler with a 500 (TypeError: ValueError is not JSON serializable),
    because exc.errors()['ctx'] holds the raw exception object."""
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    orgs = await client.get("/api/v1/organizations", headers=headers)
    org_id = orgs.json()[0]["id"]
    project = await client.post(f"/api/v1/organizations/{org_id}/projects", headers=headers, json={"name": "P"})
    project_id = project.json()["id"]
    queue = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        headers=headers,
        json={"name": "default", "priority": 0, "concurrency_limit": 5},
    )
    queue_id = queue.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/jobs",
        headers=headers,
        json={
            "name": "conflicting-schedule",
            "queue_id": queue_id,
            "delay_seconds": 5,
            "cron_expression": "* * * * *",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert "Only one of" in body["details"][0]["msg"]


@pytest.mark.asyncio
async def test_mutations_are_recorded_in_audit_log(client):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    orgs = await client.get("/api/v1/organizations", headers=headers)
    org_id = orgs.json()[0]["id"]
    project = await client.post(f"/api/v1/organizations/{org_id}/projects", headers=headers, json={"name": "P"})
    project_id = project.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/queues",
        headers=headers,
        json={"name": "default", "priority": 0, "concurrency_limit": 5},
    )

    audit = await client.get(f"/api/v1/organizations/{org_id}/audit-logs", headers=headers)
    assert audit.status_code == 200
    body = audit.json()
    actions = {entry["action"] for entry in body["items"]}
    assert "project.created" in actions
    assert "queue.created" in actions
