from bson import ObjectId
from fastapi import APIRouter, Depends

from app.core.database import get_database
from app.api.v1.dependencies import require_role
from app.models.asistencia import AsistenciaAlumnoOut
from app.models.materia import MateriaAlumnoOut

router = APIRouter()


async def _nombres_docentes(database, materias: list[dict]) -> dict[str, str]:
    docente_ids = {m["docente_id"] for m in materias if ObjectId.is_valid(m["docente_id"])}
    if not docente_ids:
        return {}
    cursor = database["usuarios"].find({"_id": {"$in": [ObjectId(d) for d in docente_ids]}}, {"nombre": 1})
    return {str(doc["_id"]): doc["nombre"] async for doc in cursor}


@router.get("/alumno/materias", response_model=list[MateriaAlumnoOut])
async def mis_materias(user: dict = Depends(require_role("alumno"))):
    database = get_database()

    materias = [m async for m in database["materias"].find({"alumnos_ids": user["user_id"]}).sort("nombre", 1)]
    docentes = await _nombres_docentes(database, materias)

    return [MateriaAlumnoOut(**m, docente_nombre=docentes.get(m["docente_id"])) for m in materias]


@router.get("/alumno/asistencias", response_model=list[AsistenciaAlumnoOut])
async def mis_asistencias(user: dict = Depends(require_role("alumno"))):
    database = get_database()

    cursor = database["asistencias"].find({"alumno_id": user["user_id"]}).sort("hora_identificacion", -1)
    asistencias = [a async for a in cursor]

    practica_ids = {a["practica_id"] for a in asistencias if ObjectId.is_valid(a["practica_id"])}
    cursor = database["practicas"].find({"_id": {"$in": [ObjectId(p) for p in practica_ids]}}, {"materia_id": 1})
    materia_por_practica = {str(p["_id"]): p["materia_id"] async for p in cursor}

    materia_ids = {m for m in materia_por_practica.values() if ObjectId.is_valid(m)}
    cursor = database["materias"].find({"_id": {"$in": [ObjectId(m) for m in materia_ids]}}, {"nombre": 1, "docente_id": 1})
    materias = {str(m["_id"]): m async for m in cursor}
    docentes = await _nombres_docentes(database, list(materias.values()))

    resultado = []
    for asistencia in asistencias:
        materia_id = materia_por_practica.get(asistencia["practica_id"])
        materia = materias.get(materia_id)
        resultado.append(AsistenciaAlumnoOut(
            **asistencia,
            materia_id=materia_id,
            materia_nombre=materia["nombre"] if materia else None,
            docente_nombre=docentes.get(materia["docente_id"]) if materia else None,
        ))
    return resultado
