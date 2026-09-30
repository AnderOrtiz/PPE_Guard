from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.api.v1.dependencies import require_role, get_current_user
from app.models.practica import PracticaCreate, PracticaInDB, ConfirmarRequest
from app.services.face_service import get_candidatos_de_materia
from app.services.practica_orchestrator import PracticaOrchestrator
from app.services import practica_registry

router = APIRouter()


@router.post("/practicas", response_model=PracticaInDB, dependencies=[Depends(require_role("docente"))])
async def iniciar_practica(data: PracticaCreate, user: dict = Depends(get_current_user)):
    if practica_registry.hay_practica_activa():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay una práctica en curso; finalízala antes de iniciar otra")

    if not ObjectId.is_valid(data.materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(data.materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes iniciar una práctica de una materia que no impartes")

    catalogo = await database["practices"].find_one({"area": materia["area"]})
    if catalogo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No hay PPE configurado para el área '{materia['area']}'")
    required_ppe = set(catalogo["ppe_requerido"])

    doc = {
        "materia_id": data.materia_id,
        "docente_id": materia["docente_id"],
        "fecha": datetime.now(timezone.utc),
        "hora_inicio": datetime.now(timezone.utc),
        "hora_fin": None,
        "estado": "activa",
    }
    result = await database["practicas"].insert_one(doc)
    practica_id = str(result.inserted_id)

    candidatos = await get_candidatos_de_materia(database, data.materia_id)

    orquestador = PracticaOrchestrator(practica_id, materia["area"], required_ppe, candidatos)
    orquestador.start()
    practica_registry.registrar(practica_id, orquestador)

    creada = await database["practicas"].find_one({"_id": result.inserted_id})
    return PracticaInDB(**creada)


@router.get("/practicas/active", response_model=PracticaInDB | None, dependencies=[Depends(require_role("docente"))])
async def practica_activa():
    if not practica_registry.hay_practica_activa():
        return None

    database = get_database()
    practica = await database["practicas"].find_one({"estado": "activa"})
    return PracticaInDB(**practica) if practica else None


@router.post("/practicas/{practica_id}/confirmar", dependencies=[Depends(require_role("docente"))])
async def confirmar_identificacion(practica_id: str, data: ConfirmarRequest):
    orquestador = practica_registry.obtener(practica_id)
    if orquestador is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay una práctica activa con ese id")

    ok = orquestador.confirmar_identificacion(data.alumno_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese alumno no es el último identificado, o la práctica ya está en modo indumentaria",
        )

    return {"fase": "indumentaria", "alumno_id": data.alumno_id}


@router.post("/practicas/{practica_id}/end", response_model=PracticaInDB, dependencies=[Depends(require_role("docente"))])
async def finalizar_practica(practica_id: str, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(practica_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="practica_id inválido")

    database = get_database()
    practica = await database["practicas"].find_one({"_id": ObjectId(practica_id)})
    if practica is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La práctica indicada no existe")

    if practica["estado"] == "finalizada":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta práctica ya fue finalizada")

    if user["rol"] == "docente" and practica["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes finalizar una práctica que no impartes")

    orquestador = practica_registry.obtener(practica_id)
    if orquestador is not None:
        orquestador.stop()
        practica_registry.eliminar(practica_id)

    await database["practicas"].update_one(
        {"_id": ObjectId(practica_id)},
        {"$set": {"hora_fin": datetime.now(timezone.utc), "estado": "finalizada"}},
    )

    finalizada = await database["practicas"].find_one({"_id": ObjectId(practica_id)})
    return PracticaInDB(**finalizada)