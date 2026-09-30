from fastapi import APIRouter
from app.api.v1.endpoints import health, practices, auth, materias, usuarios, practicas

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(practices.router, tags=["practices"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(materias.router, tags=["materias"])
api_router.include_router(usuarios.router, tags=["usuarios"])
api_router.include_router(practicas.router, tags=["practicas"])