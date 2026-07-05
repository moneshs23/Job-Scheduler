from fastapi import APIRouter

from app.api.routes import auth, dashboard, jobs, organizations, queues, websocket, workers

api_router = APIRouter()
api_router.include_router(websocket.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(queues.router)
api_router.include_router(queues.retry_policy_router)
api_router.include_router(jobs.router)
api_router.include_router(jobs.dlq_router)
api_router.include_router(workers.router)
api_router.include_router(dashboard.router)
