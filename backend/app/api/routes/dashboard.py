from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_project_access
from app.database.session import get_db
from app.models.organization import Project
from app.schemas.dashboard import OverviewStats
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/projects/{project_id}/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewStats)
async def overview(project: Project = Depends(require_project_access), db: AsyncSession = Depends(get_db)):
    return await DashboardService(db).overview(project.id)
