import os

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.core.database import get_database
from app.api.v1.dependencies import get_current_user_media

router = APIRouter()


async def _puede_ver(database, user: dict, asistencia: dict) -> bool:
    if user["rol"] == "admin":
        return True
    if user["rol"] == "alumno":
        return asistencia["alumno_id"] == user["user_id"]

    practica = await database["practicas"].find_one({"_id": ObjectId(asistencia["practica_id"])})
    if practica is None:
        return False
    materia = await database["materias"].find_one({"_id": ObjectId(practica["materia_id"])})
    if materia is None:
        return False

    campo = "docente_id" if user["rol"] == "docente" else "coordinador_id"
    return materia[campo] == user["user_id"]


@router.get("/static/evidence/{fecha}/{archivo}")
async def ver_evidencia(fecha: str, archivo: str, user: dict = Depends(get_current_user_media)):
    # Solo se sirven rutas que estén registradas en una asistencia: de ahí sale
    # tanto el permiso como la garantía de que no se lee nada fuera de la carpeta.
    evidencia_url = f"/static/evidence/{fecha}/{archivo}"

    database = get_database()
    asistencia = await database["asistencias"].find_one({"evidencia_url": evidencia_url})
    ruta = evidencia_url.lstrip("/")
    if asistencia is None or not os.path.isfile(ruta):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La evidencia indicada no existe")

    if not await _puede_ver(database, user, asistencia):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver una evidencia fuera de tu alcance")

    return FileResponse(ruta, media_type="image/jpeg")
