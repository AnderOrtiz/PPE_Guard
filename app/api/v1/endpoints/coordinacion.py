from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.core.database import get_database
from app.api.v1.dependencies import require_role
from app.models.coordinacion import ResumenCoordinacion

router = APIRouter()

DIAS_RECIENTE = 7  # ventana de "materia nueva" y de "laboratorio activo"


@router.get("/coordinacion/resumen", response_model=ResumenCoordinacion)
async def resumen_coordinacion(user: dict = Depends(require_role("coordinador"))):
    database = get_database()
    es_admin = user["rol"] == "admin"

    ahora = datetime.now(timezone.utc)
    desde_reciente = ahora - timedelta(days=DIAS_RECIENTE)
    # "Hoy" es el día del servidor (hora local), no el día UTC.
    inicio_hoy = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)

    materia_filtro = {} if es_admin else {"coordinador_id": user["user_id"]}
    materias = [m async for m in database["materias"].find(materia_filtro, {"alumnos_ids": 1})]
    materia_ids = [str(m["_id"]) for m in materias]

    # Las materias no guardan fecha de creación: se toma la que lleva su ObjectId.
    materias_nuevas = sum(1 for m in materias if m["_id"].generation_time >= desde_reciente)

    con_practica_reciente = await database["practicas"].distinct(
        "materia_id", {"materia_id": {"$in": materia_ids}, "hora_inicio": {"$gte": desde_reciente}})
    docentes_hoy = await database["practicas"].distinct(
        "docente_id", {"materia_id": {"$in": materia_ids}, "hora_inicio": {"$gte": inicio_hoy}})

    docente_filtro = {"rol": "docente"} if es_admin else {"rol": "docente", "coordinador_id": user["user_id"]}
    docentes = await database["usuarios"].count_documents(docente_filtro)

    if es_admin:
        alumnos = await database["usuarios"].count_documents({"rol": "alumno"})
    else:
        alumnos = len({alumno_id for m in materias for alumno_id in m["alumnos_ids"]})

    return ResumenCoordinacion(
        materias=len(materias),
        materias_nuevas=materias_nuevas,
        materias_lab_activo=len(con_practica_reciente),
        docentes=docentes,
        docentes_activos_hoy=len(docentes_hoy),
        alumnos=alumnos,
    )
