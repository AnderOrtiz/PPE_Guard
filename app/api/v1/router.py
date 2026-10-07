from fastapi import APIRouter
from app.api.v1.endpoints import stream, health, practices, auth, materias, usuarios, practicas, asistencias, alumno, coordinacion

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(practices.router, tags=["practices"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(materias.router, tags=["materias"])
api_router.include_router(usuarios.router, tags=["usuarios"])
api_router.include_router(practicas.router, tags=["practicas"])
api_router.include_router(asistencias.router, tags=["asistencias"])
api_router.include_router(alumno.router, tags=["alumno"])
api_router.include_router(coordinacion.router, tags=["coordinacion"])
api_router.include_router(stream.router, tags=["stream"])