import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_current_principal, require_project_access
from app.database.session import get_db
from app.models.organization import Project
from app.schemas.queue import (
    QueueCreate,
    QueueMetrics,
    QueueResponse,
    QueueUpdate,
    RetryPolicyCreate,
    RetryPolicyResponse,
)
from app.services.audit_service import client_ip, record_audit
from app.services.queue_service import QueueService

router = APIRouter(prefix="/projects/{project_id}/queues", tags=["queues"])


@router.get("", response_model=list[QueueResponse])
async def list_queues(
    project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    return await QueueService(db).queues.list_for_project(project.id)


@router.post("", response_model=QueueResponse, status_code=201)
async def create_queue(
    payload: QueueCreate,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    queue = await QueueService(db).create(
        project.id, payload.name, payload.priority, payload.concurrency_limit, payload.retry_policy_id, payload.config
    )
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="queue.created",
        resource_type="queue",
        resource_id=queue.id,
        after_state={"name": queue.name, "priority": queue.priority, "concurrency_limit": queue.concurrency_limit},
        ip_address=client_ip(request),
    )
    return queue


async def _get_queue_or_404(project_id: uuid.UUID, queue_id: uuid.UUID, service: QueueService):
    queue = await service.queues.get(queue_id)
    if queue is None or queue.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found")
    return queue


@router.patch("/{queue_id}", response_model=QueueResponse)
async def update_queue(
    queue_id: uuid.UUID,
    payload: QueueUpdate,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    service = QueueService(db)
    queue = await _get_queue_or_404(project.id, queue_id, service)
    before = {
        "priority": queue.priority,
        "concurrency_limit": queue.concurrency_limit,
        "retry_policy_id": str(queue.retry_policy_id) if queue.retry_policy_id else None,
    }
    updated = await service.update(queue, **payload.model_dump(exclude_unset=True))
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="queue.updated",
        resource_type="queue",
        resource_id=queue.id,
        before_state=before,
        after_state={
            "priority": updated.priority,
            "concurrency_limit": updated.concurrency_limit,
            "retry_policy_id": str(updated.retry_policy_id) if updated.retry_policy_id else None,
        },
        ip_address=client_ip(request),
    )
    return updated


@router.post("/{queue_id}/pause", response_model=QueueResponse)
async def pause_queue(
    queue_id: uuid.UUID,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    service = QueueService(db)
    queue = await _get_queue_or_404(project.id, queue_id, service)
    updated = await service.set_paused(queue, True)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="queue.paused",
        resource_type="queue",
        resource_id=queue.id,
        ip_address=client_ip(request),
    )
    return updated


@router.post("/{queue_id}/resume", response_model=QueueResponse)
async def resume_queue(
    queue_id: uuid.UUID,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    service = QueueService(db)
    queue = await _get_queue_or_404(project.id, queue_id, service)
    updated = await service.set_paused(queue, False)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="queue.resumed",
        resource_type="queue",
        resource_id=queue.id,
        ip_address=client_ip(request),
    )
    return updated


@router.get("/{queue_id}/metrics", response_model=QueueMetrics)
async def queue_metrics(
    queue_id: uuid.UUID,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    service = QueueService(db)
    queue = await _get_queue_or_404(project.id, queue_id, service)
    return await service.metrics(queue)


retry_policy_router = APIRouter(prefix="/projects/{project_id}/retry-policies", tags=["retry-policies"])


@retry_policy_router.get("", response_model=list[RetryPolicyResponse])
async def list_retry_policies(
    project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    return await QueueService(db).retry_policies.list_for_project(project.id)


@retry_policy_router.post("", response_model=RetryPolicyResponse, status_code=201)
async def create_retry_policy(
    payload: RetryPolicyCreate,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    return await QueueService(db).create_retry_policy(project.id, **payload.model_dump())
