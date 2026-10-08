import asyncio
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import hash_password
from app.core.cifrado import cifrar_embedding
from app.api.v1.dependencies import require_role, get_current_user, tiene_rol
from app.models.usuario import AlumnoCreate, DocenteCreate, CoordinadorCreate, DatosAcademicosUpdate, PasswordReset, UsuarioOut
from app.services.camera_service import capture_single_frame
from app.services.face_service import get_face_embedding

router = APIRouter()


async def _codigo_disponible(codigo: str) -> bool:
    database = get_database()
    return await database["usuarios"].find_one({"codigo": codigo}) is None


async def _insertar_usuario(doc: dict) -> UsuarioOut:
    database = get_database()
    try:
        result = await database["usuarios"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese código")
    creado = await database["usuarios"].find_one({"_id": result.inserted_id})
    return UsuarioOut(**creado)


@router.post("/usuarios/coordinadores", response_model=UsuarioOut, dependencies=[Depends(require_role("admin"))])
async def crear_coordinador(data: CoordinadorCreate):
    doc = data.model_dump(exclude={"password"})
    doc["password_hash"] = hash_password(data.password)
    doc["rol"] = "coordinador"
    return await _insertar_usuario(doc)


@router.post("/usuarios/docentes", response_model=UsuarioOut, dependencies=[Depends(require_role("coordinador"))])
async def crear_docente(data: DocenteCreate, user: dict = Depends(get_current_user)):
    # Un coordinador crea docentes a su propio cargo; solo el admin elige a cuál asignarlo.
    coordinador_id = user["user_id"] if user["rol"] == "coordinador" else data.coordinador_id
    if coordinador_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Indica el coordinador a cargo del docente (coordinador_id)")
    if not ObjectId.is_valid(coordinador_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="coordinador_id inválido")

    database = get_database()
    coordinador = await database["usuarios"].find_one({"_id": ObjectId(coordinador_id), "rol": "coordinador"})
    if coordinador is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El coordinador indicado no existe")

    doc = data.model_dump(exclude={"password"})
    doc["coordinador_id"] = coordinador_id
    doc["password_hash"] = hash_password(data.password)
    doc["rol"] = "docente"
    return await _insertar_usuario(doc)


async def _validar_materias_para_matricular(materias_ids: list[str], user: dict) -> list[ObjectId]:
    """Mismas reglas que matricular en /materias/{id}/alumnos: cada quien solo en las suyas."""
    if any(not ObjectId.is_valid(mid) for mid in materias_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materias_ids contiene un id inválido")

    database = get_database()
    object_ids = [ObjectId(mid) for mid in set(materias_ids)]
    materias = [m async for m in database["materias"].find({"_id": {"$in": object_ids}})]
    if len(materias) != len(object_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alguna de las materias indicadas no existe")

    for materia in materias:
        if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes matricular alumnos en una materia que no impartes")
        if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes matricular alumnos en una materia fuera de tu cargo")

    return object_ids


@router.post("/usuarios/alumnos", response_model=UsuarioOut, dependencies=[Depends(require_role("coordinador", "docente"))])
async def crear_alumno(data: AlumnoCreate, user: dict = Depends(get_current_user)):
    # Se verifican el código y las materias ANTES de la captura: son consultas rápidas, y no
    # tiene sentido hacer esperar al usuario por la cámara para rechazarlo después.
    if not await _codigo_disponible(data.codigo):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese código")
    # Los datos académicos los fija la coordinación, también en el alta
    if not tiene_rol(user, "coordinador") and (data.carrera is not None or data.facultad is not None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un coordinador puede asignar la carrera y la facultad de un alumno")
    materias_ids = await _validar_materias_para_matricular(data.materias_ids, user)

    frame = await asyncio.to_thread(capture_single_frame)
    embedding = await asyncio.to_thread(get_face_embedding, frame)

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó exactamente un rostro. Asegúrate de que solo una persona esté frente a la cámara.",
        )

    doc = data.model_dump(exclude={"password", "materias_ids"})
    doc["password_hash"] = hash_password(data.password)
    doc["rol"] = "alumno"
    doc["face_embedding"] = cifrar_embedding(embedding)  # en la base nunca queda el vector en claro
    creado = await _insertar_usuario(doc)

    if materias_ids:
        await get_database()["materias"].update_many(
            {"_id": {"$in": materias_ids}},
            {"$addToSet": {"alumnos_ids": creado.id}},
        )
    return creado


async def _filtro_visibilidad(user: dict) -> dict:
    """Acota el listado a lo que el usuario tiene a su cargo, igual que listar_materias."""
    if user["rol"] not in ("docente", "coordinador"):  # admin
        return {}

    database = get_database()
    campo = "docente_id" if user["rol"] == "docente" else "coordinador_id"
    alumnos_ids = set()
    async for materia in database["materias"].find({campo: user["user_id"]}, {"alumnos_ids": 1}):
        alumnos_ids.update(materia["alumnos_ids"])

    alumnos = {"_id": {"$in": [ObjectId(aid) for aid in alumnos_ids]}}
    if user["rol"] == "docente":
        return alumnos
    return {"$or": [alumnos, {"rol": "docente", "coordinador_id": user["user_id"]}]}


@router.get("/usuarios", response_model=list[UsuarioOut], dependencies=[Depends(require_role("coordinador", "docente"))])
async def listar_usuarios(
    rol: Literal["alumno", "docente", "coordinador"] | None = None,
    user: dict = Depends(get_current_user),
):
    database = get_database()

    filtro = await _filtro_visibilidad(user)
    if rol is not None:
        filtro["rol"] = rol

    cursor = database["usuarios"].find(filtro).sort("nombre", 1)
    return [UsuarioOut(**doc) async for doc in cursor]


@router.get("/usuarios/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_role("coordinador", "docente"))])
async def obtener_usuario(usuario_id: str, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(usuario_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="usuario_id inválido")

    database = get_database()
    usuario = await database["usuarios"].find_one({"_id": ObjectId(usuario_id)})
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario indicado no existe")

    # Misma visibilidad que listar_usuarios; cada quien puede verse a sí mismo.
    if usuario_id != user["user_id"]:
        filtro = await _filtro_visibilidad(user)
        visible = await database["usuarios"].find_one({"$and": [{"_id": usuario["_id"]}, filtro]}, {"_id": 1})
        if visible is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver un usuario fuera de tu cargo")

    return UsuarioOut(**usuario)


async def _alumno_o_docente_a_cargo(usuario_id: str, user: dict) -> dict:
    """El usuario sobre el que un coordinador puede actuar: alumnos y docentes de su cargo.
    El admin puede con cualquiera."""
    if not ObjectId.is_valid(usuario_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="usuario_id inválido")

    database = get_database()
    usuario = await database["usuarios"].find_one({"_id": ObjectId(usuario_id)})
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario indicado no existe")

    if user["rol"] == "coordinador":
        if usuario["rol"] not in ("alumno", "docente"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes modificar a alumnos y docentes")
        filtro = await _filtro_visibilidad(user)
        visible = await database["usuarios"].find_one({"$and": [{"_id": usuario["_id"]}, filtro]}, {"_id": 1})
        if visible is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar a un usuario fuera de tu cargo")

    return usuario


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_role("coordinador"))])
async def actualizar_datos_academicos(usuario_id: str, data: DatosAcademicosUpdate, user: dict = Depends(get_current_user)):
    usuario = await _alumno_o_docente_a_cargo(usuario_id, user)

    cambios = data.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se envió ningún campo para actualizar")

    database = get_database()
    await database["usuarios"].update_one({"_id": usuario["_id"]}, {"$set": cambios})

    actualizado = await database["usuarios"].find_one({"_id": usuario["_id"]})
    return UsuarioOut(**actualizado)


@router.post(
    "/usuarios/{usuario_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("coordinador"))],
)
async def resetear_password(usuario_id: str, data: PasswordReset, user: dict = Depends(get_current_user)):
    usuario = await _alumno_o_docente_a_cargo(usuario_id, user)

    await get_database()["usuarios"].update_one(
        {"_id": usuario["_id"]},
        {"$set": {"password_hash": hash_password(data.password_nueva)}},
    )
