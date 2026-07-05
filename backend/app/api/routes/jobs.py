import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_current_principal, require_project_access
from app.database.session import get_db
from app.models.organization import Project
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.execution import JobExecutionRepository, JobLogRepository
from app.schemas.common import Page
from app.schemas.job import (
    BatchJobCreate,
    DeadLetterResponse,
    JobCreate,
    JobExecutionResponse,
    JobLogResponse,
    JobResponse,
)
from app.services.audit_service import client_ip, record_audit
from app.services.job_service import JobService

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    return await JobService(db).create_job(project.id, payload)


@router.post("/batch", response_model=list[JobResponse], status_code=201)
async def create_batch(
    payload: BatchJobCreate,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
):
    return await JobService(db).create_batch(project.id, payload)


@router.get("", response_model=Page[JobResponse])
async def list_jobs(
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    queue_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    jobs, total = await JobService(db).list_jobs(
        project.id,
        queue_id=queue_id,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return Page.build(jobs, total, page, page_size)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID, project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
):
    return await JobService(db).get_job(project.id, job_id)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    job = await JobService(db).cancel_job(project.id, job_id)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="job.cancelled",
        resource_type="job",
        resource_id=job.id,
        ip_address=client_ip(request),
    )
    return job


@router.post("/{job_id}/replay", response_model=JobResponse)
async def replay_job(
    job_id: uuid.UUID,
    request: Request,
    project: Project = Depends(require_project_access),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    job = await JobService(db).replay_from_dead_letter(project.id, job_id)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=project.organization_id,
        action="job.replayed",
        resource_type="job",
        resource_id=job.id,
        ip_address=client_ip(request),
    )
    return job


@router.get("/{job_id}/executions", response_model=list[JobExecutionResponse])
async def job_executions(
    job_id: uuid.UUID, project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    await JobService(db).get_job(project.id, job_id)  # 404s if not in this project
    return await JobExecutionRepository(db).list_for_job(job_id)


@router.get("/{job_id}/logs", response_model=list[JobLogResponse])
async def job_logs(
    job_id: uuid.UUID, project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)
) -> list:
    await JobService(db).get_job(project.id, job_id)
    return await JobLogRepository(db).list_for_job(job_id)


dlq_router = APIRouter(prefix="/projects/{project_id}/dead-letter-queue", tags=["dead-letter-queue"])


@dlq_router.get("", response_model=Page[DeadLetterResponse])
async def list_dead_letters(
    queue_id: uuid.UUID,
    project: Project = Depends(require_project_access),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    entries, total = await DeadLetterRepository(db).list_for_queue(
        queue_id, offset=(page - 1) * page_size, limit=page_size
    )
    return Page.build(entries, total, page, page_size)
