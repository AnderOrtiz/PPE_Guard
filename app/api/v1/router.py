from fastapi import APIRouter
from app.api.v1.endpoints import health, practices, stream

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(practices.router, tags=["practices"])
api_router.include_router(stream.router, tags=["stream"])