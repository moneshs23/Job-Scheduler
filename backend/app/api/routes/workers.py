import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_current_principal, require_project_access
from app.database.session import get_db
from app.models.organization import Project
from app.repositories.worker import WorkerHeartbeatRepository
from app.schemas.worker import (
    WorkerHeartbeatRequest,
    WorkerHeartbeatResponse,
    WorkerRegisterRequest,
    WorkerResponse,
)
from app.services.audit_service import client_ip, record_audit
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/projects/{project_id}/workers", tags=["workers"])


@router.post("", response_model=WorkerResponse, status_code=201)
async def register_worker(
    payload: WorkerRegisterRequest,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    return await WorkerService(db).register(
        project.id, payload.hostname, payload.worker_type, payload.concurrency, payload.capabilities
    )


@router.get("", response_model=list[WorkerResponse])
async def list_workers(
    project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    return await WorkerService(db).list_for_project(project.id)


@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
async def heartbeat(
    worker_id: uuid.UUID,
    payload: WorkerHeartbeatRequest,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    return await WorkerService(db).heartbeat(
        worker_id, payload.status, payload.active_jobs, payload.cpu_percent, payload.memory_mb, payload.metadata
    )


@router.get("/{worker_id}/heartbeats", response_model=list[WorkerHeartbeatResponse])
async def worker_heartbeats(
    worker_id: uuid.UUID, project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    return await WorkerHeartbeatRepository(db).recent_for_worker(worker_id)


@router.post("/{worker_id}/shutdown", response_model=WorkerResponse)
async def shutdown_worker(
    worker_id: uuid.UUID,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    worker = await WorkerService(db).request_shutdown(worker_id)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="worker.shutdown_requested",
        resource_type="worker",
        resource_id=worker.id,
        ip_address=client_ip(request),
    )
    return worker
