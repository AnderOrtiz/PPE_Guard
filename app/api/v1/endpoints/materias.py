from app.models.usuario import AlumnoEnMateriaOut
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.api.v1.dependencies import require_role, get_current_user
from app.models.materia import MateriaCreate, MateriaInDB, MateriaUpdate, AlumnoEnrollRequest

router = APIRouter()


@router.post("/materias", response_model=MateriaInDB, dependencies=[Depends(require_role("coordinador"))])
async def crear_materia(data: MateriaCreate, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(data.docente_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="docente_id inválido")

    database = get_database()
    docente = await database["usuarios"].find_one({"_id": ObjectId(data.docente_id), "rol": "docente"})
    if docente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="El docente indicado no existe")

    # La materia queda a cargo del coordinador del docente: un coordinador solo
    # puede crearla para sus propios docentes. El admin, para cualquiera.
    if user["rol"] == "coordinador" and docente["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes crear una materia para un docente fuera de tu cargo")

    doc = data.model_dump()
    doc["coordinador_id"] = docente["coordinador_id"]
    doc["alumnos_ids"] = []

    result = await database["materias"].insert_one(doc)
    creada = await database["materias"].find_one({"_id": result.inserted_id})
    return MateriaInDB(**creada)


@router.get("/materias", 
            response_model=list[MateriaInDB],
            dependencies=[Depends(require_role("coordinador", "docente"))])
async def listar_materias(docente_id: str | None = None, user: dict = Depends(get_current_user)):
    database = get_database()

    if user["rol"] == "docente":
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


@router.get("/materias/{materia_id}", response_model=MateriaInDB, dependencies=[Depends(require_role("coordinador", "docente"))])
async def obtener_materia(materia_id: str, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver una materia fuera de tu cargo")

    return MateriaInDB(**materia)


@router.patch("/materias/{materia_id}", response_model=MateriaInDB, dependencies=[Depends(require_role("coordinador"))])
async def actualizar_materia(materia_id: str, data: MateriaUpdate, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia fuera de tu cargo")

    cambios = data.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se envió ningún campo para actualizar")

    await database["materias"].update_one({"_id": ObjectId(materia_id)}, {"$set": cambios})

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)


@router.post(
    "/materias/{materia_id}/alumnos",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador", "docente"))],
)
async def matricular_alumno_en_materia(
    materia_id: str,
    data: AlumnoEnrollRequest,
    user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="La materia indicada no existe")

    # Verifica autoridad sobre ESTA materia específica. El admin no entra en
    # ninguna de estas dos condiciones (su rol nunca es "docente" ni "coordinador"
    # literalmente), así que pasa sin restricción adicional.
    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes matricular alumnos en una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes matricular alumnos en una materia fuera de tu cargo")

    alumno = await database["usuarios"].find_one({"codigo": data.codigo, "rol": "alumno"})
    if alumno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No existe un alumno con ese código")

    alumno_id = str(alumno["_id"])
    if alumno_id in materia["alumnos_ids"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="El alumno ya está matriculado en esta materia")

    await database["materias"].update_one(
        {"_id": ObjectId(materia_id)},
        {"$push": {"alumnos_ids": alumno_id}},
    )

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)


@router.get(
    "/materias/{materia_id}/alumnos",
    response_model=list[AlumnoEnMateriaOut],
    dependencies=[Depends(require_role("coordinador", "docente"))],
)
async def listar_alumnos_en_materia(materia_id: str):
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()

    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})

    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    alumnos_ids = materia["alumnos_ids"]

    cursor = database["usuarios"].find(
        {"_id": {"$in": [ObjectId(aid) for aid in alumnos_ids]}})
    return [AlumnoEnMateriaOut(**doc) async for doc in cursor]


@router.delete(
    "/materias/{materia_id}/alumnos/{alumno_id}",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador", "docente"))],
)

async def eliminar_alumno_de_materia(
    materia_id: str,
    alumno_id: str,
    user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()

    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})

    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia fuera de tu cargo")

    if alumno_id not in materia["alumnos_ids"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese alumno no está matriculado en esta materia")

    await database["materias"].update_one(
        {"_id": ObjectId(materia_id)},
        {"$pull": {"alumnos_ids": alumno_id}},
    )

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)
