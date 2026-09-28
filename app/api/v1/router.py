from fastapi import APIRouter
from app.api.v1.endpoints import health, practices, auth, aulas, usuarios

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(practices.router, tags=["practices"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(aulas.router, tags=["aulas"])
api_router.include_router(usuarios.router, tags=["usuarios"])