from fastapi import APIRouter, Depends

from app.core.database import get_database
from app.api.v1.dependencies import require_role
from app.models.aula import AulaCreate, AulaInDB

router = APIRouter()


@router.post("/aulas", response_model=AulaInDB, dependencies=[Depends(require_role("coordinador"))])
async def crear_aula(aula: AulaCreate):
    database = get_database()
    doc = aula.model_dump()
    doc["estudiantes_ids"] = []
    result = await database["aulas"].insert_one(doc)
    creada = await database["aulas"].find_one({"_id": result.inserted_id})
    return AulaInDB(**creada)


@router.get("/aulas", response_model=list[AulaInDB], dependencies=[Depends(require_role("coordinador", "docente"))])
async def listar_aulas():
    database = get_database()
    cursor = database["aulas"].find()
    return [AulaInDB(**doc) async for doc in cursor]