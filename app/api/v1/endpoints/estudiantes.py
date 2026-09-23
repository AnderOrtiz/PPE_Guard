import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.api.v1.dependencies import require_role
from app.models.estudiante import EstudianteCreate, EstudianteOut
from app.services.camera_service import capture_single_frame
from app.services.face_service import get_face_embedding

router = APIRouter()


@router.get("/estudiantes", response_model=list[EstudianteOut], dependencies=[Depends(require_role("coordinador", "docente"))])
async def listar_estudiantes():
    database = get_database()
    cursor = database["estudiantes"].find()
    return [EstudianteOut(**doc) async for doc in cursor]


@router.post("/estudiantes", response_model=EstudianteOut, dependencies=[Depends(require_role("coordinador"))])
async def matricular_estudiante(data: EstudianteCreate):
    frame = await asyncio.to_thread(capture_single_frame)
    embedding = await asyncio.to_thread(get_face_embedding, frame)

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó exactamente un rostro. Asegúrate de que solo una persona esté frente a la cámara.",
        )

    database = get_database()
    doc = data.model_dump()
    doc["face_embedding"] = embedding

    try:
        result = await database["estudiantes"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un estudiante con ese código")

    creado = await database["estudiantes"].find_one({"_id": result.inserted_id})
    return EstudianteOut(**creado)