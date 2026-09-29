from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.api.v1.dependencies import require_role, get_current_user
from app.models.materia import MateriaCreate, MateriaInDB

router = APIRouter()


@router.post("/materias", response_model=MateriaInDB, dependencies=[Depends(require_role("coordinador"))])
async def crear_materia(data: MateriaCreate):
    if not ObjectId.is_valid(data.docente_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="docente_id inválido")

    database = get_database()
    docente = await database["usuarios"].find_one({"_id": ObjectId(data.docente_id), "rol": "docente"})
    if docente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El docente indicado no existe")

    # requerimientos = data.requerimientos
    # if requerimientos is None:
    #     catalogo = await database["practices"].find_one({"area": data.area})
    #     if catalogo is None:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail=f"No hay PPE por defecto configurado para el área '{data.area}'",
    #         )
    #     requerimientos = catalogo["ppe_requerido"]

    doc = data.model_dump()
    # doc["requerimientos"] = requerimientos
    doc["coordinador_id"] = docente["coordinador_id"]
    doc["alumnos_ids"] = []

    result = await database["materias"].insert_one(doc)
    creada = await database["materias"].find_one({"_id": result.inserted_id})
    return MateriaInDB(**creada)


@router.get("/materias", response_model=list[MateriaInDB], dependencies=[Depends(require_role("coordinador", "docente"))])
async def listar_materias(docente_id: str | None = None, user: dict = Depends(get_current_user)):
    database = get_database()

    if user["rol"] == "docente":
        # Un docente nunca puede consultar las materias de otro, aunque mande el parámetro
        filtro = {"docente_id": user["user_id"]}
    elif user["rol"] == "coordinador":
        filtro = {"coordinador_id": user["user_id"]}
        if docente_id is not None:
            filtro["docente_id"] = docente_id
    else:  # admin
        filtro = {}
        if docente_id is not None:
            filtro["docente_id"] = docente_id

    cursor = database["materias"].find(filtro)
    return [MateriaInDB(**doc) async for doc in cursor]