import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_current_principal
from app.database.session import get_db
from app.repositories.api_key import AuditLogRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.audit import AuditLogResponse
from app.schemas.common import Page
from app.schemas.organization import OrganizationResponse, ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.audit_service import client_ip, record_audit
from app.services.project_service import ProjectService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> list:
    return await OrganizationRepository(db).list_for_user(principal.user.id)


@router.get("/{organization_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    organization_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await ProjectService(db).list_for_organization(organization_id)


@router.post("/{organization_id}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    organization_id: uuid.UUID,
    payload: ProjectCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    project = await ProjectService(db).create(
        organization_id, payload.name, payload.description, payload.settings
    )
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=organization_id,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        after_state={"name": project.name, "slug": project.slug},
        ip_address=client_ip(request),
    )
    return project


@router.patch("/{organization_id}/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.projects.get(project_id)
    if project is None or project.organization_id != organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    before = {"name": project.name, "description": project.description}
    updated = await service.update(project, payload.name, payload.description, payload.settings)
    await record_audit(
        db,
        user_id=principal.user.id,
        organization_id=organization_id,
        action="project.updated",
        resource_type="project",
        resource_id=project.id,
        before_state=before,
        after_state={"name": updated.name, "description": updated.description},
        ip_address=client_ip(request),
    )
    return updated


@router.get("/{organization_id}/audit-logs", response_model=Page[AuditLogResponse])
async def list_audit_logs(
    organization_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    logs, total = await AuditLogRepository(db).list_for_organization(
        organization_id, offset=(page - 1) * page_size, limit=page_size
    )
    return Page.build(logs, total, page, page_size)
