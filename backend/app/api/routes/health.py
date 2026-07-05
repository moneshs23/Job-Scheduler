from fastapi import APIRouter
from sqlalchemy import text

from app.database.session import AsyncSessionLocal
from app.queues.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    checks = {"database": "ok", "redis": "ok"}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    try:
        await get_redis().ping()
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if healthy else "unhealthy", "checks": checks}
