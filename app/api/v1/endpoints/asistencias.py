from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.api.v1.dependencies import require_role, get_current_user
from app.models.asistencia import AsistenciaInDB
from app.models.reporte import ReportePractica, FilaAsistencia

router = APIRouter()


async def _practica_ids_permitidos(database, user: dict, materia_id: str | None, docente_id: str | None) -> list[str]:
    """Resuelve a qué practica_id tiene acceso este usuario, según su rol,
    combinado con los filtros opcionales que haya mandado (que solo acotan,
    nunca amplían, lo que su rol ya permite ver)."""
    materia_filtro = {}

    if user["rol"] == "docente":
        materia_filtro["docente_id"] = user["user_id"]
    elif user["rol"] == "coordinador":
        materia_filtro["coordinador_id"] = user["user_id"]
        if docente_id is not None:
            materia_filtro["docente_id"] = docente_id
    elif user["rol"] == "admin" and docente_id is not None:
        materia_filtro["docente_id"] = docente_id

    if materia_id is not None and ObjectId.is_valid(materia_id):
        materia_filtro["_id"] = ObjectId(materia_id)

    materias_cursor = database["materias"].find(materia_filtro, {"_id": 1})
    materia_ids = [str(m["_id"]) async for m in materias_cursor]
    if not materia_ids:
        return []

    practicas_cursor = database["practicas"].find({"materia_id": {"$in": materia_ids}}, {"_id": 1})
    return [str(p["_id"]) async for p in practicas_cursor]


@router.get("/asistencias", response_model=list[AsistenciaInDB])
async def listar_asistencias(
    materia_id: str | None = None,
    docente_id: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    user: dict = Depends(get_current_user),
):
    database = get_database()

    if user["rol"] == "alumno":
        filtro = {"alumno_id": user["user_id"]}
    else:
        practica_ids = await _practica_ids_permitidos(database, user, materia_id, docente_id)
        if not practica_ids:
            return []
        filtro = {"practica_id": {"$in": practica_ids}}

    if fecha_desde is not None or fecha_hasta is not None:
        rango = {}
        if fecha_desde is not None:
            rango["$gte"] = fecha_desde
        if fecha_hasta is not None:
            rango["$lte"] = fecha_hasta
        filtro["hora_identificacion"] = rango

    cursor = database["asistencias"].find(filtro).sort("hora_identificacion", -1)
    return [AsistenciaInDB(**doc) async for doc in cursor]


@router.get(
    "/practicas/{practica_id}/reporte",
    response_model=ReportePractica,
    dependencies=[Depends(require_role("docente", "coordinador"))],
)
async def reporte_practica(practica_id: str, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(practica_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="practica_id inválido")

    database = get_database()
    practica = await database["practicas"].find_one({"_id": ObjectId(practica_id)})
    if practica is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La práctica indicada no existe")

    materia = await database["materias"].find_one({"_id": ObjectId(practica["materia_id"])})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia de esta práctica ya no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver el reporte de una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver el reporte de una materia fuera de tu cargo")

    docente = await database["usuarios"].find_one({"_id": ObjectId(materia["docente_id"])})

    asistencias_cursor = database["asistencias"].find({"practica_id": practica_id})
    asistencias_por_alumno = {a["alumno_id"]: a async for a in asistencias_cursor}

    alumno_ids = materia["alumnos_ids"]
    alumnos_docs = {}
    if alumno_ids:
        cursor = database["usuarios"].find({"_id": {"$in": [ObjectId(a) for a in alumno_ids]}})
        alumnos_docs = {str(doc["_id"]): doc async for doc in cursor}

    detalle: list[FilaAsistencia] = []
    cumplieron = 0
    no_cumplieron = 0

    for alumno_id in alumno_ids:
        alumno = alumnos_docs.get(alumno_id)
        if alumno is None:
            continue  # el alumno ya no existe en el sistema; se omite del reporte

        asistencia = asistencias_por_alumno.get(alumno_id)

        if asistencia is None:
            detalle.append(FilaAsistencia(
                alumno_id=alumno_id, nombre=alumno["nombre"], codigo=alumno["codigo"],
                hora_identificacion=None, presente=False,
                cumplio_indumentaria=None, faltantes=[], evidencia_url=None,
            ))
        else:
            if asistencia["cumplio_indumentaria"]:
                cumplieron += 1
            else:
                no_cumplieron += 1
            detalle.append(FilaAsistencia(
                alumno_id=alumno_id, nombre=alumno["nombre"], codigo=alumno["codigo"],
                hora_identificacion=asistencia["hora_identificacion"], presente=True,
                cumplio_indumentaria=asistencia["cumplio_indumentaria"],
                faltantes=asistencia["faltantes"], evidencia_url=asistencia.get("evidencia_url"),
            ))

    presentes = sum(1 for f in detalle if f.presente)
    total = len(detalle)

    return ReportePractica(
        practica_id=practica_id,
        materia_nombre=materia["nombre"],
        docente_nombre=docente["nombre"] if docente else "—",
        fecha=practica["fecha"], hora_inicio=practica["hora_inicio"], hora_fin=practica["hora_fin"],
        total_matriculados=total, presentes=presentes, ausentes=total - presentes,
        cumplieron=cumplieron, no_cumplieron=no_cumplieron, detalle=detalle,
    )